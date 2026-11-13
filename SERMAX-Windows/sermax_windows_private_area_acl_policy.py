"""Validação estrita e somente de leitura da política ACL da área privada.

Este módulo valida um relatório produzido pela inspeção por handle. Não altera
descritores de segurança e não calcula acesso efetivo do Windows.
"""
from __future__ import annotations


class PrivateAreaAclPolicyError(RuntimeError):
    """A DACL ou a identidade do diretório não atende à política privada."""


ACCESS_ALLOWED_ACE_TYPE = 0
OBJECT_INHERIT_ACE = 0x01
CONTAINER_INHERIT_ACE = 0x02
FILE_ALL_ACCESS = 0x001F01FF
REQUIRED_PRIVATE_SIDS = frozenset({
    "S-1-5-18",       # LocalSystem
    "S-1-5-32-544",   # BUILTIN Administrators
})


def validate_private_area_acl(
    inspection: dict,
    *,
    expected_owner_sid: str,
    expected_volume_serial: int,
    expected_file_id_128: str,
    directory_entries: list,
) -> dict:
    """Valida identidade, diretório vazio e DACL privada, sem mutação.

    inspection deve vir de inspect_directory_acl() e directory_entries de
    enumeração estável do mesmo handle. O chamador mantém o handle aberto e
    garante que ambos os resultados se referem à mesma identidade.
    """
    if not isinstance(inspection, dict):
        raise PrivateAreaAclPolicyError("Relatório ACL inválido.")
    if not isinstance(expected_owner_sid, str) or not expected_owner_sid:
        raise PrivateAreaAclPolicyError("SID esperado do proprietário inválido.")
    if not isinstance(expected_volume_serial, int) or expected_volume_serial < 0:
        raise PrivateAreaAclPolicyError("Volume esperado inválido.")
    if (
        not isinstance(expected_file_id_128, str)
        or len(expected_file_id_128) != 32
        or any(ch not in "0123456789abcdefABCDEF" for ch in expected_file_id_128)
    ):
        raise PrivateAreaAclPolicyError("FileId esperado deve conter 128 bits.")
    if not isinstance(directory_entries, list):
        raise PrivateAreaAclPolicyError("A enumeração do diretório é inválida.")

    identity = inspection.get("directory_identity")
    if not isinstance(identity, dict):
        raise PrivateAreaAclPolicyError("Identidade por handle ausente.")
    if identity.get("volume_serial_number") != expected_volume_serial:
        raise PrivateAreaAclPolicyError("Volume do diretório diverge do esperado.")
    actual_file_id = identity.get("file_id_128")
    if not isinstance(actual_file_id, str) or actual_file_id.lower() != expected_file_id_128.lower():
        raise PrivateAreaAclPolicyError("FileId do diretório diverge do esperado.")
    if directory_entries:
        raise PrivateAreaAclPolicyError("O diretório precisa estar vazio.")

    if inspection.get("owner_sid") != expected_owner_sid:
        raise PrivateAreaAclPolicyError("O proprietário não corresponde ao usuário esperado.")
    if inspection.get("dacl_state") != "present":
        raise PrivateAreaAclPolicyError("A DACL precisa estar presente e não nula.")
    if inspection.get("dacl_protected") is not True:
        raise PrivateAreaAclPolicyError("A DACL precisa estar protegida contra herança.")
    if inspection.get("mutated") is not False:
        raise PrivateAreaAclPolicyError("O relatório não comprova inspeção sem mutação.")
    if inspection.get("effective_access_evaluated") is not False:
        raise PrivateAreaAclPolicyError("O relatório de inspeção contém estado inesperado.")

    aces = inspection.get("aces")
    if not isinstance(aces, list):
        raise PrivateAreaAclPolicyError("Lista de ACEs inválida.")

    expected_sids = set(REQUIRED_PRIVATE_SIDS)
    expected_sids.add(expected_owner_sid)
    if len(expected_sids) != 3 or len(aces) != 3:
        raise PrivateAreaAclPolicyError(
            "A política exige exatamente três trustees distintos e três ACEs."
        )

    observed_sids = set()
    required_flags = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
    for ace in aces:
        if not isinstance(ace, dict):
            raise PrivateAreaAclPolicyError("ACE em formato inválido.")
        if ace.get("type") != ACCESS_ALLOWED_ACE_TYPE:
            raise PrivateAreaAclPolicyError("ACE diferente de ACCESS_ALLOWED foi encontrada.")
        if ace.get("mask") != FILE_ALL_ACCESS:
            raise PrivateAreaAclPolicyError("Máscara de acesso fora da política estrita.")
        if ace.get("flags") != required_flags:
            raise PrivateAreaAclPolicyError("Flags de herança da ACE fora da política.")
        sid = ace.get("sid")
        if not isinstance(sid, str) or sid not in expected_sids or sid in observed_sids:
            raise PrivateAreaAclPolicyError("Trustee ausente, inesperado ou duplicado.")
        observed_sids.add(sid)

    if observed_sids != expected_sids:
        raise PrivateAreaAclPolicyError("A DACL não contém exatamente os três trustees exigidos.")

    return {
        "valid": True,
        "owner_sid": expected_owner_sid,
        "volume_serial_number": expected_volume_serial,
        "file_id_128": expected_file_id_128.lower(),
        "directory_empty": True,
        "dacl_protected": True,
        "trustee_sids": sorted(observed_sids),
        "effective_access_evaluated": False,
        "mutated": False,
    }
