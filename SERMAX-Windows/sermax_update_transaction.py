"""Preparação transacional de release SERMAX, sem instalação ativa.

Coordena manifesto já autenticado, validação do pacote, backup, journal e
staging por handles. Não substitui arquivos ativos nem executa código da release.
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os
from ctypes import wintypes

from sermax_update_manifest import ValidatedManifest
from sermax_windows_handle_io import close_handle, query_handle_metadata
from sermax_update_package import VerifiedPackage, validate_release_archive
from sermax_update_staging import HandleStagedRelease, stage_verified_release_by_handle
from sermax_windows_backup import BackupSnapshot, backup_existing_files_by_handle
from sermax_windows_journal import (
    JournalSession,
    create_journal_transaction_by_handle,
)


class TransactionPreparationError(RuntimeError):
    """Falha na preparação; journal e áreas parciais são preservados."""


@dataclass
class PreparedUpdateTransaction:
    """Recursos abertos de uma release pronta para futura fase de instalação."""

    package: VerifiedPackage
    journal: JournalSession
    backup: BackupSnapshot
    staging: HandleStagedRelease
    manifest: ValidatedManifest

    @property
    def transaction_id(self) -> str:
        return self.journal.transaction_id

    def begin_install(self) -> dict[str, object]:
        """Registra INSTALL_STARTED; não executa instalação nem altera arquivos."""
        events = self.journal.read_events()
        if not events or events[-1]["event"] != "STAGING_COMPLETE":
            raise TransactionPreparationError(
                "A transação não está pronta para iniciar a fase de instalação."
            )
        return self.journal.append_event("INSTALL_STARTED", {})

    def close(self) -> None:
        errors = []
        for resource in (self.staging, self.backup, self.journal):
            try:
                resource.close()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise TransactionPreparationError(
                "Falha ao fechar recursos da transação: "
                + "; ".join(map(str, errors))
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def prepare_update_transaction_by_handle(
    archive_bytes: bytes,
    manifest: ValidatedManifest,
    *,
    active_root_handle,
    backups_parent_handle,
    staging_parent_handle,
    journal_parent_handle,
) -> PreparedUpdateTransaction:
    """Valida pacote, registra PREPARED, cria backup e staging e encadeia eventos.

    manifest deve ser o objeto retornado por validate_signed_manifest, com
    verificador de assinatura vinculado a chave pública confiável. Esta função
    não recebe nem consulta caminhos absolutos.

    Em caso de falha, áreas parciais são mantidas para inspeção. O journal
    recebe RECOVERY_REQUIRED quando sua cadeia permite. Nenhum arquivo ativo
    é escrito, removido ou substituído.
    """
    if not isinstance(manifest, ValidatedManifest):
        raise TransactionPreparationError(
            "Manifesto precisa ser ValidatedManifest autenticado."
        )

    try:
        verified_package = validate_release_archive(archive_bytes, manifest)
    except Exception as exc:
        raise TransactionPreparationError(
            f"Pacote não passou na validação integral: {exc}"
        ) from exc

    journal = None
    backup = None
    staging = None
    try:
        journal = create_journal_transaction_by_handle(journal_parent_handle)
        journal.append_event(
            "PREPARED",
            {
                "release_version": manifest.release_version,
                "manifest_sha256": manifest.manifest_sha256,
            },
        )

        backup = backup_existing_files_by_handle(
            active_root_handle,
            backups_parent_handle,
            manifest,
        )
        backup_hash = (
            backup.catalog["sha256"] if backup.catalog is not None else None
        )
        journal.append_event(
            "BACKUP_COMPLETE",
            {
                "backup_component": backup.component,
                "catalog_sha256": backup_hash,
            },
        )

        staging = stage_verified_release_by_handle(
            archive_bytes,
            manifest,
            staging_parent_handle=staging_parent_handle,
        )
        journal.append_event(
            "STAGING_COMPLETE",
            {
                "staging_component": staging.component,
                "archive_sha256": verified_package.archive_sha256,
            },
        )

        return PreparedUpdateTransaction(
            package=verified_package,
            journal=journal,
            backup=backup,
            staging=staging,
            manifest=manifest,
        )
    except Exception as exc:
        if journal is not None:
            try:
                events = journal.read_events()
                if events and events[-1]["event"] not in {
                    "COMMITTED", "ROLLED_BACK", "RECOVERY_REQUIRED"
                }:
                    journal.append_event(
                        "RECOVERY_REQUIRED",
                        {"reason": f"Falha na preparação: {exc}"[:2000]},
                    )
            except Exception:
                pass
        for resource in (staging, backup, journal):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
        if isinstance(exc, TransactionPreparationError):
            raise
        transaction_id = journal.transaction_id if journal is not None else None
        raise TransactionPreparationError(
            f"Preparação interrompida; áreas parciais preservadas. "
            f"Transação={transaction_id or 'não criada'}: {exc}"
        ) from exc


_FILE_RENAME_INFORMATION_CLASS = 10
_FILE_LIST_DIRECTORY = 0x00000001
_FILE_TRAVERSE = 0x00000020
_FILE_READ_ATTRIBUTES = 0x00000080
_FILE_READ_DATA = 0x00000001
_FILE_DELETE = 0x00010000
_FILE_READ_CONTROL = 0x00020000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004


class _FILE_RENAME_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ReplaceIfExists", wintypes.BOOLEAN),
        ("RootDirectory", wintypes.HANDLE),
        ("FileNameLength", wintypes.DWORD),
        ("FileName", wintypes.WCHAR * 1),
    ]


def _rename_handle_to_parent(source_handle, destination_parent_handle, leaf_name: str, *, replace: bool) -> None:
    from sermax_windows_handle_io import _validate_component
    from sermax_windows_handle_abi import IO_STATUS_BLOCK

    _validate_component(leaf_name)
    if type(replace) is not bool:
        raise TransactionPreparationError("replace precisa ser booleano.")
    encoded_name = leaf_name.encode("utf-16-le", errors="strict")
    name_offset = _FILE_RENAME_INFORMATION.FileName.offset
    storage_size = ctypes.sizeof(_FILE_RENAME_INFORMATION) + len(encoded_name)
    storage = ctypes.create_string_buffer(storage_size)
    info = ctypes.cast(storage, ctypes.POINTER(_FILE_RENAME_INFORMATION)).contents
    info.ReplaceIfExists = 1 if replace else 0
    info.RootDirectory = (
        destination_parent_handle.value
        if isinstance(destination_parent_handle, ctypes.c_void_p)
        else destination_parent_handle
    )
    info.FileNameLength = len(encoded_name)
    ctypes.memmove(
        ctypes.addressof(storage) + name_offset,
        encoded_name,
        len(encoded_name),
    )

    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    set_info = ntdll.NtSetInformationFile
    set_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(IO_STATUS_BLOCK),
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.c_int,
    ]
    set_info.restype = ctypes.c_long
    native = source_handle.value if isinstance(source_handle, ctypes.c_void_p) else source_handle
    io_status = IO_STATUS_BLOCK()
    status = set_info(
        native,
        ctypes.byref(io_status),
        ctypes.byref(storage),
        storage_size,
        _FILE_RENAME_INFORMATION_CLASS,
    )
    if status < 0:
        raise TransactionPreparationError(
            "NtSetInformationFile(FileRenameInformation) falhou, "
            f"NTSTATUS=0x{status & 0xFFFFFFFF:08X}."
        )


def _open_active_parent(root_handle, relative_parent: str, expected_volume: int):
    from sermax_windows_directory_handle import (
        enumerate_stable_directory_handle,
        open_verified_child_component,
    )
    opened = []
    current = root_handle
    if not relative_parent:
        return current, opened
    try:
        for component in relative_parent.split("/"):
            matches = [
                entry for entry in enumerate_stable_directory_handle(current)
                if entry.name.casefold() == component.casefold()
                and entry.name not in {".", ".."}
            ]
            if len(matches) != 1 or matches[0].name != component:
                raise TransactionPreparationError(
                    f"Diretório pai ausente ou ambíguo: {relative_parent}"
                )
            entry = matches[0]
            if not entry.is_directory or entry.is_reparse_point:
                raise TransactionPreparationError(
                    f"Diretório pai não é regular: {relative_parent}"
                )
            child = open_verified_child_component(
                current,
                entry,
                desired_access=(
                    _FILE_LIST_DIRECTORY | _FILE_TRAVERSE
                    | _FILE_READ_ATTRIBUTES | _FILE_READ_CONTROL
                ),
                share_access=(
                    _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE
                ),
            )
            metadata = query_handle_metadata(child)
            if (
                not metadata["is_directory"]
                or metadata["is_reparse_point"]
                or metadata["delete_pending"]
                or metadata["volume_serial_number"] != expected_volume
            ):
                close_handle(child)
                raise TransactionPreparationError(
                    f"Diretório pai falhou na validação: {relative_parent}"
                )
            opened.append(child)
            current = child
        return current, opened
    except Exception:
        for handle in reversed(opened):
            try:
                close_handle(handle)
            except Exception:
                pass
        raise


def _find_active_leaf(parent_handle, leaf_name: str):
    from sermax_windows_directory_handle import enumerate_stable_directory_handle
    matches = [
        entry for entry in enumerate_stable_directory_handle(parent_handle)
        if entry.name.casefold() == leaf_name.casefold()
        and entry.name not in {".", ".."}
    ]
    if len(matches) > 1:
        raise TransactionPreparationError(f"Destino ambíguo: {leaf_name}")
    if not matches:
        return None
    if matches[0].name != leaf_name or matches[0].is_reparse_point or matches[0].is_directory:
        raise TransactionPreparationError(f"Destino não é arquivo regular canônico: {leaf_name}")
    return matches[0]


def install_prepared_update_by_handle(
    prepared: PreparedUpdateTransaction,
    active_root_handle,
    backups_parent_handle,
) -> dict[str, object]:
    """Instala a release preparada com renomeação atômica por handles.

    Exige INSTALL_STARTED persistido. Confere novamente backup, staging e
    destinos. Move cada arquivo do staging para o diretório ativo usando
    FileRenameInfoEx, registrando FILE_REPLACED após confirmar FileId e SHA-256.
    Ao final relê todos os destinos e grava COMMITTED.

    Diretórios pais precisam existir. A função não cria diretórios ativos.
    Em falha parcial, tenta registrar RECOVERY_REQUIRED; o backup permanece
    disponível para rollback. Não usa caminhos absolutos.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise TransactionPreparationError("Instalação por handles exige Windows x64.")
    if not isinstance(prepared, PreparedUpdateTransaction):
        raise TransactionPreparationError("Objeto de transação preparada inválido.")
    events = prepared.journal.read_events()
    if not events or events[-1]["event"] not in {"INSTALL_STARTED", "FILE_REPLACED"}:
        raise TransactionPreparationError("Journal precisa estar em INSTALL_STARTED/FILE_REPLACED.")

    from sermax_windows_backup import (
        BackupError,
        NativeHandleReader,
        _hash_and_rewind,
        _open_source_file,
        verify_backup_by_handle,
    )
    from sermax_windows_directory_handle import open_verified_child_component

    active_meta = query_handle_metadata(active_root_handle)
    stage_meta = query_handle_metadata(prepared.staging.root_handle)
    if (
        not active_meta["is_directory"] or active_meta["is_reparse_point"]
        or active_meta["delete_pending"]
        or not stage_meta["is_directory"] or stage_meta["is_reparse_point"]
        or stage_meta["delete_pending"]
        or active_meta["volume_serial_number"] != stage_meta["volume_serial_number"]
    ):
        raise TransactionPreparationError("Raiz ativa/staging inválida ou em volumes distintos.")

    backup_event = next(
        (item for item in events if item["event"] == "BACKUP_COMPLETE"), None
    )
    if backup_event is None:
        raise TransactionPreparationError("Journal sem BACKUP_COMPLETE.")
    backup_payload = backup_event["payload"]
    expected_backup_component = backup_payload["backup_component"]
    expected_backup_hash = backup_payload["catalog_sha256"]
    has_replacements = any(item.action == "replace" for item in prepared.manifest.files)
    if has_replacements != (expected_backup_component is not None):
        raise TransactionPreparationError("Cobertura do backup diverge das ações do manifesto.")
    if expected_backup_component is not None:
        # O handle da raiz criado durante o backup mantém acesso de escrita
        # aberto. Fechá-lo permite a reabertura independente com share mode
        # restrito, sem perder os arquivos persistidos.
        prepared.backup.close()
        verify_backup_by_handle(
            backups_parent_handle,
            expected_backup_component,
            expected_catalog_sha256=expected_backup_hash,
        )

    stage_results = {
        item.path: result
        for item, result in zip(prepared.manifest.files, prepared.staging.files)
    }
    if len(stage_results) != len(prepared.manifest.files):
        raise TransactionPreparationError("Inventário do staging diverge do manifesto.")

    replaced_events = {
        item["payload"]["path"]: item["payload"]
        for item in events if item["event"] == "FILE_REPLACED"
    }
    install_intents = {
        item["payload"]["path"]: item["payload"]
        for item in events if item["event"] == "FILE_INSTALL_INTENT"
    }
    installed_count = 0
    already_installed_count = 0
    try:
        # Preflight completo antes da primeira renomeação.
        for item in prepared.manifest.files:
            staged_result = stage_results[item.path]
            parent_path, leaf_name = (
                item.path.rsplit("/", 1) if "/" in item.path else ("", item.path)
            )
            parent_handle, parent_handles = _open_active_parent(
                active_root_handle, parent_path, active_meta["volume_serial_number"]
            )
            staged_handle = None
            staged_parents = []
            try:
                entry = _find_active_leaf(parent_handle, leaf_name)
                staged_handle, staged_parents, staged_file_meta = _open_source_file(
                    prepared.staging.root_handle,
                    item.path,
                    active_meta["volume_serial_number"],
                    desired_access=_FILE_READ_DATA | _FILE_READ_CONTROL | _FILE_DELETE,
                )
                if staged_handle is None:
                    if entry is None or entry.file_id.lower() != staged_result["file_id_128"].lower():
                        raise TransactionPreparationError(
                            f"Staging ausente sem FileId instalado correspondente: {item.path}"
                        )
                    active_file = open_verified_child_component(
                        parent_handle,
                        entry,
                        desired_access=_FILE_READ_DATA | _FILE_READ_CONTROL,
                    )
                    try:
                        active_file_meta = query_handle_metadata(active_file)
                        active_hash = _hash_and_rewind(
                            NativeHandleReader(active_file), item.size
                        )
                        if (
                            active_file_meta["end_of_file"] != item.size
                            or active_hash != item.sha256
                        ):
                            raise TransactionPreparationError(
                                f"Arquivo ativo não corresponde ao staging movido: {item.path}"
                            )
                    finally:
                        close_handle(active_file)
                else:
                    if staged_file_meta is None:
                        raise TransactionPreparationError(
                            f"Metadados do staging ausentes: {item.path}"
                        )
                    staged_hash = _hash_and_rewind(
                        NativeHandleReader(staged_handle), item.size
                    )
                    if (
                        staged_file_meta["file_id_128"].lower()
                        != staged_result["file_id_128"].lower()
                        or staged_file_meta["end_of_file"] != item.size
                        or staged_hash != item.sha256
                    ):
                        raise TransactionPreparationError(
                            f"Arquivo de staging diverge do manifesto: {item.path}"
                        )

                    if item.action == "create" and entry is not None:
                        raise TransactionPreparationError(
                            f"Destino create já existe: {item.path}"
                        )
                    if item.action == "replace" and entry is None:
                        raise TransactionPreparationError(
                            f"Destino replace ausente: {item.path}"
                        )
                    if entry is not None:
                        target = open_verified_child_component(
                            parent_handle,
                            entry,
                            desired_access=(
                                _FILE_READ_DATA | _FILE_READ_CONTROL | _FILE_DELETE
                            ),
                        )
                        try:
                            target_meta = query_handle_metadata(target)
                            if (
                                target_meta["number_of_links"] != 1
                                or target_meta["volume_serial_number"] != active_meta["volume_serial_number"]
                                or target_meta["attributes"] & 0x00000001
                            ):
                                raise TransactionPreparationError(
                                    f"Destino possui hardlink, volume divergente ou atributo somente leitura: {item.path}"
                                )
                        finally:
                            close_handle(target)
            finally:
                if staged_handle is not None:
                    _close_handles(staged_handle, staged_parents)
                for handle in reversed(parent_handles):
                    close_handle(handle)

        # Instalação arquivo a arquivo. FileId do staging é preservado pela renomeação.
        for item in prepared.manifest.files:
            staged_result = stage_results[item.path]
            expected_file_id = staged_result["file_id_128"].lower()
            expected_hash = item.sha256
            if item.path in replaced_events and (
                replaced_events[item.path]["sha256"] != expected_hash
                or replaced_events[item.path]["file_id_128"].lower() != expected_file_id
            ):
                raise TransactionPreparationError(
                    f"Journal registra FileId/hash divergente para {item.path}."
                )

            parent_path, leaf_name = (
                item.path.rsplit("/", 1) if "/" in item.path else ("", item.path)
            )
            parent_handle, parent_handles = _open_active_parent(
                active_root_handle, parent_path, active_meta["volume_serial_number"]
            )
            staged_handle = None
            staged_parents = []
            try:
                current_entry = _find_active_leaf(parent_handle, leaf_name)
                if current_entry is not None and current_entry.file_id.lower() == expected_file_id:
                    current_handle = open_verified_child_component(
                        parent_handle,
                        current_entry,
                        desired_access=_FILE_READ_DATA | _FILE_READ_CONTROL,
                    )
                    try:
                        current_meta = query_handle_metadata(current_handle)
                        current_hash = _hash_and_rewind(
                            NativeHandleReader(current_handle), item.size
                        )
                        if (
                            current_meta["end_of_file"] != item.size
                            or current_hash != expected_hash
                        ):
                            raise TransactionPreparationError(
                                f"Arquivo movido para destino diverge: {item.path}"
                            )
                    finally:
                        close_handle(current_handle)
                    intent = install_intents.get(item.path)
                    if intent is None:
                        intent = {
                            "path": item.path,
                            "sha256": expected_hash,
                            "file_id_128": expected_file_id,
                        }
                        prepared.journal.append_event(
                            "FILE_INSTALL_INTENT", intent
                        )
                        install_intents[item.path] = intent
                    elif (
                        intent["sha256"] != expected_hash
                        or intent["file_id_128"].lower() != expected_file_id
                    ):
                        raise TransactionPreparationError(
                            f"Intenção de instalação diverge do staging: {item.path}"
                        )
                    if item.path not in replaced_events:
                        prepared.journal.append_event(
                            "FILE_REPLACED",
                            {
                                "path": item.path,
                                "sha256": expected_hash,
                                "file_id_128": expected_file_id,
                            },
                        )
                    already_installed_count += 1
                    continue

                staged_handle, staged_parents, staged_file_meta = _open_source_file(
                    prepared.staging.root_handle,
                    item.path,
                    active_meta["volume_serial_number"],
                    desired_access=_FILE_READ_DATA | _FILE_READ_CONTROL | _FILE_DELETE,
                )
                if staged_handle is None or staged_file_meta is None:
                    raise TransactionPreparationError(
                        f"Staging ausente e FileId ativo não corresponde: {item.path}"
                    )
                if staged_file_meta["file_id_128"].lower() != expected_file_id:
                    raise TransactionPreparationError(
                        f"FileId do staging mudou: {item.path}"
                    )

                intent = install_intents.get(item.path)
                if intent is None:
                    intent = {
                        "path": item.path,
                        "sha256": expected_hash,
                        "file_id_128": expected_file_id,
                    }
                    prepared.journal.append_event("FILE_INSTALL_INTENT", intent)
                    install_intents[item.path] = intent
                elif (
                    intent["sha256"] != expected_hash
                    or intent["file_id_128"].lower() != expected_file_id
                ):
                    raise TransactionPreparationError(
                        f"Intenção de instalação diverge do staging: {item.path}"
                    )

                if item.action == "replace":
                    if current_entry is None:
                        raise TransactionPreparationError(
                            f"Destino replace desapareceu antes da renomeação: {item.path}"
                        )
                    _rename_handle_to_parent(
                        staged_handle, parent_handle, leaf_name, replace=True
                    )
                else:
                    if current_entry is not None:
                        raise TransactionPreparationError(
                            f"Destino create surgiu antes da renomeação: {item.path}"
                        )
                    _rename_handle_to_parent(
                        staged_handle, parent_handle, leaf_name, replace=False
                    )

                moved_meta = query_handle_metadata(staged_handle)
                moved_hash = _hash_and_rewind(
                    NativeHandleReader(staged_handle), item.size
                )
                if (
                    moved_meta["file_id_128"].lower() != expected_file_id
                    or moved_meta["end_of_file"] != item.size
                    or moved_hash != expected_hash
                    or moved_meta["number_of_links"] != 1
                ):
                    raise TransactionPreparationError(
                        f"Arquivo renomeado falhou na verificação: {item.path}"
                    )

                final_entry = _find_active_leaf(parent_handle, leaf_name)
                if final_entry is None or final_entry.file_id.lower() != expected_file_id:
                    raise TransactionPreparationError(
                        f"Destino não aponta para o FileId instalado: {item.path}"
                    )
                prepared.journal.append_event(
                    "FILE_REPLACED",
                    {
                        "path": item.path,
                        "sha256": expected_hash,
                        "file_id_128": expected_file_id,
                    },
                )
                installed_count += 1
            finally:
                if staged_handle is not None:
                    _close_handles(staged_handle, staged_parents)
                for handle in reversed(parent_handles):
                    close_handle(handle)

        # Verificação final da árvore ativa antes de COMMITTED.
        for item in prepared.manifest.files:
            active_handle, active_parents, active_file_meta = _open_source_file(
                active_root_handle,
                item.path,
                active_meta["volume_serial_number"],
            )
            if active_handle is None or active_file_meta is None:
                raise TransactionPreparationError(
                    f"Arquivo final ausente na instalação: {item.path}"
                )
            try:
                final_hash = _hash_and_rewind(
                    NativeHandleReader(active_handle), item.size
                )
                if (
                    active_file_meta["end_of_file"] != item.size
                    or final_hash != item.sha256
                    or active_file_meta["number_of_links"] != 1
                ):
                    raise TransactionPreparationError(
                        f"Verificação final falhou: {item.path}"
                    )
            finally:
                _close_handles(active_handle, active_parents)

        prepared.journal.append_event(
            "COMMITTED",
            {"release_version": prepared.manifest.release_version},
        )
        return {
            "valid": True,
            "transaction_id": prepared.transaction_id,
            "release_version": prepared.manifest.release_version,
            "installed_count": installed_count,
            "already_installed_count": already_installed_count,
            "file_count": len(prepared.manifest.files),
            "journal_last_event": "COMMITTED",
        }
    except Exception as exc:
        try:
            current = prepared.journal.read_events()
            if current and current[-1]["event"] not in {
                "COMMITTED", "ROLLED_BACK", "RECOVERY_REQUIRED"
            }:
                prepared.journal.append_event(
                    "RECOVERY_REQUIRED",
                    {"reason": f"Falha na instalação: {exc}"[:2000]},
                )
        except Exception:
            pass
        if isinstance(exc, TransactionPreparationError):
            raise
        raise TransactionPreparationError(
            f"Instalação interrompida; preserve backup e journal: {exc}"
        ) from exc


def _close_handles(file_handle, directory_handles) -> None:
    errors = []
    if file_handle is not None:
        try:
            close_handle(file_handle)
        except Exception as exc:
            errors.append(exc)
    for handle in reversed(directory_handles):
        try:
            close_handle(handle)
        except Exception as exc:
            errors.append(exc)
    if errors:
        raise TransactionPreparationError(
            "Falha ao fechar handles: " + "; ".join(map(str, errors))
        )


def rollback_prepared_update_by_handle(
    prepared: PreparedUpdateTransaction,
    active_root_handle,
    backups_parent_handle,
) -> dict[str, object]:
    """Executa rollback em sandbox usando FileId/hash e journal append-only.

    Remove somente destinos create comprovadamente instalados pela transação.
    Restaura destinos replace pelo backup autenticado. Exige recursos da
    transação ainda abertos; recuperação após reinício do processo permanece
    uma etapa separada.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise TransactionPreparationError("Rollback por handles exige Windows x64.")
    if not isinstance(prepared, PreparedUpdateTransaction):
        raise TransactionPreparationError("Objeto de transação preparada inválido.")
    events = prepared.journal.read_events()
    if not events or events[-1]["event"] not in {
        "INSTALL_STARTED", "FILE_REPLACED", "RECOVERY_REQUIRED",
        "ROLLBACK_STARTED", "FILE_REMOVED", "FILE_RESTORED",
    }:
        raise TransactionPreparationError("Journal não está em estado recuperável.")
    if events[-1]["event"] != "ROLLBACK_STARTED" and events[-1]["event"] not in {
        "FILE_REMOVED", "FILE_RESTORED",
    }:
        prepared.journal.append_event(
            "ROLLBACK_STARTED", {"reason": "Rollback solicitado pelo orquestrador"}
        )

    from sermax_windows_backup import (
        NativeHandleReader,
        _hash_and_rewind,
        restore_backup_files_by_handle,
        verify_backup_by_handle,
    )
    from sermax_windows_directory_handle import open_verified_child_component

    active_meta = query_handle_metadata(active_root_handle)
    if (
        not active_meta["is_directory"] or active_meta["is_reparse_point"]
        or active_meta["delete_pending"]
    ):
        raise TransactionPreparationError("Raiz ativa inválida para rollback.")

    try:
        journal_events = prepared.journal.read_events()
        replaced = {
            item["payload"]["path"]: item["payload"]
            for item in journal_events if item["event"] == "FILE_REPLACED"
        }
        install_intents = {
            item["payload"]["path"]: item["payload"]
            for item in journal_events if item["event"] == "FILE_INSTALL_INTENT"
        }
        removed = {
            item["payload"]["path"]: item["payload"]
            for item in journal_events if item["event"] == "FILE_REMOVED"
        }

        removed_count = 0
        already_removed_count = 0
        for item in prepared.manifest.files:
            if item.action != "create":
                continue
            evidence = replaced.get(item.path) or install_intents.get(item.path)
            if evidence is None:
                continue
            expected_id = evidence["file_id_128"].lower()
            if evidence["sha256"] != item.sha256:
                raise TransactionPreparationError(
                    f"Journal create diverge do manifesto: {item.path}"
                )
            parent_path, leaf_name = (
                item.path.rsplit("/", 1) if "/" in item.path else ("", item.path)
            )
            parent_handle, parent_handles = _open_active_parent(
                active_root_handle, parent_path, active_meta["volume_serial_number"]
            )
            target_handle = None
            try:
                entry = _find_active_leaf(parent_handle, leaf_name)
                if entry is None:
                    if item.path in removed:
                        if (
                            removed[item.path]["file_id_128"].lower() != expected_id
                            or removed[item.path]["sha256"] != item.sha256
                        ):
                            raise TransactionPreparationError(
                                f"FILE_REMOVED diverge do registro de instalação: {item.path}"
                            )
                        already_removed_count += 1
                    elif item.path in replaced:
                        prepared.journal.append_event(
                            "FILE_REMOVED",
                            {
                                "path": item.path,
                                "sha256": item.sha256,
                                "file_id_128": expected_id,
                            },
                        )
                        already_removed_count += 1
                    # Uma intenção sem FILE_REPLACED e destino ausente indica
                    # que a renomeação ainda não ocorreu. Não inventar remoção.
                    continue

                target_handle = open_verified_child_component(
                    parent_handle,
                    entry,
                    desired_access=(
                        _FILE_READ_DATA | _FILE_READ_CONTROL | _FILE_DELETE
                    ),
                )
                metadata = query_handle_metadata(target_handle)
                digest = _hash_and_rewind(
                    NativeHandleReader(target_handle), item.size
                )
                if (
                    metadata["is_directory"] or metadata["is_reparse_point"]
                    or metadata["delete_pending"]
                    or metadata["number_of_links"] != 1
                    or metadata["volume_serial_number"] != active_meta["volume_serial_number"]
                    or metadata["file_id_128"].lower() != expected_id
                    or metadata["end_of_file"] != item.size
                    or digest != item.sha256
                    or metadata["attributes"] & 0x00000001
                ):
                    raise TransactionPreparationError(
                        f"Arquivo create não corresponde à identidade instalada: {item.path}"
                    )

                class _FILE_DISPOSITION_INFO(ctypes.Structure):
                    _fields_ = [("DeleteFile", ctypes.c_ubyte)]

                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                set_info = kernel32.SetFileInformationByHandle
                set_info.argtypes = [
                    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                ]
                set_info.restype = wintypes.BOOL
                native = (
                    target_handle.value
                    if isinstance(target_handle, ctypes.c_void_p)
                    else target_handle
                )
                disposition = _FILE_DISPOSITION_INFO(1)
                if not set_info(
                    native, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)
                ):
                    raise TransactionPreparationError(
                        f"Marcação de exclusão por handle falhou para {item.path}, "
                        f"WinError={ctypes.get_last_error()}."
                    )
                close_handle(target_handle)
                target_handle = None
                if _find_active_leaf(parent_handle, leaf_name) is not None:
                    raise TransactionPreparationError(
                        f"Destino continua presente após exclusão: {item.path}"
                    )
                prepared.journal.append_event(
                    "FILE_REMOVED",
                    {
                        "path": item.path,
                        "sha256": item.sha256,
                        "file_id_128": expected_id,
                    },
                )
                removed_count += 1
            finally:
                if target_handle is not None:
                    close_handle(target_handle)
                for handle in reversed(parent_handles):
                    close_handle(handle)

        backup_events = [
            event for event in prepared.journal.read_events()
            if event["event"] == "BACKUP_COMPLETE"
        ]
        if not backup_events:
            raise TransactionPreparationError("Journal sem BACKUP_COMPLETE.")
        backup_component = backup_events[-1]["payload"]["backup_component"]
        replacement_items = [
            item for item in prepared.manifest.files if item.action == "replace"
        ]
        restored = {"restored_count": 0, "already_restored_count": 0}
        if replacement_items:
            if backup_component is None:
                raise TransactionPreparationError("Backup ausente para ações replace.")
            if prepared.backup.root_handle is not None:
                prepared.backup.close()
            backup_verification = verify_backup_by_handle(
                backups_parent_handle,
                backup_component,
                expected_catalog_sha256=backup_events[-1]["payload"]["catalog_sha256"],
            )
            original_ids = backup_verification.get("source_file_ids", {})
            for item in replacement_items:
                original_id = original_ids.get(item.path)
                intent = install_intents.get(item.path) or replaced.get(item.path)
                expected_ids = {
                    value.lower() for value in (
                        original_id,
                        intent["file_id_128"] if intent is not None else None,
                    ) if isinstance(value, str)
                }
                if not expected_ids:
                    raise TransactionPreparationError(
                        f"Backup não contém FileId original para {item.path}"
                    )
                parent_path, leaf_name = (
                    item.path.rsplit("/", 1) if "/" in item.path else ("", item.path)
                )
                parent_handle, parent_handles = _open_active_parent(
                    active_root_handle, parent_path, active_meta["volume_serial_number"]
                )
                target_handle = None
                try:
                    entry = _find_active_leaf(parent_handle, leaf_name)
                    if entry is None:
                        if item.path not in replaced:
                            raise TransactionPreparationError(
                                f"Destino replace ausente sem FILE_REPLACED confirmado: {item.path}"
                            )
                        continue
                    target_handle = open_verified_child_component(
                        parent_handle,
                        entry,
                        desired_access=_FILE_READ_DATA | _FILE_READ_CONTROL,
                    )
                    target_meta = query_handle_metadata(target_handle)
                    if (
                        target_meta["is_directory"]
                        or target_meta["is_reparse_point"]
                        or target_meta["delete_pending"]
                        or target_meta["number_of_links"] != 1
                        or target_meta["volume_serial_number"] != active_meta["volume_serial_number"]
                        or target_meta["file_id_128"].lower() not in expected_ids
                    ):
                        raise TransactionPreparationError(
                            f"Destino replace não corresponde ao FileId original ou à intenção: {item.path}"
                        )
                finally:
                    if target_handle is not None:
                        close_handle(target_handle)
                    for handle in reversed(parent_handles):
                        close_handle(handle)
            restored = restore_backup_files_by_handle(
                active_root_handle,
                backups_parent_handle,
                backup_component,
                prepared.journal,
            )

        final_events = prepared.journal.read_events()
        restored_paths = {
            event["payload"]["path"]
            for event in final_events if event["event"] == "FILE_RESTORED"
        }
        removed_paths = {
            event["payload"]["path"]
            for event in final_events if event["event"] == "FILE_REMOVED"
        }
        for item in prepared.manifest.files:
            if item.action == "replace" and item.path not in restored_paths:
                raise TransactionPreparationError(
                    f"Rollback não confirmou restauração: {item.path}"
                )
            if item.action == "create" and item.path in replaced and item.path not in removed_paths:
                raise TransactionPreparationError(
                    f"Rollback não confirmou remoção: {item.path}"
                )

        prepared.journal.append_event(
            "ROLLED_BACK", {"reason": "Todos os destinos foram verificados"}
        )
        return {
            "valid": True,
            "transaction_id": prepared.transaction_id,
            "removed_count": removed_count,
            "already_removed_count": already_removed_count,
            "restored_count": restored.get("restored_count", 0),
            "already_restored_count": restored.get("already_restored_count", 0),
            "journal_last_event": "ROLLED_BACK",
        }
    except Exception as exc:
        try:
            current = prepared.journal.read_events()
            if current and current[-1]["event"] not in {"COMMITTED", "ROLLED_BACK"}:
                prepared.journal.append_event(
                    "RECOVERY_REQUIRED",
                    {"reason": f"Falha no rollback: {exc}"[:2000]},
                )
        except Exception:
            pass
        if isinstance(exc, TransactionPreparationError):
            raise
        raise TransactionPreparationError(
            f"Rollback interrompido; preserve backup e journal: {exc}"
        ) from exc
