"""Build a deterministic, hash-verified SERMAX installer package.

Only explicitly selected source files are included. This prevents accidental
collection of user memory, databases, logs, credentials, and backups.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath


class BuildError(Exception):
    pass


def safe_relative(value: str) -> Path:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not value.strip() or path.is_absolute() or any(p in ("", ".", "..") for p in path.parts):
        raise BuildError(f"Caminho relativo inválido: {value!r}")
    if path.parts and ":" in path.parts[0]:
        raise BuildError(f"Caminho com unidade não permitido: {value!r}")
    return Path(*path.parts)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_mapping(value: str) -> tuple[Path, Path]:
    if "=" not in value:
        raise BuildError("Mapeamento deve usar origem=destino.")
    source, target = value.split("=", 1)
    return safe_relative(source), safe_relative(target)


def build_package(source_root: Path, output_dir: Path, version: str,
                  mappings: list[tuple[Path, Path]],
                  preserve_paths: list[str] | None = None) -> dict:
    source_root = source_root.expanduser().resolve(strict=True)
    if not source_root.is_dir():
        raise BuildError("A origem precisa ser uma pasta.")
    output_dir = output_dir.expanduser().resolve()
    if output_dir == source_root or source_root in output_dir.parents:
        raise BuildError("A pasta de saída não pode ficar dentro da origem.")
    if not version.strip():
        raise BuildError("Informe a versão do pacote.")
    if not mappings:
        raise BuildError("Informe ao menos um arquivo explicitamente.")

    seen: set[str] = set()
    staged_entries = []
    temp_parent = output_dir.parent
    temp_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".sermax-package-", dir=temp_parent))
    try:
        payload = temp_dir / "payload"
        for source_rel, target_rel in mappings:
            source_candidate = source_root / source_rel
            if source_candidate.is_symlink():
                raise BuildError(f"Links simbólicos não são aceitos: {source_rel}")
            source = source_candidate.resolve(strict=True)
            try:
                source.relative_to(source_root)
            except ValueError as exc:
                raise BuildError(f"Origem fora da pasta autorizada: {source_rel}") from exc
            if not source.is_file():
                raise BuildError(f"Origem não é arquivo regular: {source_rel}")
            key = target_rel.as_posix().casefold()
            if key in seen:
                raise BuildError(f"Destino duplicado: {target_rel}")
            seen.add(key)
            target = payload / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            staged_entries.append({
                "source": f"payload/{target_rel.as_posix()}",
                "target": target_rel.as_posix(),
                "sha256": sha256(target),
                "size_bytes": target.stat().st_size,
            })

        preserve = preserve_paths or [
            "memoria_sermax.json", "memoria_neural_pestinha.json",
            "data", "config", ".sermax-backups"
        ]
        for item in preserve:
            safe_relative(item)

        manifest = {
            "schema_version": 1,
            "version": version,
            "package_type": "sermax",
            "created_by": "sermax-package-builder",
            "preserve_paths": preserve,
            "files": sorted(staged_entries, key=lambda item: item["target"].casefold()),
        }
        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n",
            encoding="utf-8"
        )

        if output_dir.exists():
            raise BuildError(f"A pasta de saída já existe: {output_dir}")
        os.replace(temp_dir, output_dir)
        return {
            "output": str(output_dir),
            "version": version,
            "file_count": len(staged_entries),
            "total_bytes": sum(item["size_bytes"] for item in staged_entries),
        }
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Monta pacote SERMAX com hashes SHA-256.")
    parser.add_argument("--source", type=Path, required=True, help="Raiz dos arquivos autorizados.")
    parser.add_argument("--output", type=Path, required=True, help="Nova pasta de pacote, ainda inexistente.")
    parser.add_argument("--version", required=True, help="Versão do pacote.")
    parser.add_argument("--map", action="append", default=[], metavar="ORIGEM=DESTINO",
                        help="Arquivo explicitamente incluído. Repetir para cada arquivo.")
    args = parser.parse_args()
    try:
        mappings = [parse_mapping(item) for item in args.map]
        result = build_package(args.source, args.output, args.version, mappings)
    except (BuildError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
