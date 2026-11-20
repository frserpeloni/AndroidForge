from __future__ import annotations

import unittest
from unittest import mock

import sermax_update_recovery as recovery
from sermax_windows_journal import JournalError


class StartupRecoveryAssessmentTests(unittest.TestCase):
    def test_clean_and_terminal_journals_allow_startup(self):
        with mock.patch(
            "sermax_windows_journal.scan_journal_transactions_by_handle",
            return_value=(
                {
                    "transaction_id": "txn-" + "a" * 24,
                    "state": "TERMINAL",
                    "install_started": True,
                    "requires_recovery": False,
                    "last_event": "COMMITTED",
                },
            ),
        ):
            result = recovery.inspect_startup_recovery_by_handle(123)

        self.assertTrue(result["startup_allowed"])
        self.assertEqual(result["startup_action"], "CONTINUE")
        self.assertEqual(result["pending_count"], 0)
        self.assertFalse(result["automatic_rollback_performed"])

    def test_interrupted_install_blocks_startup_but_never_rolls_back(self):
        with mock.patch(
            "sermax_windows_journal.scan_journal_transactions_by_handle",
            return_value=(
                {
                    "transaction_id": "txn-" + "b" * 24,
                    "state": "RECOVERY_REQUIRED",
                    "install_started": True,
                    "requires_recovery": True,
                    "last_event": "RECOVERY_REQUIRED",
                },
            ),
        ):
            result = recovery.inspect_startup_recovery_by_handle(123)

        self.assertFalse(result["startup_allowed"])
        self.assertEqual(
            result["startup_action"], "HOLD_FOR_OPERATOR_DECISION"
        )
        self.assertEqual(
            result["transactions"][0]["startup_action"],
            "HOLD_FOR_OPERATOR_DECISION",
        )
        self.assertTrue(result["transactions"][0]["rollback_supported"])
        self.assertFalse(result["automatic_rollback_performed"])

    def test_preparation_interruption_does_not_block_active_sermax(self):
        with mock.patch(
            "sermax_windows_journal.scan_journal_transactions_by_handle",
            return_value=(
                {
                    "transaction_id": "txn-" + "c" * 24,
                    "state": "IN_PROGRESS",
                    "install_started": False,
                    "requires_recovery": True,
                    "last_event": "STAGING_COMPLETE",
                },
            ),
        ):
            result = recovery.inspect_startup_recovery_by_handle(123)

        self.assertTrue(result["startup_allowed"])
        self.assertEqual(
            result["transactions"][0]["state"], "PREPARATION_INTERRUPTED"
        )
        self.assertFalse(result["transactions"][0]["rollback_supported"])
        self.assertTrue(
            result["transactions"][0]["requires_operator_attention"]
        )

    def test_empty_transaction_is_reviewed_without_automatic_cleanup(self):
        with mock.patch(
            "sermax_windows_journal.scan_journal_transactions_by_handle",
            return_value=(
                {
                    "transaction_id": "txn-" + "d" * 24,
                    "state": "EMPTY",
                    "install_started": False,
                    "requires_recovery": True,
                    "last_event": None,
                },
            ),
        ):
            result = recovery.inspect_startup_recovery_by_handle(123)

        self.assertTrue(result["startup_allowed"])
        self.assertEqual(
            result["transactions"][0]["state"], "EMPTY_TRANSACTION"
        )
        self.assertEqual(
            result["transactions"][0]["startup_action"],
            "REVIEW_WITHOUT_AUTOMATIC_CLEANUP",
        )

    def test_corrupt_journal_fails_closed_without_recovery_action(self):
        with mock.patch(
            "sermax_windows_journal.scan_journal_transactions_by_handle",
            side_effect=JournalError("hash chain invalid"),
        ):
            with self.assertRaisesRegex(
                recovery.StartupRecoveryAssessmentError,
                "Inicialização segura bloqueada",
            ):
                recovery.inspect_startup_recovery_by_handle(123)

    def test_invalid_scan_summary_fails_closed(self):
        with mock.patch(
            "sermax_windows_journal.scan_journal_transactions_by_handle",
            return_value=({"transaction_id": "txn-invalid"},),
        ):
            with self.assertRaisesRegex(
                recovery.StartupRecoveryAssessmentError, "resumo do journal"
            ):
                recovery.inspect_startup_recovery_by_handle(123)


if __name__ == "__main__":
    unittest.main()
