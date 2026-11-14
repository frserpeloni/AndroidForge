"""Comparação conservadora de duas enumerações de diretório.

Este módulo é puro: não acessa o filesystem nem chama APIs nativas.
Duas enumerações iguais reduzem a janela de inconsistência, mas não
constituem snapshot transacional do volume.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from sermax_windows_directory_enum import DirectoryEntry


class DirectorySnapshotError(RuntimeError):
    """As enumerações são inválidas ou não representam o mesmo estado."""


def _name_key(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise DirectorySnapshotError("Nome inválido na enumeração.")
    return unicodedata.normalize("NFKC", name).casefold()


def _entry_signature(entry: DirectoryEntry) -> tuple[object, ...]:
    return (
        entry.attributes,
        entry.end_of_file,
        entry.allocation_size,
        entry.creation_time,
        entry.last_access_time,
        entry.last_write_time,
        entry.change_time,
        entry.ea_size,
        entry.short_name,
        entry.file_id,
    )


def _canonicalize(
    entries: Iterable[DirectoryEntry],
) -> dict[str, tuple[tuple[object, ...], DirectoryEntry]]:
    result: dict[str, tuple[tuple[object, ...], DirectoryEntry]] = {}
    short_names: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, DirectoryEntry):
            raise DirectorySnapshotError("Registro de enumeração com tipo inválido.")
        key = _name_key(entry.name)
        if key in result:
            raise DirectorySnapshotError(
                "Colisão de nomes após normalização NFKC e casefold."
            )
        if entry.short_name:
            short_key = _name_key(entry.short_name)
            previous = short_names.get(short_key)
            if previous is not None and previous != key:
                raise DirectorySnapshotError("Colisão entre aliases 8.3.")
            short_names[short_key] = key
        result[key] = (_entry_signature(entry), entry)
    return result


def compare_directory_snapshots(
    first: Iterable[DirectoryEntry],
    second: Iterable[DirectoryEntry],
) -> tuple[DirectoryEntry, ...]:
    """Exige igualdade integral entre duas enumerações independentes.

    FileIndex é deliberadamente excluído, pois não representa identidade
    estável do arquivo. Nome, FileId, metadados e alias curto são comparados.
    Retorna a primeira enumeração em ordem determinística pelo nome normalizado.
    """
    left = _canonicalize(first)
    right = _canonicalize(second)
    if left.keys() != right.keys():
        raise DirectorySnapshotError(
            "O namespace mudou entre enumerações: entrada criada, removida ou renomeada."
        )
    for key in left:
        if left[key][0] != right[key][0]:
            raise DirectorySnapshotError(
                f"Metadados ou identidade mudaram entre enumerações: {left[key][1].name!r}."
            )
    return tuple(left[key][1] for key in sorted(left))
