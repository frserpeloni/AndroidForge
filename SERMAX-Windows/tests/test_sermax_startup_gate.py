from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import sermax_startup_gate as gate


class StartupGateByHandleTests(unittest.TestCase):
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
        entry = SimpleNamespace(
            name="_update",
            is_directory=True,
            is_reparse_point=True,
        )
        with mock.patch(
            "sermax_windows_directory_handle.enumerate_stable_directory_handle",
            return_value=(entry,),
            create=True,
        ):
            with self.assertRaisesRegex(
                gate.StartupGateError, "ambígua ou não é um diretório regular"
            ):
                gate.inspect_update_recovery_by_sermax_handle(100)

    def test_valid_layout_delegates_assessment_and_closes_all_handles(self):
        entry = SimpleNamespace(
            name="_update",
            is_directory=True,
            is_reparse_point=False,
        )
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
                return_value=(entry,),
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

    def test_layout_validation_failure_fails_closed(self):
        entry = SimpleNamespace(
            name="_update",
            is_directory=True,
            is_reparse_point=False,
        )
        with (
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                return_value=(entry,),
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
                r"C:\\work\\AndroidForge\\SERMAX-Windows"
            )

        self.assertTrue(result["startup_allowed"])
        self.assertEqual(result["startup_action"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
