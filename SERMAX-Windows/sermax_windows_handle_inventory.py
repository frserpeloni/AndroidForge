"""Inventário conservador de uma árvore a partir de um handle raiz validado.

Não abre caminhos absolutos, não instala, copia ou altera arquivos. Cada
componente é aberto relativamente ao handle do diretório pai. Não constitui
snapshot transacional do volume; mudanças detectadas abortam o inventário.
"""
from __future__ import annotations

from sermax_windows_directory_handle import (
    enumerate_stable_directory_handle,
    open_verified_child_component,
)
from sermax_windows_directory_snapshot import (
    DirectorySnapshotError,
    compare_directory_snapshots,
)
from sermax_windows_file_hash import hash_file_component
from sermax_windows_handle_io import (
    HandleIoError,
    close_handle,
    query_handle_metadata,
)

MAX_DEPTH = 128
MAX_ENTRIES = 100_000
FILE_ATTRIBUTE_DEVICE = 0x00000040


def inventory_directory_handle(
    root_handle,
    *,
    max_depth: int = MAX_DEPTH,
    max_entries: int = MAX_ENTRIES,
    chunk_size: int | None = None,
) -> list[dict[str, object]]:
    """Produz inventário SHA-256 sob um handle raiz já validado.

    Requer handle de diretório aberto e mantido pelo chamador. Reparse points
    são listados como blocked e nunca percorridos. Arquivos são abertos e
    validados pelo FileId de 128 bits enumerado antes do hash. Cada diretório
    é enumerado novamente após processar seus filhos. Qualquer divergência
    aborta o inventário completo.
    """
    for name, value, minimum, maximum in (
        ("max_depth", max_depth, 0, MAX_DEPTH),
        ("max_entries", max_entries, 1, MAX_ENTRIES),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise HandleIoError(f"{name} deve ser inteiro.")
        if not minimum <= value <= maximum:
            raise HandleIoError(f"{name} fora dos limites permitidos.")
    if chunk_size is not None and (
        isinstance(chunk_size, bool) or not isinstance(chunk_size, int)
    ):
        raise HandleIoError("chunk_size deve ser inteiro ou None.")

    root_metadata = query_handle_metadata(root_handle)
    if (
        not root_metadata["is_directory"]
        or root_metadata["is_reparse_point"]
        or root_metadata["delete_pending"]
    ):
        raise HandleIoError("A raiz exige handle de diretório regular validado.")

    records: list[dict[str, object]] = []

    def walk(directory_handle, relative_parent: str, depth: int) -> None:
        if depth > max_depth:
            raise HandleIoError("Profundidade máxima da árvore excedida.")

        initial = enumerate_stable_directory_handle(directory_handle)
        for entry in initial:
            relative = f"{relative_parent}/{entry.name}" if relative_parent else entry.name
            if len(records) >= max_entries:
                raise HandleIoError("Limite máximo de registros excedido.")

            if entry.is_reparse_point:
                records.append({
                    "path": relative,
                    "type": "reparse",
                    "size": None,
                    "sha256": None,
                    "file_id": entry.file_id,
                    "classification": "blocked",
                })
                continue

            if entry.is_directory:
                child = open_verified_child_component(directory_handle, entry)
                try:
                    records.append({
                        "path": relative,
                        "type": "directory",
                        "size": None,
                        "sha256": None,
                        "file_id": entry.file_id,
                        "classification": "unknown",
                    })
                    walk(child, relative, depth + 1)
                finally:
                    close_handle(child)
                continue

            if entry.attributes & FILE_ATTRIBUTE_DEVICE:
                records.append({
                    "path": relative,
                    "type": "special",
                    "size": None,
                    "sha256": None,
                    "file_id": entry.file_id,
                    "classification": "blocked",
                })
                continue

            if chunk_size is None:
                digest, size = hash_file_component(directory_handle, entry)
            else:
                digest, size = hash_file_component(
                    directory_handle, entry, chunk_size=chunk_size
                )
            records.append({
                "path": relative,
                "type": "file",
                "size": size,
                "sha256": digest,
                "file_id": entry.file_id,
                "classification": "unknown",
            })

        final = enumerate_stable_directory_handle(directory_handle)
        try:
            compare_directory_snapshots(initial, final)
        except DirectorySnapshotError as exc:
            raise HandleIoError(
                f"Diretório mudou durante o inventário: {relative_parent or '<raiz>'}: {exc}"
            ) from exc

    walk(root_handle, "", 0)
    return records
