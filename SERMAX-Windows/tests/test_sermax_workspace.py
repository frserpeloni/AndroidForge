import os
import tempfile
import unittest
import sys
from unittest.mock import patch

import sermax_workspace
from pathlib import Path

from sermax_workspace import WorkspaceAdapter, TestRunner, WorkspaceError
from sermax_platform_github_agent_runner import PlatformWorkspaceAdapter


class WorkspaceAdapterTests(unittest.TestCase):
    def test_read_write_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "src" / "sample.py").write_text("old", encoding="utf-8")
            ws = WorkspaceAdapter(root)
            self.assertEqual(ws.read_text("src/sample.py"), "old")
            ws.write_text("src/sample.py", "new")
            self.assertEqual(ws.read_text("src/sample.py"), "new")
            self.assertEqual(
                (root / ".sermax_dev_backups" / "src" / "sample.py").read_text(),
                "old",
            )

    def test_blocks_protected_and_traversal_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            ws = WorkspaceAdapter(folder)
            for name in ("../outside.txt", "..\\outside.txt", "memoria_sermax.json",
                         "memoria_neural_pestinha.json", ".git/config"):
                with self.subTest(name=name), self.assertRaises(WorkspaceError):
                    ws.read_text(name)

    def test_platform_agent_adapter_blocks_server_but_allows_other_backend_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            adapter = PlatformWorkspaceAdapter(root)
            with self.assertRaises(WorkspaceError):
                adapter.preview("backend/server.py", "SERVER = 'replacement'\n")
            diff = adapter.preview("backend/instance_lock.py", "LOCK_ENABLED = True\n")
            self.assertIsInstance(diff, str)

    def test_blocks_symlink_escape(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            root = Path(folder)
            (root / "escape").symlink_to(Path(outside), target_is_directory=True)
            ws = WorkspaceAdapter(root)
            with self.assertRaises(WorkspaceError):
                ws.write_text("escape/file.txt", "blocked")

    def test_test_runner_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_smoke.py").write_text(
                "import unittest\n"
                "class SmokeTests(unittest.TestCase):\n"
                "    def test_runner_executes_discovered_tests(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            ws = WorkspaceAdapter(root)
            runner = TestRunner(ws)
            with self.assertRaises(WorkspaceError):
                runner.run("arbitrary-shell")
            result = runner.run("unittest")
            self.assertEqual(result["status"], "passed", result["output"])
            self.assertIn("Ran 1 test", result["output"])
            self.assertFalse((tests_dir / "__pycache__").exists())


    def test_test_runner_enforces_output_limit_during_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            ws = WorkspaceAdapter(folder)
            runner = TestRunner(ws, timeout_seconds=10)
            original = sermax_workspace.ALLOWED_TESTS["compileall"]
            try:
                sermax_workspace.ALLOWED_TESTS["compileall"] = (
                    sys.executable, "-c",
                    "import sys; sys.stdout.write('x' * 200000); sys.stdout.flush()",
                )
                result = runner.run("compileall")
                self.assertEqual(result["status"], "output_limit")
                self.assertTrue(result["truncated"])
            finally:
                sermax_workspace.ALLOWED_TESTS["compileall"] = original

    def test_backup_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            root = Path(folder)
            (root / ".sermax_dev_backups").symlink_to(Path(outside), target_is_directory=True)
            (root / "file.txt").write_text("old", encoding="utf-8")
            ws = WorkspaceAdapter(root)
            with self.assertRaises(WorkspaceError):
                ws.write_text("file.txt", "new")


    def test_isolated_workspace_copy_excludes_credentials_and_build_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "workspace"
            root.mkdir()
            (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / ".venv-jarvis").mkdir()
            (root / ".venv-jarvis" / "secretless-runtime.txt").write_text("runtime")
            (root / ".deps" / "pestinha").mkdir(parents=True)
            (root / ".deps" / "pestinha" / "brain.py").write_text("VALUE = 2")
            (root / ".sermax_dev_backups").mkdir()
            (root / ".sermax_dev_backups" / "old.py").write_text("OLD = 1")
            workspace = WorkspaceAdapter(root)
            runner = TestRunner(workspace, isolate_as_nobody=True)
            with tempfile.TemporaryDirectory() as temporary:
                with patch("sermax_workspace.subprocess.run") as mocked:
                    sandbox = runner._prepare_isolated_workspace(temporary)
                self.assertTrue((sandbox / "module.py").is_file())
                self.assertTrue((sandbox / ".deps" / "pestinha" / "brain.py").is_file())
                self.assertFalse((sandbox / ".venv-jarvis").exists())
                self.assertFalse((sandbox / ".sermax_dev_backups").exists())
                self.assertEqual(mocked.call_count, 2)

    def test_windows_install_path_is_rejected_by_path_guard(self):
        self.assertTrue(sermax_workspace._is_inside_windows_install(r"C:\\SERMAX"))
        self.assertTrue(sermax_workspace._is_inside_windows_install(r"C:\\SERMAX\\workspace"))
        self.assertFalse(sermax_workspace._is_inside_windows_install(r"C:\\SERMAX_DEV"))

    def test_restore_sandbox_ownership_for_temporary_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            sandbox = Path(folder) / "workspace"
            sandbox.mkdir()
            runner = TestRunner(WorkspaceAdapter(folder), isolate_as_nobody=True)
            with patch("sermax_workspace.subprocess.run") as mocked:
                runner._restore_sandbox_ownership(sandbox)
            args = mocked.call_args.args[0]
            self.assertEqual(args[:4], ["sudo", "-n", "chown", "-R"])
            self.assertEqual(args[4], f"{os.getuid()}:{os.getgid()}")
            self.assertEqual(args[5], str(sandbox))
            self.assertTrue(mocked.call_args.kwargs["check"])

if __name__ == "__main__":
    unittest.main()
