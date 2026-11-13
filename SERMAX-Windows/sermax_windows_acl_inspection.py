"""Inspeção somente de leitura da ACL de diretórios Windows.

Não altera DACL, proprietário, herança ou permissões. O resultado é
informativo e não equivale a uma avaliação completa de acesso efetivo.
"""
from __future__ import annotations

import ctypes
import os


class DirectoryAclInspectionError(RuntimeError):
    """Falha fechada ao inspecionar a segurança de um diretório."""


SE_DACL_PROTECTED = 0x1000
SE_DACL_AUTO_INHERITED = 0x0400
SE_DACL_AUTO_INHERIT_REQ = 0x0100


def _native_handle(handle):
    value = handle.value if isinstance(handle, ctypes.c_void_p) else handle
    if value is None or value == 0:
        raise DirectoryAclInspectionError("Handle nulo.")
    return value


def inspect_directory_acl(directory_handle) -> dict:
    """Retorna proprietário, estado da DACL, controle de herança e ACEs.

    Exige Windows x64 e um handle já aberto com READ_CONTROL. A função
    consulta metadados pelo handle e usa GetSecurityInfo. Não escreve ACL.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise DirectoryAclInspectionError("A inspeção exige Windows x64.")

    try:
        from sermax_windows_handle_io import query_handle_metadata
        metadata = query_handle_metadata(directory_handle)
    except Exception as exc:
        raise DirectoryAclInspectionError(
            f"Não foi possível validar o handle: {exc}"
        ) from exc

    if (
        not metadata["is_directory"]
        or metadata["is_reparse_point"]
        or metadata["delete_pending"]
    ):
        raise DirectoryAclInspectionError(
            "A inspeção exige diretório regular, sem reparse point ou DeletePending."
        )

    try:
        import win32security
    except ImportError as exc:
        raise DirectoryAclInspectionError(
            "A inspeção exige o módulo win32security."
        ) from exc

    try:
        native = _native_handle(directory_handle)
        security_info = (
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.GROUP_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION
        )
        descriptor = win32security.GetSecurityInfo(
            native, win32security.SE_FILE_OBJECT, security_info
        )
        owner = descriptor.GetOwner()
        group = descriptor.GetGroup()
        dacl = descriptor.GetSecurityDescriptorDacl()
        control, revision = descriptor.GetSecurityDescriptorControl()

        if dacl is None:
            dacl_state = "null_or_absent"
            aces = []
        else:
            dacl_state = "present"
            aces = []
            for index in range(dacl.GetAceCount()):
                ace = dacl.GetAce(index)
                ace_header = ace[0]
                ace_type, ace_flags = ace_header
                ace_record = {
                    "index": index,
                    "type": int(ace_type),
                    "flags": int(ace_flags),
                    "mask": int(ace[1]) if len(ace) > 1 and isinstance(
                        ace[1], int
                    ) else None,
                    "sid": None,
                }
                if len(ace) > 2:
                    try:
                        ace_record["sid"] = win32security.ConvertSidToStringSid(
                            ace[2]
                        )
                    except Exception:
                        # ACEs de objeto podem ter campos diferentes. Mantemos
                        # o tipo e as flags, sem inferir o trustee.
                        ace_record["sid"] = None
                aces.append(ace_record)

        owner_sid = (
            win32security.ConvertSidToStringSid(owner)
            if owner is not None else None
        )
        group_sid = (
            win32security.ConvertSidToStringSid(group)
            if group is not None else None
        )
        return {
            "owner_sid": owner_sid,
            "group_sid": group_sid,
            "dacl_state": dacl_state,
            "dacl_protected": bool(control & SE_DACL_PROTECTED),
            "dacl_auto_inherited": bool(control & SE_DACL_AUTO_INHERITED),
            "dacl_auto_inherit_requested": bool(
                control & SE_DACL_AUTO_INHERIT_REQ
            ),
            "control": int(control),
            "revision": int(revision),
            "aces": aces,
            "effective_access_evaluated": False,
            "mutated": False,
        }
    except DirectoryAclInspectionError:
        raise
    except Exception as exc:
        raise DirectoryAclInspectionError(
            f"Falha ao consultar descritor de segurança: {exc}"
        ) from exc
