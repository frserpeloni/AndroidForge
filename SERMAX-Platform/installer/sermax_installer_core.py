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
    size_bytes: int


ProgressCallback = Callable[[str, int, int, str], None]


def _safe_relative(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PackageError("Caminho vazio no manifesto.")
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    if posix.is_absolute() or any(part in ("", ".", "..") for part in posix.parts):
        raise PackageError(f"Caminho inseguro no manifesto: {value!r}")
    for part in posix.parts:
        stem = part.split(".", 1)[0].upper()
        if (":" in part or part.endswith((" ", ".")) or
                stem in {"CON", "PRN", "AUX", "NUL"} or
                (stem.startswith("COM") and stem[3:].isdigit()) or
                (stem.startswith("LPT") and stem[3:].isdigit())):
            raise PackageError(f"Componente de caminho inválido no Windows: {value!r}")
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

    preserve = manifest.get("preserve_paths", [])
    if not isinstance(preserve, list):
        raise PackageError("preserve_paths deve ser uma lista.")
    protected = {
        "memoria_sermax.json",
        "memoria_neural_pestinha.json",
        "data",
        "config",
        "credentials",
        "secrets",
        ".sermax-backups",
    }
    for entry in preserve:
        protected.add(_safe_relative(entry).as_posix().casefold())

    files: list[PackageFile] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise PackageError("Entrada de arquivo inválida.")
        source_rel = _safe_relative(item.get("source"))
        target_rel = _safe_relative(item.get("target"))
        expected_hash = item.get("sha256")
        if (not isinstance(expected_hash, str) or len(expected_hash) != 64 or
                any(char not in "0123456789abcdefABCDEF" for char in expected_hash)):
            raise PackageError(f"SHA-256 inválido para {source_rel}.")
        expected_size = item.get("size_bytes")
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
            raise PackageError(f"size_bytes inválido para {source_rel}.")
        key = target_rel.as_posix().casefold()
        reserved = {
            ".sermax-install.json",
            ".sermax-install.json.tmp",
            ".sermax-install.json.rollback",
        }
        if key in reserved:
            raise PackageError(f"Destino reservado pelo instalador: {target_rel}.")
        if any(key == path or key.startswith(path + "/") for path in protected):
            raise PackageError(f"Destino protegido para preservar dados do usuário: {target_rel}.")
        if any(key == old or key.startswith(old + "/") or old.startswith(key + "/") for old in seen):
            raise PackageError(f"Destino duplicado ou conflitante no manifesto: {target_rel}.")
        seen.add(key)
        source_candidate = package_dir / source_rel
        cursor = package_dir
        for part in source_rel.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise PackageError(f"Links simbólicos não são aceitos no pacote: {source_rel}.")
        source = source_candidate.resolve(strict=True)
        try:
            source.relative_to(package_dir)
        except ValueError as exc:
            raise PackageError(f"Origem fora do pacote: {source_rel}.") from exc
        if not source.is_file():
            raise PackageError(f"Arquivo de origem ausente: {source_rel}.")
        actual_size = source.stat().st_size
        if actual_size != expected_size:
            raise PackageError(f"Tamanho divergente no manifesto: {source_rel}.")
        actual_hash = _sha256(source)
        if actual_hash.lower() != expected_hash.lower():
            raise PackageError(f"Falha de integridade SHA-256: {source_rel}.")
        files.append(PackageFile(source, target_rel, actual_hash, actual_size))

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
    backup_bytes = 0
    if root.exists():
        for item in files:
            existing = root / item.target_relative
            if existing.is_file() and not existing.is_symlink():
                backup_bytes += existing.stat().st_size
    required = sum(item.size_bytes for item in files) * 2 + backup_bytes
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
        backup_root = root / ".sermax-backups"
        if backup_root.is_symlink():
            raise PackageError("A pasta de backups é um link simbólico. Instalação bloqueada.")
        for index, item in enumerate(files, start=1):
            target = root / item.target_relative
            cursor = root
            for part in item.target_relative.parts[:-1]:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise PackageError(f"Pasta de destino é link simbólico: {cursor}.")
            if target.is_symlink():
                raise PackageError(f"Arquivo de destino é link simbólico: {target}.")
            target.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = target.parent.resolve()
            try:
                resolved_parent.relative_to(root)
            except ValueError as exc:
                raise PackageError(f"Destino fora da instalação: {item.target_relative}.") from exc
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
