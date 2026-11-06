import json
import tempfile
import unittest
from pathlib import Path

from sermax_workspace import WorkspaceAdapter
from sermax_dev_proposal import (
    ProposalError, apply_proposal, apply_and_test_proposal, parse_proposal, preview_proposal,
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
        }), json.dumps({
            "summary": "x", "files": [{"path": "a.py", "content": "x"}],
            "tests": ["compileall"],
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
        for protected in (
            ".github/workflows/ci.yml", "sermax_github_agent_runner.py",
            "sermax_groq_backend.py", "sermax_dev_team.py",
            "memoria_sermax.json", "settings.json", "setup.ps1", "../outside.py",\n            "SERMAX_terminal/sermax_terminal.py",
        ):
            with self.subTest(path=protected), self.assertRaises(ProposalError):
                parse_proposal(json.dumps({
                    "summary": "x",
                    "files": [{"path": protected, "content": "x"}],
                    "tests": ["unittest"],
                }))

    def test_apply_and_test_rolls_back_when_tests_fail(self):
        class FailedRunner:
            def run(self, suite):
                return {"suite": suite, "status": "failed", "returncode": 1, "output": "failure"}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "module.py").write_text("ORIGINAL = True\n", encoding="utf-8")
            workspace = WorkspaceAdapter(root)
            proposal = parse_proposal(json.dumps({
                "summary": "Atualização com teste falho",
                "files": [
                    {"path": "module.py", "content": "BROKEN = True\n"},
                    {"path": "new_module.py", "content": "NEW = True\n"},
                ],
                "tests": ["unittest"],
            }))
            with self.assertRaises(RuntimeError):
                apply_and_test_proposal(workspace, proposal, FailedRunner())
            self.assertEqual(workspace.read_text("module.py"), "ORIGINAL = True\n")
            self.assertFalse((root / "new_module.py").exists())


if __name__ == "__main__":
    unittest.main()
