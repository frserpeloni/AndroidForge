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
FILE_ADD_SUBDIRECTORY = 0x00000004
FILE_SHARE_READ = 0x00000001
READ_CONTROL = 0x00020000

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
    desired_access = (
        FILE_LIST_DIRECTORY
        | FILE_ADD_SUBDIRECTORY
        | FILE_READ_ATTRIBUTES
        | SYNCHRONIZE
    )
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



def validate_existing_private_area(
    parent_handle, *, expected_owner_sid: str | None = None
) -> dict:
    """Valida _update preexistente por handle e Authz, sem reparar divergências.

    O SID esperado é derivado do token real do processo. Se o chamador ainda
    informar expected_owner_sid por compatibilidade, ele precisa coincidir.
    O mesmo handle do diretório permanece aberto durante inspeção e Authz.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise PrivateAreaError("A validação exige Windows x64.")

    from sermax_windows_directory_handle import (
        enumerate_stable_directory_handle,
        open_verified_child_component,
    )
    from sermax_windows_acl_inspection import inspect_directory_acl
    from sermax_windows_private_area_acl_policy import (
        validate_private_area_acl,
        FILE_ALL_ACCESS,
    )
    from sermax_windows_effective_access import (
        _cleanup_resource,
        evaluate_access_for_token,
        read_security_descriptor_binary,
    )
    import win32api
    import win32security

    child_handle = None
    token = None
    try:
        parent = query_handle_metadata(parent_handle)
        if (
            not parent["is_directory"]
            or parent["is_reparse_point"]
            or parent["delete_pending"]
        ):
            raise PrivateAreaError("O handle pai não é diretório regular validado.")

        entries = enumerate_stable_directory_handle(parent_handle)
        matches = [entry for entry in entries if entry.name.casefold() == "_update"]
        if len(matches) != 1:
            raise PrivateAreaError(
                "_update ausente ou ambíguo; nenhuma criação ou reparo foi tentado."
            )
        entry = matches[0]
        if not entry.is_directory:
            raise PrivateAreaError("_update existente não é diretório.")

        child_handle = open_verified_child_component(
            parent_handle, entry, desired_access=READ_CONTROL
        )
        metadata = query_handle_metadata(child_handle)
        if (
            not metadata["is_directory"]
            or metadata["is_reparse_point"]
            or metadata["delete_pending"]
        ):
            raise PrivateAreaError("_update não é diretório regular.")

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
        )
        token_user = win32security.GetTokenInformation(
            token, win32security.TokenUser
        )[0]
        actual_owner_sid = win32security.ConvertSidToStringSid(token_user)
        if expected_owner_sid is not None and expected_owner_sid != actual_owner_sid:
            raise PrivateAreaError(
                "SID informado pelo chamador diverge do SID do token real."
            )

        inspection = inspect_directory_acl(child_handle)
        contents = [
            item
            for item in enumerate_stable_directory_handle(child_handle)
            if item.name not in {".", ".."}
        ]
        policy = validate_private_area_acl(
            inspection,
            expected_owner_sid=actual_owner_sid,
            expected_volume_serial=parent["volume_serial_number"],
            expected_file_id_128=entry.file_id,
            directory_identity={
                "volume_serial_number": metadata["volume_serial_number"],
                "file_id_128": metadata["file_id_128"],
            },
            directory_entries=contents,
        )

        descriptor = read_security_descriptor_binary(child_handle)
        access = evaluate_access_for_token(token, descriptor, FILE_ALL_ACCESS)
        if (
            access.get("api") != "AuthzAccessCheck"
            or access.get("api_success") is not True
            or access.get("granted") is not True
            or access.get("desired_access") != FILE_ALL_ACCESS
            or access.get("token_source") != "real_kernel_token"
            or access.get("security_descriptor_source") != "GetSecurityInfo_same_handle"
            or access.get("mutated") is not False
            or access.get("performed_io") is not False
        ):
            raise PrivateAreaError(
                "Authz não concedeu integralmente FILE_ALL_ACCESS ao token real."
            )

        report = dict(policy)
        report.update({
            "effective_access_evaluated": True,
            "effective_access": access,
            "owner_sid": actual_owner_sid,
            "mutated": False,
        })
        return report
    except PrivateAreaError:
        raise
    except Exception as exc:
        raise PrivateAreaError(
            f"_update preexistente não passou na validação somente leitura: {exc}"
        ) from exc
    finally:
        try:
            if token is not None:
                _cleanup_resource(
                    "CloseHandle falhou ao liberar token de validação",
                    lambda handle: (win32api.CloseHandle(handle) is None),
                    token,
                )
        finally:
            if child_handle is not None:
                _cleanup_resource(
                    "CloseHandle falhou ao liberar handle de _update",
                    lambda handle: (close_handle(handle) is None),
                    child_handle,
                )
