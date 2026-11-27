"""Criação exclusiva de diretórios internos com ACL definida atomicamente.

Cada componente é criado relativamente a um handle pai validado. O descritor
de segurança é enviado em OBJECT_ATTRIBUTES durante NtCreateFile, antes de o
novo diretório ficar disponível a outros fluxos. A ACL é lida e validada pelo
handle retornado antes de a função liberar esse handle ao chamador.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
from dataclasses import dataclass
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
FILE_ADD_FILE = 0x00000002
FILE_ADD_SUBDIRECTORY = 0x00000004
FILE_SHARE_READ = 0x00000001
READ_CONTROL = 0x00020000
SE_DACL_PROTECTED = 0x1000
TOKEN_QUERY = 0x0008
FILE_ALL_ACCESS = 0x001F01FF
MAX_SECURITY_DESCRIPTOR_SIZE = 1024 * 1024

ALLOWED_PRIVATE_COMPONENTS = frozenset({
    "_update", "staging", "backups", "journal", "logs", "locks",
})


class PrivateAreaError(RuntimeError):
    """Falha fechada ao criar ou validar um diretório interno."""


def _prepare_private_security_descriptor():
    """Monta descriptor self-relative com owner e DACL privada explícitos."""
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise PrivateAreaError("A preparação de ACL exige Windows x64.")

    try:
        import win32api
        import win32security
    except ImportError as exc:
        raise PrivateAreaError("A criação protegida exige pywin32.") from exc

    token = None
    try:
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), TOKEN_QUERY
        )
        owner_sid = win32security.GetTokenInformation(
            token, win32security.TokenUser
        )[0]
        owner_sid_text = win32security.ConvertSidToStringSid(owner_sid)
        system_sid = win32security.ConvertStringSidToSid("S-1-5-18")
        admins_sid = win32security.ConvertStringSidToSid("S-1-5-32-544")
        expected_sids = {
            owner_sid_text, "S-1-5-18", "S-1-5-32-544"
        }
        if len(expected_sids) != 3:
            raise PrivateAreaError(
                "O SID do processo colide com trustee reservado da política."
            )

        dacl = win32security.ACL()
        ace_flags = 0x01 | 0x02  # OBJECT_INHERIT | CONTAINER_INHERIT
        for sid in (owner_sid, system_sid, admins_sid):
            dacl.AddAccessAllowedAceEx(
                win32security.ACL_REVISION,
                ace_flags,
                FILE_ALL_ACCESS,
                sid,
            )
        if dacl.GetAceCount() != 3:
            raise PrivateAreaError("A DACL preparada não contém três ACEs.")

        descriptor = win32security.SECURITY_DESCRIPTOR()
        descriptor.Initialize()
        descriptor.SetSecurityDescriptorOwner(owner_sid, False)
        descriptor.SetSecurityDescriptorDacl(True, dacl, False)
        descriptor.SetSecurityDescriptorControl(
            SE_DACL_PROTECTED, SE_DACL_PROTECTED
        )

        if not descriptor.IsValid() or not descriptor.IsSelfRelative():
            raise PrivateAreaError(
                "O descritor de segurança não é válido e self-relative."
            )
        control, _revision = descriptor.GetSecurityDescriptorControl()
        if not (control & SE_DACL_PROTECTED):
            raise PrivateAreaError("A DACL não ficou protegida contra herança.")

        raw = memoryview(descriptor).tobytes()
        if not raw or len(raw) > MAX_SECURITY_DESCRIPTOR_SIZE:
            raise PrivateAreaError("Tamanho do descritor de segurança inválido.")
        descriptor_buffer = ctypes.create_string_buffer(raw, len(raw))

        return token, win32api.CloseHandle, descriptor_buffer, owner_sid_text
    except Exception as exc:
        if token is not None:
            try:
                win32api.CloseHandle(token)
            except Exception as close_error:
                if hasattr(exc, "add_note"):
                    exc.add_note(
                        f"Falha ao fechar token após erro na ACL: {close_error}"
                    )
        if isinstance(exc, PrivateAreaError):
            raise
        raise PrivateAreaError(
            f"Não foi possível preparar a ACL privada: {exc}"
        ) from exc


def _validate_created_private_directory(
    child_handle,
    metadata: dict[str, object],
    token_handle,
    *,
    require_empty: bool = True,
) -> dict[str, object]:
    """Valida DACL e Authz no mesmo handle antes de liberar o diretório."""
    try:
        from sermax_windows_acl_inspection import inspect_directory_acl
        from sermax_windows_directory_handle import enumerate_stable_directory_handle
        from sermax_windows_update_area import (
            UpdateAreaInspection,
            validate_update_area_acl_policy,
        )

        acl = inspect_directory_acl(child_handle)
        contents = [
            entry
            for entry in enumerate_stable_directory_handle(child_handle)
            if entry.name not in {".", ".."}
        ]
        inspection = UpdateAreaInspection(
            handle=child_handle,
            metadata=metadata,
            acl_inspection=acl,
            directory_entries=contents,
        )
        result = validate_update_area_acl_policy(
            inspection,
            token_handle=token_handle,
            require_empty=require_empty,
        )
        if result.get("valid") is not True or result.get("mutated") is not False:
            raise PrivateAreaError(
                "A política ACL não confirmou o diretório recém-criado."
            )
        return result
    except PrivateAreaError:
        raise
    except Exception as exc:
        raise PrivateAreaError(
            f"O diretório foi criado, mas a validação ACL falhou: {exc}"
        ) from exc


def create_private_directory_component(
    parent_handle, component: str, *, _allow_staging_component: bool = False
):
    """Cria um diretório interno com DACL privada aplicada na própria criação.

    O pai deve permanecer aberto e conceder FILE_ADD_SUBDIRECTORY. Por padrão,
    o componente pertence à allowlist estrutural. A exceção privada de staging
    aceita um único componente validado vindo da árvore autenticada. O
    SECURITY_DESCRIPTOR self-relative é anexado a OBJECT_ATTRIBUTES durante
    NtCreateFile.
    Depois da criação, a função valida owner, DACL, trustees, identidade, estado
    vazio e direitos Authz pelo mesmo handle. Se a validação falhar, fecha o
    handle e preserva o diretório recém-criado para inspeção, sem gravar dados.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise PrivateAreaError("A criação exige Windows x64.")
    try:
        _validate_component(component)
    except Exception as exc:
        raise PrivateAreaError(f"Componente inválido: {exc}") from exc
    if not _allow_staging_component and component not in ALLOWED_PRIVATE_COMPONENTS:
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

    token = None
    close_token = None
    child_handle = None
    try:
        token, close_token, descriptor_buffer, _owner_sid = (
            _prepare_private_security_descriptor()
        )

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
        attributes.SecurityDescriptor = ctypes.cast(
            descriptor_buffer, ctypes.c_void_p
        )

        result_handle = wintypes.HANDLE()
        io_status = IO_STATUS_BLOCK()
        desired_access = (
            FILE_LIST_DIRECTORY
            | FILE_ADD_FILE
            | FILE_ADD_SUBDIRECTORY
            | FILE_READ_ATTRIBUTES
            | READ_CONTROL
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

        _validate_created_private_directory(child_handle, child, token)
        return child_handle
    except Exception as exc:
        if child_handle is not None:
            try:
                close_handle(child_handle)
            except Exception as close_error:
                if hasattr(exc, "add_note"):
                    exc.add_note(
                        f"Falha ao fechar handle do diretório após erro: {close_error}"
                    )
        if isinstance(exc, PrivateAreaError):
            raise
        raise PrivateAreaError(
            f"Falha ao criar diretório privado com ACL: {exc}"
        ) from exc
    finally:
        if token is not None and close_token is not None:
            active_error = sys.exc_info()[1]
            try:
                close_token(token)
            except Exception as close_error:
                if active_error is not None:
                    if hasattr(active_error, "add_note"):
                        active_error.add_note(
                            f"Falha ao fechar token após erro: {close_error}"
                        )
                else:
                    if child_handle is not None:
                        try:
                            close_handle(child_handle)
                        except Exception as handle_error:
                            if hasattr(close_error, "add_note"):
                                close_error.add_note(
                                    f"Falha ao fechar diretório após erro do token: {handle_error}"
                                )
                    raise PrivateAreaError(
                        f"Falha ao liberar token de criação: {close_error}"
                    ) from close_error


def create_staging_directory_component(parent_handle, component: str):
    """Cria diretório de pacote sob staging com a mesma ACL atômica.

    O componente deve vir de manifesto autenticado ou do gerador interno de
    identificador. A validação de componente único continua obrigatória.
    Esta função não aceita caminhos nem altera a allowlist dos diretórios
    estruturais (_update, staging, backups, journal, logs e locks).
    """
    return create_private_directory_component(
        parent_handle, component, _allow_staging_component=True
    )


def create_journal_directory_component(parent_handle, component: str):
    """Cria diretório de transação/journal com ACL privada explícita."""
    return create_private_directory_component(
        parent_handle, component, _allow_staging_component=True
    )


def create_backup_directory_component(parent_handle, component: str):
    """Cria raiz/subdiretório de backup com ACL explícita e nome de componente."""
    return create_private_directory_component(
        parent_handle, component, _allow_staging_component=True
    )


def validate_private_directory_handle(
    directory_handle, *, require_empty: bool = True
) -> dict[str, object]:
    """Revalida ACL/Authz de um diretório privado pelo handle retido.

    require_empty=True é obrigatório para uma nova área de operação. False
    permite diretórios estruturais persistentes, desde que o chamador valide
    separadamente o namespace interno e seus filhos.
    """
    if type(require_empty) is not bool:
        raise PrivateAreaError("require_empty deve ser booleano.")
    token = None
    close_token = None
    try:
        metadata = query_handle_metadata(directory_handle)
        if (
            not metadata["is_directory"]
            or metadata["is_reparse_point"]
            or metadata["delete_pending"]
        ):
            raise PrivateAreaError("O handle não representa diretório regular.")
        token, close_token, _descriptor_buffer, _owner_sid = (
            _prepare_private_security_descriptor()
        )
        policy = _validate_created_private_directory(
            directory_handle,
            metadata,
            token,
            require_empty=require_empty,
        )
        return {
            "valid": True,
            "metadata": metadata,
            "policy": policy,
            "mutated": False,
        }
    except PrivateAreaError:
        raise
    except Exception as exc:
        raise PrivateAreaError(
            f"Diretório privado não passou na validação ACL/Authz: {exc}"
        ) from exc
    finally:
        if token is not None and close_token is not None:
            try:
                close_token(token)
            except Exception as exc:
                active_error = sys.exc_info()[1]
                if active_error is not None:
                    if hasattr(active_error, "add_note"):
                        active_error.add_note(
                            f"Falha ao fechar token após validação privada: {exc}"
                        )
                else:
                    raise PrivateAreaError(
                        f"Falha ao fechar token após validação privada: {exc}"
                    ) from exc


def validate_empty_private_directory_handle(directory_handle) -> dict[str, object]:
    """Compatibilidade explícita: valida ACL/Authz e exige diretório vazio."""
    return validate_private_directory_handle(
        directory_handle, require_empty=True
    )



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
        if entry.name != "_update":
            raise PrivateAreaError("_update existente usa grafia não canônica.")
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



@dataclass
class ExistingPrivateAreaLayout:
    """Handles retidos de _update e das cinco áreas estruturais validadas."""

    update_handle: object
    directories: dict[str, object]
    metadata: dict[str, object]
    validation: dict[str, object]

    def close(self) -> None:
        errors = []
        for name in reversed(tuple(self.directories)):
            handle = self.directories[name]
            try:
                close_handle(handle)
            except Exception as exc:
                errors.append((name, exc))
            else:
                del self.directories[name]
        if self.update_handle is not None:
            try:
                close_handle(self.update_handle)
            except Exception as exc:
                errors.append(("_update", exc))
            else:
                self.update_handle = None
        if errors:
            details = "; ".join(f"{name}: {error}" for name, error in errors)
            raise PrivateAreaError(
                f"Falha ao fechar handles da área privada; handles pendentes preservados: {details}"
            )

    def __enter__(self):
        if self.update_handle is None:
            raise PrivateAreaError("Layout da área privada já foi encerrado.")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


_PRIVATE_LAYOUT_COMPONENTS = ("staging", "backups", "journal", "logs", "locks")
_LAYOUT_ACCESS = (
    FILE_LIST_DIRECTORY
    | FILE_ADD_FILE
    | FILE_ADD_SUBDIRECTORY
    | FILE_READ_ATTRIBUTES
    | READ_CONTROL
    | SYNCHRONIZE
)


def open_existing_private_area_layout(
    parent_handle, *, expected_owner_sid: str | None = None
) -> ExistingPrivateAreaLayout:
    """Abre e valida a estrutura persistente _update sem repará-la.

    Exige exatamente os diretórios staging, backups, journal, logs e locks.
    Cada handle é aberto relativamente ao pai enumerado, vinculado ao FileId
    de 128 bits e validado por ACL/Authz no mesmo handle. Todos os handles
    permanecem retidos no objeto retornado. Divergências fecham os handles
    abertos e abortam sem criar, remover ou alterar objetos.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise PrivateAreaError("A abertura da área privada exige Windows x64.")

    from sermax_windows_directory_handle import (
        enumerate_stable_directory_handle,
        open_verified_child_component,
    )
    import win32api
    import win32security

    parent_metadata = query_handle_metadata(parent_handle)
    if (
        not parent_metadata["is_directory"]
        or parent_metadata["is_reparse_point"]
        or parent_metadata["delete_pending"]
    ):
        raise PrivateAreaError("O handle pai não representa diretório regular.")

    update_handle = None
    child_handles: dict[str, object] = {}
    token = None
    result = None
    active_error = None
    try:
        parent_entries = enumerate_stable_directory_handle(parent_handle)
        matches = [
            entry for entry in parent_entries
            if entry.name.casefold() == "_update"
        ]
        if len(matches) != 1 or matches[0].name != "_update":
            raise PrivateAreaError(
                "_update ausente, ambíguo ou com grafia não canônica."
            )
        update_entry = matches[0]
        if not update_entry.is_directory or update_entry.is_reparse_point:
            raise PrivateAreaError("_update não é diretório comum.")

        update_handle = open_verified_child_component(
            parent_handle, update_entry, desired_access=_LAYOUT_ACCESS
        )
        update_metadata = query_handle_metadata(update_handle)
        if (
            not update_metadata["is_directory"]
            or update_metadata["is_reparse_point"]
            or update_metadata["delete_pending"]
            or update_metadata["volume_serial_number"]
            != parent_metadata["volume_serial_number"]
        ):
            raise PrivateAreaError("_update mudou de identidade ou volume.")

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
        )
        token_user = win32security.GetTokenInformation(
            token, win32security.TokenUser
        )[0]
        actual_owner_sid = win32security.ConvertSidToStringSid(token_user)
        if expected_owner_sid is not None and expected_owner_sid != actual_owner_sid:
            raise PrivateAreaError(
                "SID esperado diverge do SID do token real do processo."
            )

        update_validation = _validate_created_private_directory(
            update_handle, update_metadata, token, require_empty=False
        )
        if update_validation.get("valid") is not True:
            raise PrivateAreaError("ACL/Authz de _update não foi confirmada.")
        update_entries = tuple(
            entry
            for entry in enumerate_stable_directory_handle(update_handle)
            if entry.name not in {".", ".."}
        )
        observed_names = {entry.name for entry in update_entries}
        if observed_names != set(_PRIVATE_LAYOUT_COMPONENTS):
            raise PrivateAreaError(
                "A estrutura _update não contém exatamente staging, backups, "
                "journal, logs e locks."
            )

        entry_by_name = {entry.name: entry for entry in update_entries}
        child_validations: dict[str, dict[str, object]] = {}
        for component in _PRIVATE_LAYOUT_COMPONENTS:
            entry = entry_by_name[component]
            if not entry.is_directory or entry.is_reparse_point:
                raise PrivateAreaError(
                    f"A área estrutural {component} não é diretório regular."
                )
            child = open_verified_child_component(
                update_handle, entry, desired_access=_LAYOUT_ACCESS
            )
            child_handles[component] = child
            metadata = query_handle_metadata(child)
            if (
                not metadata["is_directory"]
                or metadata["is_reparse_point"]
                or metadata["delete_pending"]
                or metadata["volume_serial_number"]
                != update_metadata["volume_serial_number"]
            ):
                raise PrivateAreaError(
                    f"A área estrutural {component} mudou de identidade ou volume."
                )

            child_validation = _validate_created_private_directory(
                child, metadata, token, require_empty=False
            )
            child_entries = tuple(
                child_entry
                for child_entry in enumerate_stable_directory_handle(child)
                if child_entry.name not in {".", ".."}
            )
            for child_entry in child_entries:
                try:
                    _validate_component(child_entry.name)
                except Exception as exc:
                    raise PrivateAreaError(
                        f"Nome inválido em {component}: {child_entry.name!r}"
                    ) from exc
                if child_entry.is_reparse_point:
                    raise PrivateAreaError(
                        f"Reparse point encontrado dentro de {component}."
                    )
                if component == "staging" and (
                    not child_entry.is_directory
                    or not re.fullmatch(r"stage-[0-9a-f]{24}", child_entry.name)
                ):
                    raise PrivateAreaError(
                        "A área staging contém objeto que não corresponde a "
                        "um diretório de staging exclusivo."
                    )
            if child_validation.get("valid") is not True:
                raise PrivateAreaError(
                    f"ACL/Authz da área {component} não foi confirmada."
                )
            child_validations[component] = child_validation

        result = ExistingPrivateAreaLayout(
            update_handle=update_handle,
            directories=child_handles,
            metadata=update_metadata,
            validation={
                "valid": True,
                "owner_sid": actual_owner_sid,
                "update": update_validation,
                "directories": child_validations,
                "mutated": False,
            },
        )
        update_handle = None
        child_handles = {}
    except Exception as exc:
        active_error = exc
        for name in reversed(tuple(child_handles)):
            try:
                close_handle(child_handles[name])
            except Exception as close_error:
                if hasattr(exc, "add_note"):
                    exc.add_note(
                        f"Falha ao fechar handle {name} após erro: {close_error}"
                    )
        child_handles.clear()
        if update_handle is not None:
            try:
                close_handle(update_handle)
            except Exception as close_error:
                if hasattr(exc, "add_note"):
                    exc.add_note(
                        f"Falha ao fechar handle _update após erro: {close_error}"
                    )
            update_handle = None
        if isinstance(exc, PrivateAreaError):
            raise
        raise PrivateAreaError(
            f"A estrutura persistente _update não passou na validação: {exc}"
        ) from exc
    finally:
        if token is not None:
            try:
                win32api.CloseHandle(token)
            except Exception as close_error:
                if result is not None:
                    try:
                        result.close()
                    finally:
                        raise PrivateAreaError(
                            f"Falha ao fechar token após validação: {close_error}"
                        ) from close_error
                if active_error is not None and hasattr(active_error, "add_note"):
                    active_error.add_note(
                        f"Falha ao fechar token após erro: {close_error}"
                    )
                elif active_error is None:
                    raise PrivateAreaError(
                        f"Falha ao fechar token após validação: {close_error}"
                    ) from close_error

    if result is None:
        raise PrivateAreaError("A validação não produziu layout utilizável.")
    return result
