import tempfile
import unittest
import sys

import sermax_workspace
from pathlib import Path

from sermax_workspace import WorkspaceAdapter, TestRunner, WorkspaceError


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
            for name in ("../outside.txt", "..\\\\outside.txt", "memoria_sermax.json",
                         "memoria_neural_pestinha.json", ".git/config"):
                with self.subTest(name=name), self.assertRaises(WorkspaceError):
                    ws.read_text(name)

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
            (root / "tests").mkdir()
            ws = WorkspaceAdapter(root)
            runner = TestRunner(ws)
            with self.assertRaises(WorkspaceError):
                runner.run("arbitrary-shell")
            result = runner.run("unittest")
            self.assertEqual(result["status"], "passed")


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

if __name__ == "__main__":
    unittest.main()
