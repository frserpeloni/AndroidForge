import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import windows_autostart as autostart


class WindowsAutostartXmlTests(unittest.TestCase):
    def test_task_runs_at_user_logon_with_interactive_low_privilege(self):
        xml_text = autostart.build_task_xml(
            Path("C:/SERMAX-Platform"),
            executable="C:/Python/python.exe",
            frozen=False,
            user_id="PC\\fabiano",
        )
        self.assertIn("<LogonType>InteractiveToken</LogonType>", xml_text)
        self.assertIn("<RunLevel>LeastPrivilege</RunLevel>", xml_text)
        self.assertIn("<UserId>PC\\fabiano</UserId>", xml_text)
        self.assertIn("--no-browser", xml_text)
        self.assertIn("IgnoreNew", xml_text)
        self.assertNotIn("LocalSystem", xml_text)


    def test_source_task_prefers_platform_virtual_environment_python(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            venv_python = root / "backend" / ".venv" / "Scripts" / "pythonw.exe"
            venv_python.parent.mkdir(parents=True)
            venv_python.write_text("", encoding="utf-8")
            xml_text = autostart.build_task_xml(
                root, frozen=False, user_id="PC\\\\fabiano"
            )
            self.assertIn(f"<Command>{venv_python}</Command>", xml_text)
            self.assertIn(f"{root / 'sermax_platform_launcher.py'}", xml_text)
            self.assertIn("--no-browser", xml_text)


    def test_source_task_falls_back_to_python_exe_when_pythonw_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            venv_python = root / "backend" / ".venv" / "Scripts" / "python.exe"
            venv_python.parent.mkdir(parents=True)
            venv_python.write_text("", encoding="utf-8")
            xml_text = autostart.build_task_xml(
                root, frozen=False, user_id="PC\\\\fabiano"
            )
            self.assertIn(f"<Command>{venv_python}</Command>", xml_text)

    def test_generated_task_xml_is_well_formed_and_has_user_logon_trigger(self):
        namespace = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
        xml_text = autostart.build_task_xml(
            Path("C:/SERMAX-Platform"),
            executable="C:/Python/python.exe",
            frozen=False,
            user_id="PC\\\\fabiano",
        )
        task = autostart.ET.fromstring(xml_text)
        self.assertEqual(task.tag, f"{namespace}Task")
        trigger = task.find(f"{namespace}Triggers/{namespace}LogonTrigger")
        self.assertIsNotNone(trigger)
        self.assertEqual(trigger.findtext(f"{namespace}UserId"), "PC\\\\fabiano")
        principal = task.find(f"{namespace}Principals/{namespace}Principal")
        self.assertEqual(principal.findtext(f"{namespace}LogonType"), "InteractiveToken")
        self.assertEqual(principal.findtext(f"{namespace}RunLevel"), "LeastPrivilege")

    def test_frozen_launcher_does_not_pass_python_script_path(self):
        xml_text = autostart.build_task_xml(
            Path("C:/SERMAX"),
            executable="C:/SERMAX/SERMAX.exe",
            frozen=True,
            user_id="fabiano",
        )
        self.assertIn("<Command>C:/SERMAX/SERMAX.exe</Command>", xml_text)
        self.assertIn("<Arguments>--no-browser</Arguments>", xml_text)


class WindowsAutostartCommandTests(unittest.TestCase):
    def setUp(self):
        self.windows = patch.object(autostart, "_is_windows", return_value=True)
        self.windows.start()

    def tearDown(self):
        self.windows.stop()

    def test_install_uses_task_scheduler_xml_and_removes_temporary_file(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            xml_path = Path(command[command.index("/XML") + 1])
            self.assertTrue(xml_path.is_file())
            self.assertIn("InteractiveToken", xml_path.read_text(encoding="utf-16"))
            return subprocess.CompletedProcess(command, 0, "", "")

        autostart.install_autostart(Path("C:/SERMAX-Platform"), runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][1:4], ["/Create", "/TN", autostart.TASK_NAME])
        self.assertFalse(Path(calls[0][0][calls[0][0].index("/XML") + 1]).exists())

    def test_install_reports_scheduler_failure(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, "", "Access denied"))
        with self.assertRaisesRegex(RuntimeError, "Access denied"):
            autostart.install_autostart(Path("C:/SERMAX-Platform"), runner=runner)

    def test_status_reports_task_presence(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "TaskName", ""))
        self.assertTrue(autostart.autostart_status(runner=runner))

    def test_remove_is_idempotent_when_task_is_missing(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, "", "not found"))
        self.assertFalse(autostart.remove_autostart(runner=runner))
        runner.assert_called_once()

    def test_remove_deletes_existing_task(self):
        responses = [
            subprocess.CompletedProcess([], 0, "TaskName", ""),
            subprocess.CompletedProcess([], 0, "SUCCESS", ""),
        ]
        runner = Mock(side_effect=responses)
        self.assertTrue(autostart.remove_autostart(runner=runner))
        self.assertEqual(runner.call_count, 2)
        self.assertIn("/Delete", runner.call_args.args[0])

    def test_non_windows_platform_is_rejected(self):
        with patch.object(autostart, "_is_windows", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "somente no Windows"):
                autostart.autostart_status()


if __name__ == "__main__":
    unittest.main()
