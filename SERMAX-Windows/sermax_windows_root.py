"""Abertura validada da raiz de uma unidade local e do diretório SERMAX.

A caminhada usa handles: primeiro X:\, depois o componente SERMAX relativo
à raiz. O módulo não lê conteúdo nem altera arquivos.
"""
from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes

from sermax_windows_handle_io import (
    close_handle,
    open_relative_component,
    query_handle_metadata,
)

FILE_READ_ATTRIBUTES = 0x0080
FILE_LIST_DIRECTORY = 0x0001
SYNCHRONIZE = 0x00100000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
FILE_ADD_FILE = 0x00000002
FILE_ADD_SUBDIRECTORY = 0x00000004
OBJECT_INHERIT_ACE = 0x01
CONTAINER_INHERIT_ACE = 0x02
INHERIT_ONLY_ACE = 0x08
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_DRIVE_ROOT = re.compile(r"^[A-Za-z]:\\$")


class RootOpenError(RuntimeError):
    """A raiz ou o diretório gerenciado não pôde ser validado."""


def _require_windows_x64() -> None:
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RootOpenError("A abertura segura exige Windows x64.")


def _validate_drive_root(path: str) -> str:
    if not isinstance(path, str) or not _DRIVE_ROOT.fullmatch(path):
        raise RootOpenError("Informe a raiz local no formato X:\\.")
    _require_windows_x64()
    return path


def open_drive_root(path: str):
    """Abre X:\ como diretório e valida o objeto pelo handle retornado.

    O chamador deve fechar o handle com close_handle().
    """
    path = _validate_drive_root(path)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
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


def open_managed_directory(parent_handle, component: str = "SERMAX", *,
                           expected_volume_serial: int | None = None,
                           access_mask: int | None = None):
    """Abre um diretório filho relativo ao pai e valida identidade e tipo.

    O handle pai deve permanecer aberto durante a chamada e durante o uso do
    handle filho. Reparse points e mudanças de volume são rejeitados.
    """
    _require_windows_x64()
    if component != "SERMAX":
        raise RootOpenError("Esta etapa aceita exclusivamente o componente SERMAX.")

    try:
        parent_metadata = query_handle_metadata(parent_handle)
    except Exception as exc:
        raise RootOpenError(f"Não foi possível validar o handle pai: {exc}") from exc

    if not parent_metadata["is_directory"] or parent_metadata["is_reparse_point"]:
        raise RootOpenError("O handle pai não representa um diretório regular.")
    if parent_metadata["delete_pending"]:
        raise RootOpenError("O diretório pai está marcado para exclusão.")

    parent_volume = int(parent_metadata["volume_serial_number"])
    if expected_volume_serial is not None and parent_volume != expected_volume_serial:
        raise RootOpenError("A identidade do volume pai diverge da identidade esperada.")

    if access_mask is None:
        child = open_relative_component(parent_handle, component, directory=True)
    else:
        child = open_relative_component(
            parent_handle, component, directory=True, desired_access=access_mask
        )
    try:
        child_metadata = query_handle_metadata(child)
        if not child_metadata["is_directory"] or child_metadata["is_reparse_point"]:
            raise RootOpenError("SERMAX não é um diretório regular.")
        if child_metadata["delete_pending"]:
            raise RootOpenError("SERMAX está marcado para exclusão.")
        if int(child_metadata["volume_serial_number"]) != parent_volume:
            raise RootOpenError("SERMAX está em outro volume; montagem rejeitada.")
        if expected_volume_serial is not None and int(
            child_metadata["volume_serial_number"]
        ) != expected_volume_serial:
            raise RootOpenError("A identidade do volume SERMAX diverge da esperada.")
        return child
    except Exception:
        try:
            close_handle(child)
        except Exception as close_error:
            raise RootOpenError(
                f"Falha ao validar SERMAX e também ao fechar o handle: {close_error}"
            ) from close_error
        raise


def open_managed_directory_for_acl(parent_handle, component: str = "SERMAX"):
    """Abre um diretório gerenciado com READ_CONTROL e WRITE_DAC.

    O handle retornado permite consultar e alterar a DACL. O chamador deve
    fechá-lo e aplicar somente uma política explicitamente definida.
    """
    return open_managed_directory(
        parent_handle,
        component,
        access_mask=READ_CONTROL | WRITE_DAC,
    )


def _ace_denies_child_creation_on_directory(ace, sid, win32security) -> bool:
    """Confirma uma negação efetiva no diretório e herdável por seus filhos."""
    ace_type, ace_flags = ace[0]
    denied_mask = FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY
    inherit_flags = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
    return (
        ace_type == win32security.ACCESS_DENIED_ACE_TYPE
        and (ace_flags & inherit_flags) == inherit_flags
        and not (ace_flags & INHERIT_ONLY_ACE)
        and (ace[1] & denied_mask) == denied_mask
        and win32security.ConvertSidToStringSid(ace[2])
        == win32security.ConvertSidToStringSid(sid)
    )


def deny_child_creation_for_sid(directory_handle, sid) -> bool:
    """Nega criação de arquivos e subdiretórios para um SID específico.

    A ACE vale para o diretório e é herdável por arquivos e subdiretórios.
    As demais ACEs existentes são preservadas. A função exige DACL presente,
    não nula, e um handle de diretório aberto com READ_CONTROL e WRITE_DAC.

    Retorna True quando adiciona a ACE e False quando a mesma regra já existe.
    Não escolhe SID automaticamente e não altera qualquer caminho por nome.
    """
    _require_windows_x64()
    try:
        metadata = query_handle_metadata(directory_handle)
    except Exception as exc:
        raise RootOpenError(f"Não foi possível validar o handle para ACL: {exc}") from exc

    if not metadata["is_directory"] or metadata["is_reparse_point"]:
        raise RootOpenError("A ACL exige handle de diretório regular, sem reparse point.")
    if metadata["delete_pending"]:
        raise RootOpenError("O diretório está marcado para exclusão.")

    try:
        import win32security
    except ImportError as exc:
        raise RootOpenError("A camada de ACL exige o módulo win32security.") from exc

    native_handle = (
        directory_handle.value
        if isinstance(directory_handle, ctypes.c_void_p)
        else directory_handle
    )
    if native_handle is None:
        raise RootOpenError("Handle nulo para alteração de ACL.")

    denied_mask = FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY
    inherit_flags = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
    try:
        current_sd = win32security.GetSecurityInfo(
            native_handle,
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
        )
        current_dacl = current_sd.GetSecurityDescriptorDacl()
        if current_dacl is None:
            raise RootOpenError(
                "DACL ausente ou nula; alteração recusada para evitar liberar ou bloquear "
                "acessos de forma ampla."
            )

        for index in range(current_dacl.GetAceCount()):
            ace = current_dacl.GetAce(index)
            if _ace_denies_child_creation_on_directory(ace, sid, win32security):
                return False

        updated_dacl = current_dacl
        updated_dacl.SetEntriesInAcl([
            {
                "AccessMode": win32security.DENY_ACCESS,
                "AccessPermissions": denied_mask,
                "Inheritance": inherit_flags,
                "Trustee": {
                    "TrusteeType": win32security.TRUSTEE_IS_USER,
                    "TrusteeForm": win32security.TRUSTEE_IS_SID,
                    "Identifier": sid,
                },
            }
        ])

        win32security.SetSecurityInfo(
            native_handle,
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
            None,
            None,
            updated_dacl,
            None,
        )

        verified_sd = win32security.GetSecurityInfo(
            native_handle,
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
        )
        verified_dacl = verified_sd.GetSecurityDescriptorDacl()
        if verified_dacl is None:
            raise RootOpenError("A verificação posterior encontrou DACL ausente.")
        for index in range(verified_dacl.GetAceCount()):
            ace = verified_dacl.GetAce(index)
            if _ace_denies_child_creation_on_directory(ace, sid, win32security):
                return True
        raise RootOpenError("A ACE de negação não foi confirmada após a gravação.")
    except RootOpenError:
        raise
    except Exception as exc:
        raise RootOpenError(f"Falha ao aplicar ou verificar a DACL: {exc}") from exc


def open_sermax_directory(drive_root_handle):
    """Abre C:\SERMAX por componente relativo ao handle da raiz C:\."""
    return open_managed_directory(drive_root_handle, "SERMAX")
