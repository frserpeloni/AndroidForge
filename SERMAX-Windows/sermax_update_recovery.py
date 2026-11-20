"""Avaliação somente leitura de transações pendentes antes da inicialização SERMAX.

Este módulo não executa rollback, não remove staging/backup e não altera journal.
Uma transação que já registrou INSTALL_STARTED bloqueia a inicialização normal
até uma decisão explícita do operador e uma chamada separada de recuperação.
"""
from __future__ import annotations

from typing import Any


class StartupRecoveryAssessmentError(RuntimeError):
    """Não foi possível avaliar o estado persistente com segurança."""


def inspect_startup_recovery_by_handle(journal_parent_handle) -> dict[str, Any]:
    """Avalia journals pendentes sem executar ações de recuperação.

    Regras:
    - COMMITTED/ROLLED_BACK: terminal, sem bloqueio.
    - Sem INSTALL_STARTED: a fase ativa não começou; sinaliza revisão, mas
      permite a inicialização normal do SERMAX.
    - Com INSTALL_STARTED e sem estado terminal: bloqueia a inicialização
      normal e exige decisão explícita antes de chamar a rotina de rollback.
    - Journal inválido: falha fechada, sem alterar os dados.

    A função não interpreta nem autentica manifestos e não executa rollback.
    """
    from sermax_windows_journal import (
        JournalError,
        scan_journal_transactions_by_handle,
    )

    try:
        scanned = scan_journal_transactions_by_handle(journal_parent_handle)
    except JournalError as exc:
        raise StartupRecoveryAssessmentError(
            f"Journal não passou na inspeção. Inicialização segura bloqueada: {exc}"
        ) from exc
    except Exception as exc:
        raise StartupRecoveryAssessmentError(
            f"Falha ao inspecionar journals. Inicialização segura bloqueada: {exc}"
        ) from exc

    assessments = []
    startup_blocked = False
    attention_count = 0

    for item in scanned:
        transaction_id = item.get("transaction_id")
        state = item.get("state")
        install_started = item.get("install_started")
        requires_recovery = item.get("requires_recovery")

        if (
            not isinstance(transaction_id, str)
            or state not in {"EMPTY", "TERMINAL", "IN_PROGRESS", "RECOVERY_REQUIRED"}
            or type(install_started) is not bool
            or type(requires_recovery) is not bool
        ):
            raise StartupRecoveryAssessmentError(
                "Resumo do journal incompleto ou inválido. Inicialização segura bloqueada."
            )

        if state == "TERMINAL":
            assessments.append({
                "transaction_id": transaction_id,
                "state": "TERMINAL",
                "startup_action": "CONTINUE",
                "rollback_supported": False,
                "requires_operator_attention": False,
                "last_event": item.get("last_event"),
            })
            continue

        attention_count += 1
        if install_started:
            startup_blocked = True
            assessments.append({
                "transaction_id": transaction_id,
                "state": "INSTALL_INTERRUPTED",
                "startup_action": "HOLD_FOR_OPERATOR_DECISION",
                "rollback_supported": True,
                "requires_operator_attention": True,
                "last_event": item.get("last_event"),
            })
        elif state == "EMPTY":
            assessments.append({
                "transaction_id": transaction_id,
                "state": "EMPTY_TRANSACTION",
                "startup_action": "REVIEW_WITHOUT_AUTOMATIC_CLEANUP",
                "rollback_supported": False,
                "requires_operator_attention": True,
                "last_event": None,
            })
        else:
            assessments.append({
                "transaction_id": transaction_id,
                "state": "PREPARATION_INTERRUPTED",
                "startup_action": "REVIEW_PREPARATION_ONLY",
                "rollback_supported": False,
                "requires_operator_attention": True,
                "last_event": item.get("last_event"),
            })

    return {
        "schema_version": 1,
        "startup_allowed": not startup_blocked,
        "startup_action": "HOLD_FOR_OPERATOR_DECISION" if startup_blocked else "CONTINUE",
        "transaction_count": len(assessments),
        "pending_count": attention_count,
        "automatic_rollback_performed": False,
        "transactions": assessments,
    }
