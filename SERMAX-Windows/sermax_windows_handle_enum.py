"""Enumeração de diretórios por handle para Windows x64.

A enumeração não abre entradas nem lê conteúdo. Cada nome retornado é candidato
e deve ser aberto relativamente ao handle pai antes de qualquer confiança.
"""
from __future__ import annotations

import ctypes
import os
import struct
from ctypes import wintypes

FILE_ID_BOTH_DIRECTORY_INFO_CLASS = 10
FILE_ID_BOTH_DIRECTORY_RESTART_INFO_CLASS = 11
ERROR_NO_MORE_FILES = 18
ERROR_MORE_DATA = 234
DEFAULT_BUFFER_SIZE = 64 * 1024
MAX_BUFFER_SIZE = 4 * 1024 * 1024
MAX_ENTRIES = 1_000_000

# FILE_ID_BOTH_DIR_INFO offsets from the Windows SDK layout.
_NEXT_ENTRY_OFFSET = 0
_FILE_ATTRIBUTES_OFFSET = 56
_FILE_NAME_LENGTH_OFFSET = 60
_FILE_ID_OFFSET = 96
_FILE_NAME_OFFSET = 104


class DirectoryEnumerationError(RuntimeError):
    """Enumeração incompleta ou buffer inconsistente."""


def _parse_directory_buffer(buffer: bytes | bytearray | memoryview) -> list[dict[str, object]]:
    """Valida e decodifica as entradas presentes em um buffer nativo."""
    view = memoryview(buffer)
    capacity = len(view)
    entries: list[dict[str, object]] = []
    offset = 0

    while True:
        if offset < 0 or offset + _FILE_NAME_OFFSET > capacity:
            raise DirectoryEnumerationError("Cabeçalho de entrada fora do buffer.")

        next_offset = struct.unpack_from("<I", view, offset + _NEXT_ENTRY_OFFSET)[0]
        attributes = struct.unpack_from("<I", view, offset + _FILE_ATTRIBUTES_OFFSET)[0]
        name_length = struct.unpack_from("<I", view, offset + _FILE_NAME_LENGTH_OFFSET)[0]
        file_id = struct.unpack_from("<Q", view, offset + _FILE_ID_OFFSET)[0]

        if name_length % 2:
            raise DirectoryEnumerationError("FileNameLength não é múltiplo de UTF-16.")
        name_end = offset + _FILE_NAME_OFFSET + name_length
        if name_end > capacity:
            raise DirectoryEnumerationError("Nome excede o buffer retornado.")

        try:
            name = bytes(view[offset + _FILE_NAME_OFFSET:name_end]).decode("utf-16-le", errors="strict")
        except UnicodeDecodeError as exc:
            raise DirectoryEnumerationError("Nome contém UTF-16 inválido.") from exc

        if not name or "\\x00" in name or "/" in name or "\\\\" in name:
            raise DirectoryEnumerationError("Nome de entrada inválido.")
        if name not in {".", ".."}:
            entries.append({
                "name": name,
                "attributes": attributes,
                "file_id_64": file_id,
            })
            if len(entries) > MAX_ENTRIES:
                raise DirectoryEnumerationError("Limite de entradas excedido.")

        if next_offset == 0:
            break
        if next_offset < _FILE_NAME_OFFSET + name_length or next_offset % 8:
            raise DirectoryEnumerationError("NextEntryOffset inválido ou desalinhado.")
        if offset + next_offset <= offset or offset + next_offset + _FILE_NAME_OFFSET > capacity:
            raise DirectoryEnumerationError("NextEntryOffset aponta fora do buffer.")
        offset += next_offset

    return entries


def enumerate_directory_handle(handle, *, buffer_size: int = DEFAULT_BUFFER_SIZE) -> list[dict[str, object]]:
    """Enumera um diretório já aberto. Não segue nomes nem abre filhos.

    Usa RestartInfo na primeira chamada e Info nas seguintes. Qualquer erro
    diferente de ERROR_NO_MORE_FILES aborta, sem fallback por caminho.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise DirectoryEnumerationError("Enumeração exige Windows x64.")
    if not isinstance(buffer_size, int) or buffer_size < 4096 or buffer_size > MAX_BUFFER_SIZE:
        raise DirectoryEnumerationError("Tamanho de buffer fora dos limites.")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel32.GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    query.restype = wintypes.BOOL

    # Reserva margem e alinha o endereço efetivamente passado em 8 bytes.
    raw = ctypes.create_string_buffer(buffer_size + 7)
    base = ctypes.addressof(raw)
    aligned = (base + 7) & ~7
    result: list[dict[str, object]] = []
    info_class = FILE_ID_BOTH_DIRECTORY_RESTART_INFO_CLASS

    while True:
        ctypes.memset(aligned, 0, buffer_size)
        ok = query(handle, info_class, ctypes.c_void_p(aligned), buffer_size)
        info_class = FILE_ID_BOTH_DIRECTORY_INFO_CLASS
        if not ok:
            error = ctypes.get_last_error()
            if error == ERROR_NO_MORE_FILES:
                return result
            if error == ERROR_MORE_DATA:
                raise DirectoryEnumerationError(
                    "Buffer insuficiente; enumeração interrompida sem reiniciar por caminho."
                )
            raise DirectoryEnumerationError(
                f"GetFileInformationByHandleEx falhou, WinError={error}"
            )

        batch = _parse_directory_buffer(
            ctypes.string_at(aligned, buffer_size)
        )
        result.extend(batch)
        if len(result) > MAX_ENTRIES:
            raise DirectoryEnumerationError("Limite total de entradas excedido.")
