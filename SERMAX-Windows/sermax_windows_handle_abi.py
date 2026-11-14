"""Declarações ABI isoladas para a futura leitura segura por handles no Windows.

Este módulo não abre arquivos nem altera a instalação. As funções nativas só são
carregadas explicitamente por load_native_apis(), em Windows x64.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

# NTSTATUS e tipos base da Native API.
NTSTATUS = ctypes.c_long
ACCESS_MASK = wintypes.DWORD
ULONG = wintypes.ULONG
HANDLE = wintypes.HANDLE
PVOID = ctypes.c_void_p
ULONG_PTR = ctypes.c_size_t
LARGE_INTEGER = ctypes.c_longlong


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]


PUNICODE_STRING = ctypes.POINTER(UNICODE_STRING)


class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Length", ULONG),
        ("RootDirectory", HANDLE),
        ("ObjectName", PUNICODE_STRING),
        ("Attributes", ULONG),
        ("SecurityDescriptor", PVOID),
        ("SecurityQualityOfService", PVOID),
    ]


POBJECT_ATTRIBUTES = ctypes.POINTER(OBJECT_ATTRIBUTES)


class _IO_STATUS_BLOCK_UNION(ctypes.Union):
    _fields_ = [
        ("Status", NTSTATUS),
        ("Pointer", PVOID),
    ]


class IO_STATUS_BLOCK(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("u", _IO_STATUS_BLOCK_UNION),
        ("Information", ULONG_PTR),
    ]


PIO_STATUS_BLOCK = ctypes.POINTER(IO_STATUS_BLOCK)


class FILE_ID_128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_ubyte * 16)]


class FILE_ID_INFO(ctypes.Structure):
    _fields_ = [
        ("VolumeSerialNumber", ctypes.c_ulonglong),
        ("FileId", FILE_ID_128),
    ]


class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
    _fields_ = [
        ("FileAttributes", ULONG),
        ("ReparseTag", ULONG),
    ]


class FILE_STANDARD_INFO(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", LARGE_INTEGER),
        ("EndOfFile", LARGE_INTEGER),
        ("NumberOfLinks", ULONG),
        ("DeletePending", wintypes.BOOLEAN),
        ("Directory", wintypes.BOOLEAN),
    ]


# OBJECT_ATTRIBUTES.Attributes
OBJ_CASE_INSENSITIVE = 0x00000040

# NtCreateFile CreateDisposition / CreateOptions.
FILE_OPEN = 0x00000001
FILE_DIRECTORY_FILE = 0x00000001
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_OPEN_REPARSE_POINT = 0x00200000

# Share mode inicial conservador. A política final ainda depende dos testes.
FILE_SHARE_READ = 0x00000001

# FILE_INFO_BY_HANDLE_CLASS, conforme Win32.
FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
FILE_ID_BOTH_DIRECTORY_INFO_CLASS = 10
FILE_ID_INFO_CLASS = 18
FILE_ID_EXTD_DIRECTORY_INFO_CLASS = 19
FILE_STANDARD_INFO_CLASS = 1


class NativeApiError(RuntimeError):
    """A plataforma ou a carga das APIs nativas não atende ao contrato."""


def load_native_apis():
    """Carrega as APIs sem executá-las. Exige Windows x64."""
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise NativeApiError("A camada de handles exige Windows x64.")

    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    nt_create_file = ntdll.NtCreateFile
    nt_create_file.argtypes = [
        ctypes.POINTER(HANDLE),
        ACCESS_MASK,
        POBJECT_ATTRIBUTES,
        PIO_STATUS_BLOCK,
        ctypes.POINTER(LARGE_INTEGER),
        ULONG,
        ULONG,
        ULONG,
        ULONG,
        PVOID,
        ULONG,
    ]
    nt_create_file.restype = NTSTATUS

    get_file_information_by_handle_ex = kernel32.GetFileInformationByHandleEx
    get_file_information_by_handle_ex.argtypes = [
        HANDLE,
        ctypes.c_int,
        PVOID,
        ULONG,
    ]
    get_file_information_by_handle_ex.restype = wintypes.BOOL

    return nt_create_file, get_file_information_by_handle_ex
