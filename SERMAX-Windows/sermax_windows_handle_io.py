"""Operações iniciais de I/O por handle, isoladas para Windows x64.

Abre um único componente relativamente a um handle de diretório já validado.
Não resolve a raiz, não enumera diretórios e não lê conteúdo.
"""
from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes

from sermax_windows_handle_abi import (
    FILE_DIRECTORY_FILE,
    FILE_NON_DIRECTORY_FILE,
    FILE_OPEN,
    FILE_OPEN_REPARSE_POINT,
    FILE_SHARE_READ,
    FILE_SYNCHRONOUS_IO_NONALERT,
    OBJ_CASE_INSENSITIVE,
    OBJECT_ATTRIBUTES,
    UNICODE_STRING,
    IO_STATUS_BLOCK,
    NativeApiError,
)

FILE_READ_ATTRIBUTES = 0x0080
SYNCHRONIZE = 0x00100000
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
FILE_STANDARD_INFO_CLASS = 1
_NAME_RESERVED = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?$",
    re.IGNORECASE,
)


class HandleIoError(RuntimeError):
    """Falha fechada em operação de I/O por handle."""


class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
    _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]


class FILE_STANDARD_INFO(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", ctypes.c_longlong),
        ("EndOfFile", ctypes.c_longlong),
        ("NumberOfLinks", wintypes.DWORD),
        ("DeletePending", wintypes.BOOLEAN),
        ("Directory", wintypes.BOOLEAN),
    ]


def _validate_component(name: str) -> None:
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise HandleIoError("É exigido um único nome de componente.")
    if any(ch in name for ch in ("\\", "/", ":", "\x00")):
        raise HandleIoError("Separadores, ADS e NUL não são aceitos.")
    if name.endswith((" ", ".")) or _NAME_RESERVED.fullmatch(name):
        raise HandleIoError("Nome incompatível com as regras do Windows.")
    if any(ord(ch) < 32 for ch in name):
        raise HandleIoError("Caractere de controle no nome.")


def _native_api():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise NativeApiError("A camada de handles exige Windows x64.")
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = ntdll.NtCreateFile
    create.argtypes = [
        ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
        ctypes.POINTER(OBJECT_ATTRIBUTES), ctypes.POINTER(IO_STATUS_BLOCK),
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
    ]
    create.restype = ctypes.c_long
    query = kernel32.GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    query.restype = wintypes.BOOL
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    return create, query, close


def open_relative_component(parent_handle, name: str, *, directory: bool = False):
    """Abre um componente sob parent_handle sem seguir reparse point.

    O chamador deve manter parent_handle aberto e validado como diretório.
    O handle retornado pertence ao chamador e deve ser fechado por ele.
    """
    _validate_component(name)
    create, _, _ = _native_api()

    name_buffer = ctypes.create_unicode_buffer(name)
    encoded_length = len(name.encode("utf-16-le"))
    unicode_name = UNICODE_STRING(
        Length=encoded_length,
        MaximumLength=encoded_length + 2,
        Buffer=ctypes.cast(name_buffer, wintypes.LPWSTR),
    )
    attributes = OBJECT_ATTRIBUTES()
    attributes.Length = ctypes.sizeof(OBJECT_ATTRIBUTES)
    attributes.RootDirectory = parent_handle
    attributes.ObjectName = ctypes.pointer(unicode_name)
    attributes.Attributes = OBJ_CASE_INSENSITIVE

    result_handle = wintypes.HANDLE()
    io_status = IO_STATUS_BLOCK()
    options = FILE_OPEN_REPARSE_POINT | FILE_SYNCHRONOUS_IO_NONALERT
    options |= FILE_DIRECTORY_FILE if directory else FILE_NON_DIRECTORY_FILE

    status = create(
        ctypes.byref(result_handle),
        FILE_READ_ATTRIBUTES | SYNCHRONIZE,
        ctypes.byref(attributes),
        ctypes.byref(io_status),
        None,
        0,
        FILE_SHARE_READ,
        FILE_OPEN,
        options,
        None,
        0,
    )
    if status < 0:
        raise HandleIoError(f"NtCreateFile falhou, NTSTATUS=0x{status & 0xffffffff:08X}")
    return result_handle


def query_handle_metadata(handle) -> dict[str, int | bool]:
    """Consulta atributos, reparse tag e metadados pelo handle aberto."""
    _, query, _ = _native_api()
    tag = FILE_ATTRIBUTE_TAG_INFO()
    standard = FILE_STANDARD_INFO()
    if not query(handle, FILE_ATTRIBUTE_TAG_INFO_CLASS, ctypes.byref(tag), ctypes.sizeof(tag)):
        error = ctypes.get_last_error()
        raise HandleIoError(f"FileAttributeTagInfo falhou, WinError={error}")
    if not query(handle, FILE_STANDARD_INFO_CLASS, ctypes.byref(standard), ctypes.sizeof(standard)):
        error = ctypes.get_last_error()
        raise HandleIoError(f"FileStandardInfo falhou, WinError={error}")
    return {
        "attributes": int(tag.FileAttributes),
        "reparse_tag": int(tag.ReparseTag),
        "is_directory": bool(standard.Directory),
        "is_reparse_point": bool(tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT),
        "end_of_file": int(standard.EndOfFile),
        "number_of_links": int(standard.NumberOfLinks),
        "delete_pending": bool(standard.DeletePending),
    }


def close_handle(handle) -> None:
    """Fecha handle nativo. Falha explicitamente se CloseHandle falhar."""
    _, _, close = _native_api()
    if not close(handle):
        error = ctypes.get_last_error()
        raise HandleIoError(f"CloseHandle falhou, WinError={error}")
