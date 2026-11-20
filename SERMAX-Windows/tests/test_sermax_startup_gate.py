from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock
from unittest.mock import call

import sermax_startup_gate as gate


class StartupGateByHandleTests(unittest.TestCase):
    def _entry(self, name="_update", *, is_directory=True, is_reparse_point=False):
        return SimpleNamespace(
            name=name,
            is_directory=is_directory,
            is_reparse_point=is_reparse_point,
        )

    def test_installation_without_update_area_keeps_legacy_startup(self):
        with (
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(),
                create=True,
            ),
            mock.patch(
                "sermax_windows_private_area.open_existing_private_area_layout",
                create=True,
            ) as open_layout,
        ):
            result = gate.inspect_update_recovery_by_sermax_handle(100)

        self.assertFalse(result["configured"])
        self.assertTrue(result["startup_allowed"])
        self.assertFalse(result["automatic_rollback_performed"])
        open_layout.assert_not_called()

    def test_rejects_reparse_or_non_directory_update_component(self):
        for entry in (
            self._entry(is_reparse_point=True),
            self._entry(is_directory=False),
        ):
            with self.subTest(entry=entry), mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(entry,),
                create=True,
            ):
                with self.assertRaisesRegex(
                    gate.StartupGateError, "ambígua ou não é um diretório regular"
                ):
                    gate.inspect_update_recovery_by_sermax_handle(100)

    def test_rejects_duplicate_update_components(self):
        entries = (self._entry(), self._entry())
        with mock.patch(
            "sermax_windows_directory_handle.enumerate_stable_directory_handle",
            return_value=entries,
            create=True,
        ):
            with self.assertRaisesRegex(
                gate.StartupGateError, "ambígua ou não é um diretório regular"
            ):
                gate.inspect_update_recovery_by_sermax_handle(100)

    def test_rejects_case_variant_update_component(self):
        with mock.patch(
            "sermax_windows_directory_handle.enumerate_stable_directory_handle",
            return_value=(self._entry("_UPDATE"),),
            create=True,
        ):
            with self.assertRaisesRegex(
                gate.StartupGateError, "ambígua ou não é um diretório regular"
            ):
                gate.inspect_update_recovery_by_sermax_handle(100)

    def test_valid_layout_delegates_assessment_and_closes_layout(self):
        layout = SimpleNamespace(
            directories={"journal": 300},
            close=mock.Mock(),
        )
        assessment = {
            "startup_allowed": False,
            "startup_action": "HOLD_FOR_OPERATOR_DECISION",
            "pending_count": 1,
            "automatic_rollback_performed": False,
            "transactions": [],
        }
        with (
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(self._entry(),),
                create=True,
            ),
            mock.patch(
                "sermax_windows_private_area.open_existing_private_area_layout",
                return_value=layout,
                create=True,
            ),
            mock.patch(
                "sermax_update_recovery.inspect_startup_recovery_by_handle",
                return_value=assessment,
            ) as inspect,
        ):
            result = gate.inspect_update_recovery_by_sermax_handle(100)

        inspect.assert_called_once_with(300)
        layout.close.assert_called_once_with()
        self.assertTrue(result["configured"])
        self.assertFalse(result["startup_allowed"])
        self.assertFalse(result["automatic_rollback_performed"])

    def test_layout_is_closed_when_journal_assessment_fails(self):
        layout = SimpleNamespace(
            directories={"journal": 300},
            close=mock.Mock(),
        )
        with (
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(self._entry(),),
                create=True,
            ),
            mock.patch(
                "sermax_windows_private_area.open_existing_private_area_layout",
                return_value=layout,
                create=True,
            ),
            mock.patch(
                "sermax_update_recovery.inspect_startup_recovery_by_handle",
                side_effect=RuntimeError("journal read failed"),
            ),
        ):
            with self.assertRaisesRegex(
                gate.StartupGateError, "validar a área persistente"
            ):
                gate.inspect_update_recovery_by_sermax_handle(100)

        layout.close.assert_called_once_with()

    def test_layout_validation_failure_fails_closed(self):
        with (
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(self._entry(),),
                create=True,
            ),
            mock.patch(
                "sermax_windows_private_area.open_existing_private_area_layout",
                side_effect=RuntimeError("ACL invalid"),
                create=True,
            ),
        ):
            with self.assertRaisesRegex(
                gate.StartupGateError, "validar a área persistente"
            ):
                gate.inspect_update_recovery_by_sermax_handle(100)


class StartupGatePathTests(unittest.TestCase):
    def test_non_windows_execution_keeps_legacy_startup(self):
        with mock.patch.object(gate.os, "name", "posix"):
            result = gate.inspect_update_recovery_at_startup("/tmp/SERMAX")

        self.assertTrue(result["startup_allowed"])
        self.assertEqual(result["startup_action"], "NOT_APPLICABLE")

    def test_development_directory_is_not_treated_as_installed_sermax(self):
        with mock.patch.object(gate.os, "name", "nt"):
            result = gate.inspect_update_recovery_at_startup(
                r"C:\work\AndroidForge\SERMAX-Windows"
            )

        self.assertTrue(result["startup_allowed"])
        self.assertEqual(result["startup_action"], "NOT_APPLICABLE")

    def test_managed_installation_closes_both_directory_handles(self):
        assessment = {
            "configured": True,
            "startup_allowed": True,
            "pending_count": 0,
            "automatic_rollback_performed": False,
            "transactions": [],
        }
        with (
            mock.patch.object(gate.os, "name", "nt"),
            mock.patch.object(gate.ctypes, "sizeof", return_value=8),
            mock.patch(
                "sermax_windows_root.open_drive_root", return_value=10
            ),
            mock.patch(
                "sermax_windows_root.open_managed_directory", return_value=20
            ),
            mock.patch("sermax_windows_handle_io.close_handle") as close_handle,
            mock.patch.object(
                gate,
                "inspect_update_recovery_by_sermax_handle",
                return_value=assessment,
            ),
        ):
            result = gate.inspect_update_recovery_at_startup(r"C:\SERMAX")

        self.assertTrue(result["startup_allowed"])
        close_handle.assert_has_calls([call(20), call(10)])
        self.assertEqual(close_handle.call_count, 2)

    def test_drive_handle_is_closed_when_sermax_open_fails(self):
        with (
            mock.patch.object(gate.os, "name", "nt"),
            mock.patch.object(gate.ctypes, "sizeof", return_value=8),
            mock.patch(
                "sermax_windows_root.open_drive_root", return_value=10
            ),
            mock.patch(
                "sermax_windows_root.open_managed_directory",
                side_effect=RuntimeError("SERMAX open failed"),
            ),
            mock.patch("sermax_windows_handle_io.close_handle") as close_handle,
        ):
            with self.assertRaisesRegex(
                gate.StartupGateError, "Falha ao abrir a instalação"
            ):
                gate.inspect_update_recovery_at_startup(r"C:\SERMAX")

        close_handle.assert_called_once_with(10)


if __name__ == "__main__":
    unittest.main()
