"""Inspeção e validação somente de leitura da área privada _update.

Reutiliza o inspetor ACL, a política estrita e o avaliador Authz já existentes
no SERMAX. Não cria diretórios, não altera ACL e não grava arquivos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sermax_windows_acl_inspection import (
    DirectoryAclInspectionError,
    inspect_directory_acl,
)
from sermax_windows_directory_enum import DirectoryEntry
from sermax_windows_directory_handle import (
    enumerate_stable_directory_handle,
    open_verified_child_component,
)
from sermax_windows_effective_access import (
    EffectiveAccessError,
    evaluate_access_for_token,
    read_security_descriptor_binary,
)
from sermax_windows_handle_io import (
    HandleIoError,
    close_handle,
    query_handle_metadata,
)
from sermax_windows_private_area_acl_policy import (
    PrivateAreaAclPolicyError,
    validate_private_area_acl,
)

READ_CONTROL = 0x00020000
_UPDATE_COMPONENT = "_update"
_REQUIRED_EFFECTIVE_RIGHTS = {
    "list_directory": 0x0001,
    "add_file": 0x0002,
    "add_subdirectory": 0x0004,
    "delete_child": 0x0040,
    "read_control": 0x00020000,
    "write_dac": 0x00040000,
    "write_owner": 0x00080000,
}


class UpdateAreaError(RuntimeError):
    """A área _update não passou pela inspeção ou política de segurança."""


@dataclass
class UpdateAreaInspection:
    """Handle retido e evidências lidas do mesmo objeto _update."""

    handle: Any
    metadata: dict[str, object]
    acl_inspection: dict[str, object]
    directory_entries: list[DirectoryEntry]

    def close(self) -> None:
        if self.handle is not None:
            close_handle(self.handle)
            self.handle = None

    def __enter__(self) -> "UpdateAreaInspection":
        if self.handle is None:
            raise UpdateAreaError("Inspeção já foi encerrada.")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def inspect_update_area_by_handle(sermax_handle) -> UpdateAreaInspection:
    """Abre _update relativamente ao handle SERMAX e coleta evidências.

    Exige exatamente um componente literal _update, diretório comum e sem
    reparse point. A abertura valida FileId, volume, atributos e tamanho.
    A DACL é lida pelo inspetor ACL já existente. O handle fica aberto até
    close() para manter a identidade durante validações posteriores.
    """
    try:
        parent = query_handle_metadata(sermax_handle)
        if (
            not parent["is_directory"]
            or parent["is_reparse_point"]
            or parent["delete_pending"]
        ):
            raise UpdateAreaError("Handle SERMAX inválido ou instável.")

        entries = enumerate_stable_directory_handle(sermax_handle)
        candidates = [
            entry for entry in entries
            if entry.name.casefold() == _UPDATE_COMPONENT.casefold()
        ]
        if len(candidates) != 1:
            raise UpdateAreaError(
                "A enumeração não encontrou exatamente uma área _update."
            )

        entry = candidates[0]
        if entry.name != _UPDATE_COMPONENT:
            raise UpdateAreaError("Nome da área diverge da grafia canônica _update.")
        if not entry.is_directory or entry.is_reparse_point:
            raise UpdateAreaError("_update não é diretório comum; abertura recusada.")

        handle = open_verified_child_component(
            sermax_handle, entry, desired_access=READ_CONTROL
        )
        try:
            metadata = query_handle_metadata(handle)
            if (
                not metadata["is_directory"]
                or metadata["is_reparse_point"]
                or metadata["delete_pending"]
            ):
                raise UpdateAreaError("Objeto _update aberto não é diretório válido.")
            if metadata["volume_serial_number"] != parent["volume_serial_number"]:
                raise UpdateAreaError("_update pertence a volume diferente de SERMAX.")

            acl_inspection = inspect_directory_acl(handle)
            directory_entries = list(enumerate_stable_directory_handle(handle))
            return UpdateAreaInspection(
                handle=handle,
                metadata=metadata,
                acl_inspection=acl_inspection,
                directory_entries=directory_entries,
            )
        except Exception:
            close_handle(handle)
            raise
    except UpdateAreaError:
        raise
    except (HandleIoError, DirectoryAclInspectionError) as exc:
        raise UpdateAreaError(f"Falha na inspeção segura de _update: {exc}") from exc


def _token_user_sid(token_handle) -> str:
    try:
        import ctypes
        import win32security

        native = token_handle.value if isinstance(token_handle, ctypes.c_void_p) else token_handle
        if native is None or native == 0:
            raise UpdateAreaError("Token de segurança nulo.")
        token_user = win32security.GetTokenInformation(
            native, win32security.TokenUser
        )[0]
        return str(win32security.ConvertSidToStringSid(token_user))
    except UpdateAreaError:
        raise
    except Exception as exc:
        raise UpdateAreaError(f"Não foi possível identificar o usuário do token: {exc}") from exc


def validate_update_area_acl_policy(
    inspection: UpdateAreaInspection,
    *,
    token_handle,
) -> dict[str, object]:
    """Valida a política ACL existente e os direitos do token real do instalador.

    O SID proprietário esperado vem do usuário do token fornecido. A política
    exige diretório vazio, DACL protegida e exatamente as ACEs definidas no
    módulo sermax_windows_private_area_acl_policy. Authz avalia os direitos
    solicitados sobre o descritor obtido do mesmo handle. Nenhuma operação de
    escrita é executada por esta função.
    """
    if not isinstance(inspection, UpdateAreaInspection) or inspection.handle is None:
        raise UpdateAreaError("Inspeção _update inválida ou já encerrada.")

    owner_sid = _token_user_sid(token_handle)
    metadata = inspection.metadata
    try:
        policy = validate_private_area_acl(
            inspection.acl_inspection,
            expected_owner_sid=owner_sid,
            expected_volume_serial=int(metadata["volume_serial_number"]),
            expected_file_id_128=str(metadata["file_id_128"]),
            directory_identity=metadata,
            directory_entries=inspection.directory_entries,
        )

        descriptor = read_security_descriptor_binary(inspection.handle)
        effective: dict[str, object] = {}
        for name, mask in _REQUIRED_EFFECTIVE_RIGHTS.items():
            result = evaluate_access_for_token(token_handle, descriptor, mask)
            if (
                result.get("api_success") is not True
                or result.get("granted") is not True
                or result.get("token_source") != "real_kernel_token"
                or result.get("mutated") is not False
                or result.get("performed_io") is not False
            ):
                raise UpdateAreaError(
                    f"Authz não confirmou o direito exigido: {name}."
                )
            effective[name] = result
    except (PrivateAreaAclPolicyError, EffectiveAccessError) as exc:
        raise UpdateAreaError(f"Política ACL de _update recusada: {exc}") from exc

    return {
        "valid": True,
        "owner_sid": owner_sid,
        "acl_policy": policy,
        "effective_rights": effective,
        "mutated": False,
        "performed_io": False,
    }
