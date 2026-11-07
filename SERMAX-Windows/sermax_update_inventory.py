"""Inventário somente de leitura para o atualizador SERMAX.

Este módulo não instala, copia, remove ou modifica arquivos. A raiz é sempre
informada pelo chamador; nenhum caminho padrão aponta para C:\\SERMAX.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import unicodedata
from pathlib import Path
from typing import Iterable

PROTECTED_FILES = frozenset({
    "memoria_sermax.json",
    "memoria_neural_pestinha.json",
})

REPARSE_POINT_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_WINDOWS_RESERVED = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?$",
    re.IGNORECASE,
)


class InventoryError(RuntimeError):
    """Falha que impede confiar no inventário."""


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _is_reparse_point(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & REPARSE_POINT_ATTRIBUTE)


def _normalize_relative(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise InventoryError("Caminho relativo vazio ou inválido.")
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if normalized.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise InventoryError(f"Caminho relativo inseguro: {value!r}")

    for part in parts:
        if ":" in part or any(ord(char) < 32 for char in part):
            raise InventoryError(f"Caminho com caractere reservado: {value!r}")
        if part.endswith((" ", ".")):
            raise InventoryError(f"Componente com ponto/espaço final: {value!r}")
        if unicodedata.normalize("NFC", part) != part:
            raise InventoryError(f"Componente Unicode não normalizado: {value!r}")
        if _WINDOWS_RESERVED.fullmatch(part):
            raise InventoryError(f"Nome reservado do Windows: {value!r}")

    return "/".join(parts)


def inventory_directory(
    root: str | os.PathLike[str],
    *,
    managed_paths: Iterable[str] = (),
) -> list[dict[str, object]]:
    """Retorna inventário determinístico sem seguir symlinks/junctions.

    managed_paths é uma allowlist explícita, relativa à raiz. Tudo o que não
    estiver nela será classificado como protected ou unknown, nunca managed.
    Diretórios e arquivos reparse são registrados como blocked e não percorridos.
    """
    root_path = Path(root)
    try:
        root_info = root_path.lstat()
    except OSError as exc:
        raise InventoryError(f"Não foi possível inspecionar a raiz: {exc}") from exc

    if stat.S_ISLNK(root_info.st_mode) or _is_reparse_point(root_info):
        raise InventoryError("A raiz da instalação não pode ser link/reparse point.")
    if not stat.S_ISDIR(root_info.st_mode):
        raise InventoryError("A raiz informada não é um diretório.")

    root_path = root_path.resolve(strict=True)
    allowlist = {_normalize_relative(item).casefold() for item in managed_paths}
    records: list[dict[str, object]] = []

    def walk(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name.casefold())
        except OSError as exc:
            raise InventoryError(f"Falha ao enumerar diretório relativo: {exc}") from exc

        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root_path).as_posix()
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise InventoryError(f"Falha ao inspecionar entrada {relative!r}: {exc}") from exc

            # Rejeita nomes ambíguos para destinos Windows antes de classificá-los.
            _normalize_relative(relative)

            if stat.S_ISLNK(info.st_mode) or _is_reparse_point(info):
                records.append({
                    "path": relative, "type": "reparse", "size": None,
                    "sha256": None, "classification": "blocked",
                })
                continue

            if stat.S_ISDIR(info.st_mode):
                records.append({
                    "path": relative, "type": "directory", "size": None,
                    "sha256": None, "classification": "unknown",
                })
                walk(path)
                continue

            if not stat.S_ISREG(info.st_mode):
                records.append({
                    "path": relative, "type": "special", "size": None,
                    "sha256": None, "classification": "blocked",
                })
                continue

            try:
                digest = _sha256_file(path)
                final_size = path.stat(follow_symlinks=False).st_size
            except OSError as exc:
                raise InventoryError(f"Falha ao calcular hash de {relative!r}: {exc}") from exc

            basename = path.name.casefold()
            if basename in PROTECTED_FILES:
                classification = "protected"
            elif relative.casefold() in allowlist:
                classification = "managed"
            else:
                classification = "unknown"

            records.append({
                "path": relative,
                "type": "file",
                "size": final_size,
                "sha256": digest,
                "classification": classification,
            })

    walk(root_path)
    return records
