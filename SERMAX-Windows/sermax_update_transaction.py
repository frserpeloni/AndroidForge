"""Preparação transacional de release SERMAX, sem instalação ativa.

Coordena manifesto já autenticado, validação do pacote, backup, journal e
staging por handles. Não substitui arquivos ativos nem executa código da release.
"""
from __future__ import annotations

from dataclasses import dataclass

from sermax_update_manifest import ValidatedManifest
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
