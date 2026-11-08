"""Abertura validada da raiz de uma unidade local no Windows x64.

Aceita somente o formato exato X:\. Não altera arquivos.
"""
from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes

from sermax_windows_handle_io import close_handle, query_handle_metadata

FILE_READ_ATTRIBUTES = 0x0080
FILE_LIST_DIRECTORY = 0x0001
SYNCHRONIZE = 0x00100000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_DRIVE_ROOT = re.compile(r"^[A-Za-z]:\\$")


class RootOpenError(RuntimeError):
    """A raiz solicitada não pôde ser aberta e validada."""


def _validate_drive_root(path: str) -> str:
    if not isinstance(path, str) or not _DRIVE_ROOT.fullmatch(path):
        raise RootOpenError("Informe a raiz local no formato X:\\.")
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RootOpenError("A abertura da raiz exige Windows x64.")
    return path


def open_drive_root(path: str):
    """Abre X:\ como diretório e valida o objeto pelo handle retornado.

    O chamador passa a ser responsável por fechar o handle com close_handle().
    A abertura compartilha leitura, escrita e exclusão para não impor bloqueio
    global à raiz do volume. A validação de reparse point ocorre no handle.
    """
    path = _validate_drive_root(path)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE

    handle = create_file(
        path,
        FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY | SYNCHRONIZE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        raise RootOpenError(f"CreateFileW falhou para a raiz, WinError={error}")

    try:
        metadata = query_handle_metadata(handle)
        if not metadata["is_directory"]:
            raise RootOpenError("O objeto aberto não é um diretório.")
        if metadata["is_reparse_point"]:
            raise RootOpenError("A raiz aberta é um reparse point e foi rejeitada.")
        if metadata["delete_pending"]:
            raise RootOpenError("A raiz está marcada para exclusão.")
        return handle
    except Exception:
        try:
            close_handle(handle)
        except Exception as close_error:
            raise RootOpenError(
                f"Falha ao validar a raiz e também ao fechar o handle: {close_error}"
            ) from close_error
        raise
