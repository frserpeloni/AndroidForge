from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sermax_windows11_homologation as report


class HomologationReportTests(unittest.TestCase):
    def test_report_is_read_only_and_does_not_include_memory_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SERMAX_terminal").mkdir()
            (root / "SERMAX.exe").write_bytes(b"executable-placeholder")
            (root / "SERMAX_terminal" / "sermax_terminal.py").write_text(
                "terminal source", encoding="utf-8"
            )
            secret_marker = "FABIANO_PRIVATE_MEMORY_MARKER"
            (root / "memoria_sermax.json").write_text(
                '{"memory":"' + secret_marker + '"}', encoding="utf-8"
            )

            result = report.collect_report(
                str(root),
                system="Windows",
                release="11",
                version="10.0.22631",
                machine="AMD64",
            )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertTrue(result["read_only"])
        self.assertTrue(result["host"]["windows_11"])
        self.assertTrue(result["installation"]["files"]["memory"]["regular_file"])
        self.assertEqual(
            result["installation"]["files"]["terminal"]["sha256"],
            __import__("hashlib").sha256(b"terminal source").hexdigest(),
        )
        self.assertNotIn(secret_marker, serialized)
        self.assertFalse(result["privacy"]["memory_file_content_read"])
        self.assertFalse(result["privacy"]["file_contents_included"])

    def test_missing_installation_is_reported_without_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            result = report.collect_report(str(root))

        self.assertFalse(result["installation"]["root_exists"])
        self.assertFalse(result["installation"]["files"]["memory"]["exists"])
        self.assertFalse(result["installation"]["files"]["terminal"]["exists"])

    def test_windows_11_build_detection(self):
        self.assertTrue(report._windows_11_status("Windows", "10.0.22631"))
        self.assertFalse(report._windows_11_status("Windows", "10.0.19045"))
        self.assertFalse(report._windows_11_status("Linux", "6.8.0"))
        self.assertIsNone(report._windows_11_status("Windows", "unknown"))

    def test_only_exact_drive_root_sermax_path_is_managed(self):
        self.assertTrue(report._is_root_installation(r"C:\SERMAX"))
        self.assertTrue(report._is_root_installation(r"D:\SERMAX"))
        self.assertFalse(report._is_root_installation(r"C:\work\SERMAX"))
        self.assertFalse(report._is_root_installation(r"C:\SERMAX\nested"))

    def test_recovery_assessment_is_sanitized_and_read_only(self):
        assessment = {
            "configured": True,
            "startup_allowed": False,
            "pending_count": 1,
            "automatic_rollback_performed": False,
            "transactions": [{
                "transaction_id": "tx-001",
                "state": "INSTALL_INTERRUPTED",
                "startup_action": "HOLD_FOR_OPERATOR_DECISION",
                "last_event": "FILE_REPLACED",
                "private_field": "must-not-leak",
            }],
        }
        inspector = mock.Mock(return_value=assessment)
        with mock.patch.object(report.platform, "system", return_value="Windows"):
            result = report._inspect_recovery(r"C:\SERMAX", inspector)

        inspector.assert_called_once_with(r"C:\SERMAX")
        self.assertEqual(result["status"], "ASSESSED")
        self.assertFalse(result["startup_allowed"])
        self.assertNotIn("private_field", json.dumps(result))
        self.assertFalse(result["automatic_rollback_performed"])


if __name__ == "__main__":
    unittest.main()
