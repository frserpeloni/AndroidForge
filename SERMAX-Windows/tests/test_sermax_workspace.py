import tempfile
import unittest
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
            for name in ("../outside.txt", "memoria_sermax.json",
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


if __name__ == "__main__":
    unittest.main()
