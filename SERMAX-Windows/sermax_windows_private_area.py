"""Criação exclusiva de diretórios internos por handle no Windows.

Esta camada cria um único componente relativo a um diretório pai validado.
Não cria caminhos recursivos, não altera ACL e não autoriza instalação.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from sermax_windows_handle_io import (
    FILE_READ_ATTRIBUTES,
    SYNCHRONIZE,
    HandleIoError,
    _native_api,
    _validate_component,
    close_handle,
    query_handle_metadata,
)

FILE_CREATE = 0x00000002
FILE_DIRECTORY_FILE = 0x00000001
FILE_OPEN_REPARSE_POINT = 0x00200000
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_LIST_DIRECTORY = 0x00000001
FILE_SHARE_READ = 0x00000001

ALLOWED_PRIVATE_COMPONENTS = frozenset({
    "_update", "staging", "backups", "journal", "logs", "locks",
})


class PrivateAreaError(RuntimeError):
    """Falha fechada ao criar ou validar um diretório interno."""


def create_private_directory_component(parent_handle, component: str):
    """Cria um diretório filho com semântica exclusiva, relativo ao handle pai.

    O pai deve permanecer aberto durante a operação e ter sido aberto com
    FILE_ADD_SUBDIRECTORY (0x00000004), além dos direitos de leitura de
    diretório/metadados exigidos pelo chamador. O componente precisa pertencer
    à lista fixa de nomes internos. A função falha se o nome já
    existir, se o pai não for diretório regular ou se a identidade do volume
    divergir. O handle retornado pertence ao chamador.

    Esta função não cria ACL restritiva. O chamador ainda precisa executar
    provisionamento e validação de ACL antes de armazenar qualquer dado.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise PrivateAreaError("A criação exige Windows x64.")
    try:
        _validate_component(component)
    except Exception as exc:
        raise PrivateAreaError(f"Componente inválido: {exc}") from exc
    if component not in ALLOWED_PRIVATE_COMPONENTS:
        raise PrivateAreaError("Componente fora da lista privada permitida.")

    try:
        parent = query_handle_metadata(parent_handle)
    except Exception as exc:
        raise PrivateAreaError(f"Não foi possível validar o diretório pai: {exc}") from exc
    if (
        not parent["is_directory"]
        or parent["is_reparse_point"]
        or parent["delete_pending"]
    ):
        raise PrivateAreaError("O handle pai não é um diretório regular validado.")

    create, _, _ = _native_api()
    name_buffer = ctypes.create_unicode_buffer(component)
    encoded_length = len(component.encode("utf-16-le"))

    from sermax_windows_handle_abi import (
        IO_STATUS_BLOCK,
        OBJECT_ATTRIBUTES,
        OBJ_CASE_INSENSITIVE,
        UNICODE_STRING,
    )

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
    desired_access = FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | SYNCHRONIZE
    options = (
        FILE_DIRECTORY_FILE
        | FILE_OPEN_REPARSE_POINT
        | FILE_SYNCHRONOUS_IO_NONALERT
    )

    status = create(
        ctypes.byref(result_handle),
        desired_access,
        ctypes.byref(attributes),
        ctypes.byref(io_status),
        None,
        FILE_ATTRIBUTE_DIRECTORY,
        FILE_SHARE_READ,
        FILE_CREATE,
        options,
        None,
        0,
    )
    if status < 0:
        raise PrivateAreaError(
            "NtCreateFile não criou o componente exclusivamente, "
            f"NTSTATUS=0x{status & 0xffffffff:08X}"
        )

    child_handle = result_handle
    try:
        child = query_handle_metadata(child_handle)
        if (
            not child["is_directory"]
            or child["is_reparse_point"]
            or child["delete_pending"]
        ):
            raise PrivateAreaError("O objeto criado não é diretório regular.")
        if child["volume_serial_number"] != parent["volume_serial_number"]:
            raise PrivateAreaError("O diretório criado está em volume divergente.")
        if not child["file_id_128"] or len(child["file_id_128"]) != 32:
            raise PrivateAreaError("O diretório criado não forneceu FileId de 128 bits.")
        return child_handle
    except Exception:
        try:
            close_handle(child_handle)
        except Exception as close_error:
            raise PrivateAreaError(
                f"Falha na validação e também ao fechar o handle: {close_error}"
            ) from close_error
        raise
