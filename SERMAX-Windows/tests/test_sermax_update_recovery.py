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
                    "rollback_supported": False,
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
                    "rollback_supported": True,
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
                    "rollback_supported": False,
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

    def test_inconsistent_pending_flag_fails_closed(self):
        with mock.patch(
            "sermax_windows_journal.scan_journal_transactions_by_handle",
            return_value=(
                {
                    "transaction_id": "txn-" + "e" * 24,
                    "state": "IN_PROGRESS",
                    "install_started": False,
                    "requires_recovery": False,
                    "rollback_supported": False,
                    "last_event": "STAGING_COMPLETE",
                },
            ),
        ):
            with self.assertRaisesRegex(
                recovery.StartupRecoveryAssessmentError, "[Rr]esumo do journal"
            ):
                recovery.inspect_startup_recovery_by_handle(123)

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
                recovery.StartupRecoveryAssessmentError, "[Rr]esumo do journal"
            ):
                recovery.inspect_startup_recovery_by_handle(123)


@unittest.skipUnless(
    __import__("os").name == "nt",
    "Inspeção nativa de journal exige Windows.",
)
class StartupRecoveryAssessmentWindowsTests(unittest.TestCase):
    def test_assessment_reads_persistent_journal_without_mutating_it(self):
        import ctypes
        import os
        import tempfile

        from sermax_windows_handle_io import close_handle
        from sermax_windows_private_area import create_private_directory_component
        from sermax_windows_journal import create_journal_transaction_by_handle

        with tempfile.TemporaryDirectory(prefix="sermax-startup-recovery-") as root:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p,
            ]
            create_file.restype = ctypes.c_void_p
            invalid = ctypes.c_void_p(-1).value
            parent = create_file(
                root,
                0x0001 | 0x0004 | 0x0080 | 0x00100000,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            self.assertNotIn(parent, (None, 0, invalid))
            journal_parent = None
            session = None
            try:
                journal_parent = create_private_directory_component(
                    parent, "journal"
                )
                session = create_journal_transaction_by_handle(journal_parent)
                session.append_event(
                    "PREPARED",
                    {
                        "release_version": "1.2.3",
                        "manifest_sha256": "a" * 64,
                    },
                )
                session.append_event(
                    "BACKUP_COMPLETE",
                    {"backup_component": None, "catalog_sha256": None},
                )
                session.append_event(
                    "STAGING_COMPLETE",
                    {
                        "staging_component": "stage-" + "b" * 24,
                        "archive_sha256": "c" * 64,
                    },
                )
                session.append_event("INSTALL_STARTED", {})
                before = session.read_events()
                result = recovery.inspect_startup_recovery_by_handle(
                    journal_parent
                )
                after = session.read_events()

                self.assertFalse(result["startup_allowed"])
                self.assertFalse(result["automatic_rollback_performed"])
                self.assertEqual(
                    result["transactions"][0]["state"], "INSTALL_INTERRUPTED"
                )
                self.assertEqual(
                    [item["record_sha256"] for item in before],
                    [item["record_sha256"] for item in after],
                )
            finally:
                if session is not None:
                    session.close()
                if journal_parent is not None:
                    close_handle(journal_parent)
                close_handle(parent)


if __name__ == "__main__":
    unittest.main()
