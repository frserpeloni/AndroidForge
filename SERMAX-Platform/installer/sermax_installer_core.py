"""Transactional file installer engine for SERMAX packages."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


class PackageError(Exception):
    """Invalid or unsafe installation package."""


@dataclass(frozen=True)
class PackageFile:
    source: Path
    target_relative: Path
    sha256: str


ProgressCallback = Callable[[str, int, int, str], None]


def _safe_relative(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PackageError("Caminho vazio no manifesto.")
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    if posix.is_absolute() or any(part in ("", ".", "..") for part in posix.parts):
        raise PackageError(f"Caminho inseguro no manifesto: {value!r}")
    if posix.parts and ":" in posix.parts[0]:
        raise PackageError(f"Caminho com unidade não permitido: {value!r}")
    return Path(*posix.parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_package(package_dir: Path) -> tuple[dict[str, Any], list[PackageFile]]:
    package_dir = package_dir.resolve(strict=True)
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        raise PackageError("manifest.json não encontrado.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"Manifesto inválido: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise PackageError("Versão ou estrutura do manifesto não suportada.")
    version = manifest.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PackageError("Versão do pacote ausente.")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise PackageError("Manifesto sem arquivos de instalação.")

    files: list[PackageFile] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise PackageError("Entrada de arquivo inválida.")
        source_rel = _safe_relative(item.get("source"))
        target_rel = _safe_relative(item.get("target"))
        expected_hash = item.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise PackageError(f"SHA-256 inválido para {source_rel}.")
        key = target_rel.as_posix().casefold()
        reserved = {
            ".sermax-install.json",
            ".sermax-install.json.tmp",
            ".sermax-install.json.rollback",
        }
        if key in reserved or key == ".sermax-backups" or key.startswith(".sermax-backups/"):
            raise PackageError(f"Destino reservado pelo instalador: {target_rel}.")
        if key in seen:
            raise PackageError(f"Destino duplicado no manifesto: {target_rel}.")
        seen.add(key)
        source = (package_dir / source_rel).resolve(strict=True)
        try:
            source.relative_to(package_dir)
        except ValueError as exc:
            raise PackageError(f"Origem fora do pacote: {source_rel}.") from exc
        if not source.is_file():
            raise PackageError(f"Arquivo de origem ausente: {source_rel}.")
        actual_hash = _sha256(source)
        if actual_hash.lower() != expected_hash.lower():
            raise PackageError(f"Falha de integridade SHA-256: {source_rel}.")
        files.append(PackageFile(source, target_rel, actual_hash))

    preserve = manifest.get("preserve_paths", [])
    if not isinstance(preserve, list):
        raise PackageError("preserve_paths deve ser uma lista.")
    for entry in preserve:
        _safe_relative(entry)
    return manifest, files


def detect_installation(install_dir: Path) -> dict[str, Any]:
    """Read installer metadata without modifying the destination."""
    root = install_dir.expanduser().resolve()
    marker = root / ".sermax-install.json"
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("version"), str):
                return {"installed": True, "version": data["version"], "marker": str(marker)}
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"installed": True, "version": None, "marker": str(marker), "metadata_error": True}
    known = (root / "SERMAX.exe", root / "SERMAX-Windows" / "sermax_launcher.py",
             root / "SERMAX-Platform" / "backend" / "server.py")
    if any(item.exists() for item in known):
        return {"installed": True, "version": None, "marker": None}
    return {"installed": False, "version": None, "marker": None}


def preflight(package_dir: Path, install_dir: Path) -> dict[str, Any]:
    manifest, files = load_package(package_dir)
    root = install_dir.expanduser().resolve()
    probe = root
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    required = sum(item.source.stat().st_size for item in files)
    free = shutil.disk_usage(probe).free
    if free < required:
        raise PackageError(
            f"Espaço insuficiente: necessários {required} bytes, disponíveis {free}."
        )
    installed = detect_installation(root)
    return {
        "version": manifest["version"],
        "file_count": len(files),
        "required_bytes": required,
        "free_bytes": free,
        "preserve_paths": list(manifest.get("preserve_paths", [])),
        "installation": installed,
    }


def install_package(package_dir: Path, install_dir: Path,
                    progress: ProgressCallback | None = None) -> dict[str, Any]:
    """Install only manifest-listed files, backing up replaced files first."""
    manifest, files = load_package(package_dir)
    root = install_dir.expanduser().resolve()
    preflight(package_dir, root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = root / ".sermax-backups" / stamp
    staged: list[tuple[Path, Path | None, Path]] = []
    completed: list[Path] = []
    marker = root / ".sermax-install.json"
    marker_existed = marker.is_file()
    marker_previous = marker.read_bytes() if marker_existed else None

    def report(phase: str, current: int, total: int, name: str = "") -> None:
        if progress:
            progress(phase, current, total, name)

    try:
        report("preparing", 0, len(files), "")
        for index, item in enumerate(files, start=1):
            target = (root / item.target_relative).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise PackageError(f"Destino fora da instalação: {item.target_relative}.") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            previous: Path | None = None
            if target.exists():
                if not target.is_file():
                    raise PackageError(f"Destino existente não é arquivo: {target}.")
                backup = backup_dir / item.target_relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                previous = backup
            fd, temp_name = tempfile.mkstemp(prefix=".sermax-install-", dir=target.parent)
            os.close(fd)
            temp_path = Path(temp_name)
            shutil.copy2(item.source, temp_path)
            if _sha256(temp_path) != item.sha256:
                temp_path.unlink(missing_ok=True)
                raise PackageError(f"Integridade alterada durante cópia: {item.source.name}.")
            staged.append((target, previous, temp_path))
            report("staging", index, len(files), item.target_relative.as_posix())

        for index, (target, _previous, temp_path) in enumerate(staged, start=1):
            os.replace(temp_path, target)
            completed.append(target)
            report("installing", index, len(staged), target.name)

        marker_data = {
            "schema_version": 1,
            "version": manifest["version"],
            "installed_at_utc": datetime.now(timezone.utc).isoformat(),
            "installed_files": len(completed),
        }
        marker_tmp = root / ".sermax-install.json.tmp"
        marker_tmp.write_text(json.dumps(marker_data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(marker_tmp, marker)
        report("complete", len(completed), len(completed), "")
    except Exception:
        for target, previous, _temp_path in reversed(staged):
            if target in completed:
                if previous and previous.exists():
                    restore = target.with_name(target.name + ".sermax-restore")
                    shutil.copy2(previous, restore)
                    os.replace(restore, target)
                else:
                    target.unlink(missing_ok=True)
        for _target, _previous, temp_path in staged:
            temp_path.unlink(missing_ok=True)
        marker_tmp = root / ".sermax-install.json.rollback"
        if marker_existed and marker_previous is not None:
            marker_tmp.write_bytes(marker_previous)
            os.replace(marker_tmp, marker)
        else:
            marker.unlink(missing_ok=True)
        raise

    return {
        "status": "success",
        "version": manifest["version"],
        "installed_files": len(completed),
        "backup_directory": str(backup_dir) if backup_dir.exists() else None,
        "preserved_paths": list(manifest.get("preserve_paths", [])),
    }
