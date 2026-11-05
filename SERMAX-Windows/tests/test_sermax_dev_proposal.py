import json
import tempfile
import unittest
from pathlib import Path

from sermax_workspace import WorkspaceAdapter
from sermax_dev_proposal import (
    ProposalError, apply_proposal, parse_proposal, preview_proposal,
)


class DevelopmentProposalTests(unittest.TestCase):
    def test_parse_preview_and_apply_structured_proposal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "src" / "module.py").write_text("old = 1\n", encoding="utf-8")
            workspace = WorkspaceAdapter(root)
            raw = json.dumps({
                "summary": "Atualiza módulo de teste",
                "files": [{"path": "src/module.py", "content": "new = 2\n"}],
                "tests": ["unittest", "compileall"],
            })
            proposal = parse_proposal(raw)
            self.assertIn("-old = 1", preview_proposal(workspace, proposal)[0]["diff"])
            self.assertEqual(apply_proposal(workspace, proposal), ["src/module.py"])
            self.assertEqual(workspace.read_text("src/module.py"), "new = 2\n")
            self.assertEqual(
                (root / ".sermax_dev_backups" / "src" / "module.py").read_text(encoding="utf-8"),
                "old = 1\n",
            )

    def test_rejects_invalid_json_schema_and_test_command(self):
        for raw in ("not-json", "{}", json.dumps({
            "summary": "x", "files": [{"path": "a.py", "content": "x"}],
            "tests": ["powershell"],
        })):
            with self.subTest(raw=raw), self.assertRaises(ProposalError):
                parse_proposal(raw)

    def test_rejects_duplicate_and_protected_paths(self):
        duplicate = json.dumps({
            "summary": "x",
            "files": [
                {"path": "src/a.py", "content": "1"},
                {"path": "SRC/A.PY", "content": "2"},
            ],
            "tests": ["unittest"],
        })
        with self.assertRaises(ProposalError):
            parse_proposal(duplicate)
        with tempfile.TemporaryDirectory() as folder:
            workspace = WorkspaceAdapter(folder)
            blocked = parse_proposal(json.dumps({
                "summary": "x",
                "files": [{"path": "../outside.py", "content": "x"}],
                "tests": ["unittest"],
            }))
            with self.assertRaises(ProposalError):
                apply_proposal(workspace, blocked)
            self.assertFalse((Path(folder).parent / "outside.py").exists())


if __name__ == "__main__":
    unittest.main()
