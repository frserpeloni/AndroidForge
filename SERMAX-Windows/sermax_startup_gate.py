"""Gate de inicialização para a área persistente do atualizador SERMAX.

A avaliação é somente leitura. O módulo nunca executa rollback nem limpa
transações. Instalações sem a estrutura _update mantêm o fluxo legado.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
from contextlib import ExitStack
from typing import Any


class StartupGateError(RuntimeError):
    """A área de atualização não pôde ser inspecionada com segurança."""


def inspect_update_recovery_by_sermax_handle(sermax_handle) -> dict[str, Any]:
    """Inspeciona _update relativa ao handle SERMAX, sem mutações."""
    from sermax_windows_directory_handle import enumerate_stable_directory_handle
    from sermax_windows_private_area import open_existing_private_area_layout
    from sermax_update_recovery import inspect_startup_recovery_by_handle

    try:
        entries = tuple(enumerate_stable_directory_handle(sermax_handle))
        candidates = [
            entry for entry in entries
            if entry.name.casefold() == "_update"
        ]
        if not candidates:
            return {
                "configured": False,
                "startup_allowed": True,
                "startup_action": "CONTINUE",
                "pending_count": 0,
                "automatic_rollback_performed": False,
                "transactions": [],
            }
        if (
            len(candidates) != 1
            or candidates[0].name != "_update"
            or not candidates[0].is_directory
            or candidates[0].is_reparse_point
        ):
            raise StartupGateError(
                "A área _update está ambígua ou não é um diretório regular."
            )

        layout = open_existing_private_area_layout(sermax_handle)
        try:
            assessment = inspect_startup_recovery_by_handle(
                layout.directories["journal"]
            )
        finally:
            layout.close()

        return {
            **assessment,
            "configured": True,
        }
    except StartupGateError:
        raise
    except Exception as exc:
        raise StartupGateError(
            f"Não foi possível validar a área persistente _update: {exc}"
        ) from exc


def inspect_update_recovery_at_startup(install_root: str) -> dict[str, Any]:
    """Abre a instalação SERMAX por handles e avalia a recuperação pendente.

    O gate só se aplica à instalação local cujo diretório final é SERMAX na
    raiz de uma unidade. Execuções de desenvolvimento em outra pasta preservam
    o fluxo atual e não tentam abrir a área de atualização.
    """
    if os.name != "nt":
        return {
            "configured": False,
            "startup_allowed": True,
            "startup_action": "NOT_APPLICABLE",
            "pending_count": 0,
            "automatic_rollback_performed": False,
            "transactions": [],
        }
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise StartupGateError(
            "A inspeção segura do atualizador exige Windows x64."
        )
    if not isinstance(install_root, str) or not install_root:
        raise StartupGateError("Raiz de instalação inválida.")

    normalized_root = ntpath.normpath(ntpath.abspath(install_root))
    drive, tail = ntpath.splitdrive(normalized_root)
    expected_root = ntpath.normcase(ntpath.join(drive + ntpath.sep, "SERMAX"))
    if not drive or ntpath.normcase(normalized_root) != expected_root:
        return {
            "configured": False,
            "startup_allowed": True,
            "startup_action": "NOT_APPLICABLE",
            "pending_count": 0,
            "automatic_rollback_performed": False,
            "transactions": [],
        }

    from sermax_windows_handle_io import close_handle
    from sermax_windows_root import open_drive_root, open_managed_directory

    drive_handle = None
    sermax_handle = None
    try:
        drive_handle = open_drive_root(drive + ntpath.sep)
        sermax_handle = open_managed_directory(drive_handle)
        return inspect_update_recovery_by_sermax_handle(sermax_handle)
    except StartupGateError:
        raise
    except Exception as exc:
        raise StartupGateError(
            f"Falha ao abrir a instalação para inspeção de atualização: {exc}"
        ) from exc
    finally:
        close_errors = []
        for handle in (sermax_handle, drive_handle):
            if handle is not None:
                try:
                    close_handle(handle)
                except Exception as exc:
                    close_errors.append(exc)
        if close_errors:
            raise StartupGateError(
                "Falha ao fechar handles da inspeção: "
                + "; ".join(map(str, close_errors))
            )
