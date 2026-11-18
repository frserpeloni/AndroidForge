"""Inspeção somente de leitura da área _update sob um handle SERMAX.

Não cria a pasta, não altera ACL, não grava staging e não autoriza escrita.
A evidência retornada deve passar por uma política de segurança separada.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sermax_windows_directory_enum import DirectoryEntry
from sermax_windows_directory_handle import (
    enumerate_stable_directory_handle,
    open_verified_child_component,
)
from sermax_windows_handle_io import (
    HandleIoError,
    close_handle,
    query_handle_metadata,
)
from sermax_windows_security import (
    DirectorySecurityError,
    read_security_by_handle,
)

READ_CONTROL = 0x00020000
_UPDATE_COMPONENT = "_update"


class UpdateAreaError(RuntimeError):
    """A área _update não pôde ser inspecionada com identidade confiável."""


@dataclass
class UpdateAreaInspection:
    """Handle aberto e evidências somente de leitura da área _update."""

    handle: Any
    metadata: dict[str, object]
    security: dict[str, object]

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

    A enumeração precisa encontrar exatamente o componente literal
    `_update`, como diretório comum, sem reparse point. A abertura valida
    FileId, volume, atributos e tamanho contra a entrada enumerada.
    O handle retornado solicita READ_CONTROL e permanece aberto até close().
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

            security = read_security_by_handle(handle)
            return UpdateAreaInspection(
                handle=handle,
                metadata=metadata,
                security=security,
            )
        except Exception:
            close_handle(handle)
            raise
    except UpdateAreaError:
        raise
    except (HandleIoError, DirectorySecurityError) as exc:
        raise UpdateAreaError(f"Falha na inspeção segura de _update: {exc}") from exc
