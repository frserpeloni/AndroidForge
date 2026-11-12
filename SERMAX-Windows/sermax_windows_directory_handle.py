"""Enumeração nativa isolada de diretório por handle, Windows x64.

A função não modifica o filesystem. Cada chamada inicia uma enumeração nova.
A API do Windows não fornece snapshot transacional; o chamador deve repetir
a enumeração e comparar resultados antes de confiar no namespace.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from sermax_windows_directory_enum import (
    DirectoryBufferError,
    DirectoryEntry,
    parse_file_id_both_dir_info,
)
from sermax_windows_handle_io import (
    HandleIoError,
    _native_api,
    query_handle_metadata,
)

FILE_ID_BOTH_DIRECTORY_INFO_CLASS = 10
FILE_ID_BOTH_DIRECTORY_RESTART_INFO_CLASS = 11
ERROR_NO_MORE_FILES = 18
ERROR_MORE_DATA = 234
DEFAULT_BUFFER_SIZE = 64 * 1024
MAX_BATCHES = 1_000_000
MAX_ENTRIES = 10_000_000


def enumerate_directory_handle(
    handle,
    *,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> tuple[DirectoryEntry, ...]:
    """Enumera um diretório já aberto, sempre reiniciando a consulta.

    Falha fechada para handle não diretório, reparse point, erros Win32,
    buffer inválido, falta de progresso e limites excessivos.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise HandleIoError("Enumeração nativa exige Windows x64.")
    if isinstance(buffer_size, bool) or not isinstance(buffer_size, int):
        raise HandleIoError("buffer_size deve ser inteiro.")
    if buffer_size < 4096 or buffer_size > 1024 * 1024 or buffer_size % 8:
        raise HandleIoError("buffer_size fora dos limites ou desalinhado.")

    metadata = query_handle_metadata(handle)
    if not metadata["is_directory"] or metadata["is_reparse_point"]:
        raise HandleIoError("Enumeração exige diretório regular, sem reparse point.")
    if metadata["delete_pending"]:
        raise HandleIoError("Diretório marcado para exclusão.")

    _, query, _ = _native_api()
    buffer = ctypes.create_string_buffer(buffer_size)
    results: list[DirectoryEntry] = []
    seen_names: set[str] = set()

    info_class = FILE_ID_BOTH_DIRECTORY_RESTART_INFO_CLASS
    for _ in range(MAX_BATCHES):
        ctypes.memset(buffer, 0, buffer_size)
        ok = query(handle, info_class, ctypes.byref(buffer), buffer_size)
        if not ok:
            error = ctypes.get_last_error()
            if error == ERROR_NO_MORE_FILES:
                return tuple(results)
            if error == ERROR_MORE_DATA:
                raise HandleIoError("Buffer insuficiente durante enumeração.")
            raise HandleIoError(f"GetFileInformationByHandleEx falhou, WinError={error}")

        try:
            batch = parse_file_id_both_dir_info(buffer.raw)
        except DirectoryBufferError as exc:
            raise HandleIoError(f"Buffer de enumeração inválido: {exc}") from exc
        if not batch:
            raise HandleIoError("Enumeração retornou lote vazio sem término.")
        for entry in batch:
            # A enumeração pode expor nomes duplicados em volumes ou cenários
            # inconsistentes. Não escolher silenciosamente uma das entradas.
            folded = entry.name.casefold()
            if folded in seen_names:
                raise HandleIoError("Nome duplicado na enumeração do diretório.")
            seen_names.add(folded)
            results.append(entry)
            if len(results) > MAX_ENTRIES:
                raise HandleIoError("Limite máximo de entradas excedido.")

        info_class = FILE_ID_BOTH_DIRECTORY_INFO_CLASS

    raise HandleIoError("Limite de lotes excedido; enumeração abortada.")
