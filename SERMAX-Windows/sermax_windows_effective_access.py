"""Avaliação de acesso efetivo por token real usando a API Authz do Windows.

A avaliação usa o descritor de segurança obtido do objeto-alvo e um token
aberto com TOKEN_QUERY. Não altera ACLs nem executa operações no objeto.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class EffectiveAccessError(RuntimeError):
    """Falha fechada ao avaliar acesso efetivo no Windows."""


ERROR_SUCCESS = 0
GENERIC_ACCESS_BITS = 0xF0000000
SE_FILE_OBJECT = 1
OWNER_SECURITY_INFORMATION = 0x00000001
GROUP_SECURITY_INFORMATION = 0x00000002
DACL_SECURITY_INFORMATION = 0x00000004
MAX_SECURITY_DESCRIPTOR_SIZE = 1024 * 1024


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class AUTHZ_ACCESS_REQUEST(ctypes.Structure):
    _fields_ = [
        ("DesiredAccess", wintypes.DWORD),
        ("PrincipalSelfSid", ctypes.c_void_p),
        ("ObjectTypeList", ctypes.c_void_p),
        ("ObjectTypeListLength", wintypes.DWORD),
        ("OptionalArguments", ctypes.c_void_p),
    ]


class AUTHZ_ACCESS_REPLY(ctypes.Structure):
    _fields_ = [
        ("ResultListLength", wintypes.DWORD),
        ("GrantedAccessMask", ctypes.POINTER(wintypes.DWORD)),
        ("SaclEvaluationResults", ctypes.POINTER(wintypes.DWORD)),
        ("Error", ctypes.POINTER(wintypes.DWORD)),
    ]


def _require_windows_x64() -> None:
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise EffectiveAccessError("A avaliação exige Windows x64.")


def _native_handle_value(handle) -> int:
    value = handle.value if isinstance(handle, ctypes.c_void_p) else handle
    if value is None:
        raise EffectiveAccessError("Handle nulo.")
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EffectiveAccessError("Handle inválido.") from exc
    if value == 0 or value == ctypes.c_void_p(-1).value:
        raise EffectiveAccessError("Handle inválido.")
    return value


def read_security_descriptor_binary(directory_handle) -> bytes:
    """Lê OWNER, GROUP e DACL pelo handle já aberto com READ_CONTROL.

    Usa GetSecurityInfo com SE_FILE_OBJECT e copia o SECURITY_DESCRIPTOR
    self-relative retornado pelo Windows antes de liberar sua memória.
    """
    _require_windows_x64()
    value = _native_handle_value(directory_handle)

    try:
        from sermax_windows_handle_io import query_handle_metadata
        metadata = query_handle_metadata(directory_handle)
        if (
            not metadata["is_directory"]
            or metadata["is_reparse_point"]
            or metadata["delete_pending"]
        ):
            raise EffectiveAccessError(
                "O descritor exige diretório regular, sem reparse point ou DeletePending."
            )

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_security_info = advapi32.GetSecurityInfo
        get_security_info.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        get_security_info.restype = wintypes.DWORD

        get_length = advapi32.GetSecurityDescriptorLength
        get_length.argtypes = [ctypes.c_void_p]
        get_length.restype = wintypes.DWORD

        local_free = kernel32.LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p

        descriptor = ctypes.c_void_p()
        security_info = (
            OWNER_SECURITY_INFORMATION
            | GROUP_SECURITY_INFORMATION
            | DACL_SECURITY_INFORMATION
        )
        status = get_security_info(
            wintypes.HANDLE(value), SE_FILE_OBJECT, security_info,
            None, None, None, None, ctypes.byref(descriptor),
        )
        if status != ERROR_SUCCESS:
            raise EffectiveAccessError(
                f"GetSecurityInfo falhou, WinError={int(status)}."
            )
        if not descriptor:
            raise EffectiveAccessError("GetSecurityInfo retornou descritor nulo.")

        try:
            length = int(get_length(descriptor))
            if length < 20 or length > MAX_SECURITY_DESCRIPTOR_SIZE:
                raise EffectiveAccessError(
                    f"Comprimento do descritor fora dos limites: {length}."
                )
            binary = ctypes.string_at(descriptor, length)
            if len(binary) != length:
                raise EffectiveAccessError("Cópia do descritor incompleta.")
            return binary
        finally:
            if local_free(descriptor):
                raise EffectiveAccessError(
                    "LocalFree falhou ao liberar o descritor de segurança."
                )
    except EffectiveAccessError:
        raise
    except Exception as exc:
        raise EffectiveAccessError(
            f"Falha ao ler o descritor de segurança pelo handle: {exc}"
        ) from exc


def evaluate_access_for_token(
    token_handle,
    security_descriptor: bytes,
    desired_access: int,
) -> dict:
    """Avalia direitos de diretório para um token real via AuthzAccessCheck.

    O token deve estar aberto com TOKEN_QUERY. desired_access deve conter
    direitos específicos de arquivo/diretório já mapeados, sem GENERIC_*.
    A função não cria tokens, não altera ACLs e não executa operações de I/O.
    """
    _require_windows_x64()
    if not isinstance(security_descriptor, bytes) or len(security_descriptor) < 20:
        raise EffectiveAccessError("Descritor de segurança binário inválido.")
    if not isinstance(desired_access, int) or not 0 < desired_access <= 0xFFFFFFFF:
        raise EffectiveAccessError("Máscara de acesso solicitada inválida.")
    if desired_access & GENERIC_ACCESS_BITS:
        raise EffectiveAccessError(
            "Máscaras GENERIC_* devem ser mapeadas antes da avaliação."
        )

    token = _native_handle_value(token_handle)

    authz = ctypes.WinDLL("authz", use_last_error=True)
    initialize_rm = authz.AuthzInitializeResourceManager
    initialize_rm.argtypes = [
        wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
    ]
    initialize_rm.restype = wintypes.BOOL

    initialize_context = authz.AuthzInitializeContextFromToken
    initialize_context.argtypes = [
        wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, LUID, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    initialize_context.restype = wintypes.BOOL

    access_check = authz.AuthzAccessCheck
    access_check.argtypes = [
        wintypes.DWORD, ctypes.c_void_p,
        ctypes.POINTER(AUTHZ_ACCESS_REQUEST), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        wintypes.DWORD, ctypes.POINTER(AUTHZ_ACCESS_REPLY),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    access_check.restype = wintypes.BOOL

    free_context = authz.AuthzFreeContext
    free_context.argtypes = [ctypes.c_void_p]
    free_context.restype = wintypes.BOOL

    free_rm = authz.AuthzFreeResourceManager
    free_rm.argtypes = [ctypes.c_void_p]
    free_rm.restype = wintypes.BOOL

    resource_manager = ctypes.c_void_p()
    client_context = ctypes.c_void_p()
    if not initialize_rm(
        0x1, None, None, None, "SERMAX effective access validation",
        ctypes.byref(resource_manager),
    ):
        error = ctypes.get_last_error()
        raise EffectiveAccessError(
            f"AuthzInitializeResourceManager falhou, WinError={error}."
        )

    try:
        if not initialize_context(
            0, wintypes.HANDLE(token), resource_manager, None, LUID(0, 0), None,
            ctypes.byref(client_context),
        ):
            error = ctypes.get_last_error()
            raise EffectiveAccessError(
                f"AuthzInitializeContextFromToken falhou, WinError={error}."
            )
        try:
            granted = wintypes.DWORD(0)
            sacl_result = wintypes.DWORD(0)
            status = wintypes.DWORD(0)
            request = AUTHZ_ACCESS_REQUEST(desired_access, None, None, 0, None)
            reply = AUTHZ_ACCESS_REPLY(
                1, ctypes.pointer(granted), ctypes.pointer(sacl_result),
                ctypes.pointer(status),
            )
            descriptor_buffer = ctypes.create_string_buffer(security_descriptor)
            if not access_check(
                0, client_context, ctypes.byref(request), None,
                ctypes.cast(descriptor_buffer, ctypes.c_void_p),
                None, 0, ctypes.byref(reply), None,
            ):
                error = ctypes.get_last_error()
                raise EffectiveAccessError(
                    f"AuthzAccessCheck falhou, WinError={error}."
                )

            granted_mask = int(granted.value)
            status_code = int(status.value)
            return {
                "api": "AuthzAccessCheck",
                "api_success": True,
                "desired_access": int(desired_access),
                "granted_access_mask": granted_mask,
                "error": status_code,
                "granted": (
                    status_code == ERROR_SUCCESS
                    and (granted_mask & desired_access) == desired_access
                ),
                "token_source": "real_kernel_token",
                "security_descriptor_source": "GetSecurityInfo_same_handle",
                "mutated": False,
                "performed_io": False,
            }
        finally:
            if client_context and not free_context(client_context):
                raise EffectiveAccessError("AuthzFreeContext falhou.")
    finally:
        if resource_manager and not free_rm(resource_manager):
            raise EffectiveAccessError("AuthzFreeResourceManager falhou.")
