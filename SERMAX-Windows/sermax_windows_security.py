"""Protótipo independente de leitura de metadados de segurança por handle.

Não é o inspetor oficial do fluxo do atualizador. O fluxo integrado deve usar
sermax_windows_acl_inspection.py e sermax_windows_private_area_acl_policy.py.
Este protótipo fica preservado para comparação e não autoriza escrita.
"""
from __future__ import annotations

import ctypes
import os

from sermax_windows_handle_io import HandleIoError, query_handle_metadata

OWNER_SECURITY_INFORMATION = 0x00000001
GROUP_SECURITY_INFORMATION = 0x00000002
DACL_SECURITY_INFORMATION = 0x00000004

_BASIC_ACE_TYPES = {0, 1}


class DirectorySecurityError(RuntimeError):
    """Falha ao ler ou interpretar o descritor de segurança."""


def _sid_text(sid, win32security) -> str | None:
    if sid is None:
        return None
    try:
        return str(win32security.ConvertSidToStringSid(sid))
    except Exception as exc:
        raise DirectorySecurityError("SID inválido no descritor de segurança.") from exc


def read_security_by_handle(handle) -> dict[str, object]:
    """Lê owner, group, DACL e ACEs do objeto já aberto.

    O chamador deve manter o handle aberto durante a leitura e qualquer
    validação subsequente. Requer Windows x64 e um objeto que não esteja
    marcado para exclusão. Não interpreta direitos efetivos e não escreve.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise DirectorySecurityError("Leitura de segurança exige Windows x64.")

    metadata = query_handle_metadata(handle)
    if not metadata["is_directory"] or metadata["is_reparse_point"]:
        raise DirectorySecurityError("A leitura exige handle de diretório regular.")
    if metadata["delete_pending"]:
        raise DirectorySecurityError("Diretório marcado para exclusão.")

    try:
        import win32security
    except ImportError as exc:
        raise DirectorySecurityError("Módulo win32security indisponível.") from exc

    information = (
        OWNER_SECURITY_INFORMATION
        | GROUP_SECURITY_INFORMATION
        | DACL_SECURITY_INFORMATION
    )
    native_handle = handle.value if isinstance(handle, ctypes.c_void_p) else handle
    try:
        descriptor = win32security.GetSecurityInfo(
            native_handle, win32security.SE_FILE_OBJECT, information
        )
        owner, owner_defaulted = descriptor.GetSecurityDescriptorOwner()
        group, group_defaulted = descriptor.GetSecurityDescriptorGroup()
        dacl = descriptor.GetSecurityDescriptorDacl()
        control, revision = descriptor.GetSecurityDescriptorControl()
    except Exception as exc:
        raise DirectorySecurityError(
            f"Não foi possível ler o descritor de segurança: {exc}"
        ) from exc

    dacl_present = bool(control & 0x0004)
    dacl_protected = bool(control & 0x1000)
    dacl_auto_inherited = bool(control & 0x0400)

    if not dacl_present or dacl is None:
        dacl_state = "null_or_absent"
        ace_records: list[dict[str, object]] = []
    else:
        dacl_state = "present"
        ace_records = []
        for index in range(dacl.GetAceCount()):
            try:
                ace = dacl.GetAce(index)
                ace_header = ace[0]
                ace_type = int(ace_header[0])
                ace_flags = int(ace_header[1])
                access_mask = int(ace[1]) if len(ace) >= 3 and isinstance(
                    ace[1], int
                ) else None
                trustee = None
                if len(ace) >= 3:
                    for candidate in ace[2:]:
                        try:
                            trustee = _sid_text(candidate, win32security)
                            if trustee is not None:
                                break
                        except DirectorySecurityError:
                            continue
                ace_records.append({
                    "index": index,
                    "ace_type": ace_type,
                    "ace_flags": ace_flags,
                    "access_mask": access_mask,
                    "trustee_sid": trustee,
                    "basic_allow_or_deny": ace_type in _BASIC_ACE_TYPES,
                    "supported_for_policy": (
                        ace_type in _BASIC_ACE_TYPES
                        and access_mask is not None
                        and trustee is not None
                    ),
                    "field_count": len(ace),
                })
            except Exception as exc:
                raise DirectorySecurityError(
                    f"ACE {index} não pôde ser interpretada; política deve falhar fechada."
                ) from exc

    return {
        "owner_sid": _sid_text(owner, win32security),
        "owner_defaulted": bool(owner_defaulted),
        "group_sid": _sid_text(group, win32security),
        "group_defaulted": bool(group_defaulted),
        "dacl_state": dacl_state,
        "dacl_protected": dacl_protected,
        "dacl_auto_inherited": dacl_auto_inherited,
        "descriptor_control": int(control),
        "descriptor_revision": int(revision),
        "aces": ace_records,
        "volume_serial_number": int(metadata["volume_serial_number"]),
        "file_id_128": str(metadata["file_id_128"]),
        "number_of_links": int(metadata["number_of_links"]),
    }
