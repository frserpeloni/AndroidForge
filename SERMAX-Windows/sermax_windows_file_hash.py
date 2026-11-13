"""Leitura e SHA-256 de arquivos por handle nativo, Windows x64.

O arquivo é aberto relativamente ao handle do diretório pai. O modo de
compartilhamento da abertura existente permite leitura concorrente, mas
recusa handles incompatíveis com escrita/exclusão enquanto este handle vive.
Hardlinks são rejeitados por política conservadora.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes

from sermax_windows_directory_enum import DirectoryEntry
from sermax_windows_directory_handle import open_verified_child_component
from sermax_windows_handle_io import (
    HandleIoError,
    close_handle,
    query_handle_metadata,
)

FILE_READ_DATA = 0x0001
DEFAULT_CHUNK_SIZE = 1024 * 1024
MAX_CHUNK_SIZE = 16 * 1024 * 1024


def _read_file_api():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise HandleIoError("Leitura por handle exige Windows x64.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    read_file = kernel32.ReadFile
    read_file.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    read_file.restype = wintypes.BOOL
    return read_file


def _identity(metadata: dict[str, object]) -> tuple[object, ...]:
    return (
        metadata["volume_serial_number"],
        metadata["file_id_128"],
        metadata["end_of_file"],
        metadata["number_of_links"],
        metadata["attributes"],
        metadata["is_directory"],
        metadata["is_reparse_point"],
        metadata["delete_pending"],
    )


def _validate_regular_single_link(metadata: dict[str, object]) -> None:
    if metadata["is_directory"]:
        raise HandleIoError("A leitura exige arquivo regular, não diretório.")
    if metadata["is_reparse_point"]:
        raise HandleIoError("Arquivo reparse rejeitado.")
    if metadata["delete_pending"]:
        raise HandleIoError("Arquivo marcado para exclusão.")
    if int(metadata["number_of_links"]) != 1:
        raise HandleIoError("Arquivo com hardlinks rejeitado pela política conservadora.")
    if int(metadata["end_of_file"]) < 0:
        raise HandleIoError("Tamanho de arquivo inválido.")


def _hash_handle(handle, *, chunk_size: int = DEFAULT_CHUNK_SIZE,
                 read_file=None) -> tuple[str, int]:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise HandleIoError("chunk_size deve ser inteiro.")
    if chunk_size < 4096 or chunk_size > MAX_CHUNK_SIZE:
        raise HandleIoError("chunk_size fora dos limites permitidos.")

    before = query_handle_metadata(handle)
    _validate_regular_single_link(before)
    expected_size = int(before["end_of_file"])
    before_identity = _identity(before)
    reader = read_file or _read_file_api()

    digest = hashlib.sha256()
    total = 0
    buffer = ctypes.create_string_buffer(chunk_size)
    bytes_read = wintypes.DWORD()

    while True:
        bytes_read.value = 0
        ok = reader(
            handle,
            ctypes.byref(buffer),
            chunk_size,
            ctypes.byref(bytes_read),
            None,
        )
        if not ok:
            error = ctypes.get_last_error()
            raise HandleIoError(f"ReadFile falhou, WinError={error}")
        count = int(bytes_read.value)
        if count == 0:
            break
        if count > chunk_size:
            raise HandleIoError("ReadFile retornou quantidade acima do buffer.")
        total += count
        if total > expected_size:
            raise HandleIoError("Arquivo cresceu durante a leitura.")
        digest.update(buffer.raw[:count])

    after = query_handle_metadata(handle)
    _validate_regular_single_link(after)
    if _identity(after) != before_identity:
        raise HandleIoError("Identidade ou metadados mudaram durante a leitura.")
    if total != expected_size:
        raise HandleIoError(
            f"Leitura incompleta ou tamanho divergente: esperado={expected_size}, lido={total}."
        )
    return digest.hexdigest(), total


def hash_file_component(parent_handle, entry: DirectoryEntry, *,
                        chunk_size: int = DEFAULT_CHUNK_SIZE) -> tuple[str, int]:
    """Abre o arquivo enumerado, valida seu FileId e calcula SHA-256.

    A abertura é relativa ao handle pai. O FileId de 128 bits, o volume,
    os atributos e o tamanho precisam corresponder à entrada enumerada antes
    da leitura. O handle é fechado mesmo quando a validação ou leitura falha.
    """
    if not isinstance(entry, DirectoryEntry) or entry.is_directory:
        raise HandleIoError("hash_file_component exige uma entrada de arquivo.")
    handle = open_verified_child_component(
        parent_handle,
        entry,
        desired_access=FILE_READ_DATA,
    )
    try:
        return _hash_handle(handle, chunk_size=chunk_size)
    finally:
        close_handle(handle)
