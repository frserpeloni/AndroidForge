from __future__ import annotations

import ctypes
import hashlib
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import sermax_windows_journal as journal


class JournalUnitTests(unittest.TestCase):

    def test_scan_marks_nonterminal_transaction_for_recovery(self):
        entry = SimpleNamespace(
            name="txn-" + "a" * 24,
            is_directory=True,
            is_reparse_point=False,
        )
        events = (
            {"event": "PREPARED", "record_sha256": "b" * 64},
            {"event": "INSTALL_STARTED", "record_sha256": "c" * 64},
        )
        with (
            mock.patch.object(journal, "_validate_journal_parent"),
            mock.patch.object(journal, "_real_entries", return_value=(entry,)),
            mock.patch(
                "sermax_windows_directory_handle.open_verified_child_component",
                return_value=200,
            ),
            mock.patch.object(
                journal, "read_journal_events_by_handle", return_value=events
            ),
            mock.patch.object(journal, "close_handle") as closer,
        ):
            result = journal.scan_journal_transactions_by_handle(100)
        self.assertEqual(result[0]["state"], "IN_PROGRESS")
        self.assertTrue(result[0]["requires_recovery"])
        self.assertTrue(result[0]["install_started"])
        self.assertTrue(result[0]["rollback_supported"])
        closer.assert_called_once_with(200)

    def test_scan_marks_pre_install_transaction_as_not_rollback_supported(self):
        entry = SimpleNamespace(
            name="txn-" + "f" * 24,
            is_directory=True,
            is_reparse_point=False,
        )
        events = (
            {"event": "PREPARED", "record_sha256": "b" * 64},
            {"event": "BACKUP_COMPLETE", "record_sha256": "c" * 64},
        )
        with (
            mock.patch.object(journal, "_validate_journal_parent"),
            mock.patch.object(journal, "_real_entries", return_value=(entry,)),
            mock.patch(
                "sermax_windows_directory_handle.open_verified_child_component",
                return_value=200,
            ),
            mock.patch.object(
                journal, "read_journal_events_by_handle", return_value=events
            ),
            mock.patch.object(journal, "close_handle"),
        ):
            result = journal.scan_journal_transactions_by_handle(100)
        self.assertTrue(result[0]["requires_recovery"])
        self.assertFalse(result[0]["install_started"])
        self.assertFalse(result[0]["rollback_supported"])

    def test_scan_marks_committed_transaction_as_terminal(self):
        entry = SimpleNamespace(
            name="txn-" + "a" * 24,
            is_directory=True,
            is_reparse_point=False,
        )
        events = ({"event": "COMMITTED", "record_sha256": "b" * 64},)
        with (
            mock.patch.object(journal, "_validate_journal_parent"),
            mock.patch.object(journal, "_real_entries", return_value=(entry,)),
            mock.patch(
                "sermax_windows_directory_handle.open_verified_child_component",
                return_value=200,
            ),
            mock.patch.object(
                journal, "read_journal_events_by_handle", return_value=events
            ),
            mock.patch.object(journal, "close_handle"),
        ):
            result = journal.scan_journal_transactions_by_handle(100)
        self.assertEqual(result[0]["state"], "TERMINAL")
        self.assertFalse(result[0]["requires_recovery"])

    def test_canonical_json_is_stable_and_rejects_nonfinite_values(self):
        left = journal._canonical_json({"b": 2, "a": 1})
        right = journal._canonical_json({"a": 1, "b": 2})
        self.assertEqual(left, right)
        with self.assertRaises(journal.JournalError):
            journal._canonical_json({"invalid": float("nan")})

    def test_rejects_invalid_state_transition(self):
        with self.assertRaisesRegex(journal.JournalError, "Transição"):
            journal._validate_transition("COMMITTED", "INSTALL_STARTED")

    def test_requires_prepared_as_first_event(self):
        with self.assertRaisesRegex(journal.JournalError, "Transição"):
            journal._validate_transition(None, "BACKUP_COMPLETE")

    def test_rejects_protected_paths_in_file_events(self):
        payload = {"path": "_update/journal/event.bin", "sha256": "a" * 64, "file_id_128": "1" * 32}
        with self.assertRaisesRegex(journal.JournalError, "protegido"):
            journal._validate_event_payload("FILE_REPLACED", payload)

    def test_rejects_invalid_hash_in_event_payload(self):
        payload = {"path": "bin/engine.dll", "sha256": "xyz", "file_id_128": "1" * 32}
        with self.assertRaisesRegex(journal.JournalError, "Hash inválido"):
            journal._validate_event_payload("FILE_REPLACED", payload)

    def test_requires_event_specific_payload_fields(self):
        with self.assertRaisesRegex(journal.JournalError, "incompleto"):
            journal._validate_event_payload("PREPARED", {"release_version": "2.0"})

    def test_file_install_intent_requires_valid_file_identity(self):
        payload = {
            "path": "bin/new-engine.dll",
            "sha256": "a" * 64,
            "file_id_128": "b" * 32,
        }
        journal._validate_event_payload("FILE_INSTALL_INTENT", payload)
        invalid = {**payload, "file_id_128": "not-a-file-id"}
        with self.assertRaisesRegex(journal.JournalError, "FileId inválido"):
            journal._validate_event_payload("FILE_INSTALL_INTENT", invalid)

    def test_install_intent_precedes_replacement_and_allows_rollback(self):
        journal._validate_transition("INSTALL_STARTED", "FILE_INSTALL_INTENT")
        journal._validate_transition("FILE_INSTALL_INTENT", "FILE_REPLACED")
        journal._validate_transition("FILE_INSTALL_INTENT", "ROLLBACK_STARTED")

    def test_file_removed_requires_valid_file_identity(self):
        payload = {
            "path": "bin/new-engine.dll",
            "sha256": "a" * 64,
            "file_id_128": "b" * 32,
        }
        journal._validate_event_payload("FILE_REMOVED", payload)
        invalid = {**payload, "file_id_128": "not-a-file-id"}
        with self.assertRaisesRegex(journal.JournalError, "FileId inválido"):
            journal._validate_event_payload("FILE_REMOVED", invalid)

    def test_rollback_state_accepts_removed_then_restored(self):
        journal._validate_transition("ROLLBACK_STARTED", "FILE_REMOVED")
        journal._validate_transition("FILE_REMOVED", "FILE_RESTORED")
        journal._validate_transition("FILE_RESTORED", "ROLLED_BACK")


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Journal nativo exige Windows x64.",
)
class JournalWindowsIntegrationTests(unittest.TestCase):
    def test_appends_reopens_and_detects_tampered_event(self):
        import shutil
        from sermax_windows_handle_io import close_handle
        from sermax_windows_private_area import create_private_directory_component

        with tempfile.TemporaryDirectory(prefix="sermax-journal-native-") as root:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p,
            ]
            create_file.restype = ctypes.c_void_p
            close = kernel32.CloseHandle
            close.argtypes = [ctypes.c_void_p]
            close.restype = ctypes.c_int
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
            reopened = None
            try:
                journal_parent = create_private_directory_component(
                    parent, "journal"
                )
                session = journal.create_journal_transaction_by_handle(
                    journal_parent
                )
                transaction_id = session.transaction_id

                events = [
                    ("PREPARED", {
                        "release_version": "2.0.0",
                        "manifest_sha256": "a" * 64,
                    }),
                    ("BACKUP_COMPLETE", {
                        "backup_component": None,
                        "catalog_sha256": None,
                    }),
                    ("STAGING_COMPLETE", {
                        "staging_component": "stage-" + "b" * 24,
                        "archive_sha256": "c" * 64,
                    }),
                    ("INSTALL_STARTED", {}),
                    ("FILE_INSTALL_INTENT", {
                        "path": "bin/engine.dll",
                        "sha256": "d" * 64,
                        "file_id_128": "1" * 32,
                    }),
                    ("FILE_REPLACED", {
                        "path": "bin/engine.dll",
                        "sha256": "d" * 64,
                        "file_id_128": "1" * 32,
                    }),
                    ("COMMITTED", {"release_version": "2.0.0"}),
                ]
                for event, payload in events:
                    session.append_event(event, payload)

                observed = session.read_events()
                self.assertEqual(len(observed), len(events))
                self.assertEqual(
                    [item["event"] for item in observed],
                    [item[0] for item in events],
                )
                for index, item in enumerate(observed):
                    self.assertEqual(item["sequence"], index + 1)
                    self.assertEqual(len(item["record_sha256"]), 64)
                    if index:
                        self.assertEqual(
                            item["previous_hash"],
                            observed[index - 1]["record_sha256"],
                        )

                session.close()
                session = None
                reopened = journal.open_journal_transaction_by_handle(
                    journal_parent, transaction_id
                )
                self.assertEqual(len(reopened.read_events()), len(events))
                reopened.close()
                reopened = None
                scan = journal.scan_journal_transactions_by_handle(journal_parent)
                self.assertEqual(len(scan), 1)
                self.assertEqual(scan[0]["last_event"], "COMMITTED")
                self.assertFalse(scan[0]["requires_recovery"])
                reopened = None

                event_path = os.path.join(
                    root, "journal", transaction_id, "event-000001.json"
                )
                with open(event_path, "r+b") as event_file:
                    raw = event_file.read()
                    record = json.loads(raw.decode("utf-8"))
                    record["payload"]["release_version"] = "9.9.9"
                    event_file.seek(0)
                    event_file.write(json.dumps(
                        record, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False,
                    ).encode("utf-8"))
                    event_file.truncate()

                with self.assertRaises(journal.JournalError):
                    journal.open_journal_transaction_by_handle(
                        journal_parent, transaction_id
                    )
            finally:
                if reopened is not None:
                    reopened.close()
                if session is not None:
                    session.close()
                if journal_parent is not None:
                    close_handle(journal_parent)
                self.assertTrue(close(parent))
                shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
