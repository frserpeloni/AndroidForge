import json
import os
import tempfile
import unittest
from unittest.mock import patch
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
        invalid = (
            "not-json",
            "{}",
            json.dumps({
                "summary": "x", "files": [{"path": "a.py", "content": "x"}],
                "tests": ["powershell"],
            }),
            json.dumps({
                "summary": "x", "files": [{"path": "a.py", "content": "x"}],
                "tests": ["compileall"],
            }),
        )
        for raw in invalid:
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
        protected_paths = (
            ".github/workflows/ci.yml",
            "sermax_github_agent_runner.py",
            "sermax_groq_backend.py",
            "sermax_dev_team.py",
            "memoria_sermax.json",
            "settings.json",
            "setup.ps1",
            "../outside.py",
            "SERMAX_terminal/sermax_terminal.py",
        )
        for protected in protected_paths:
            with self.subTest(path=protected), self.assertRaises(ProposalError):
                parse_proposal(json.dumps({
                    "summary": "x",
                    "files": [{"path": protected, "content": "x"}],
                    "tests": ["unittest"],
                }))

    def test_test_only_mode_accepts_only_new_regression_test_files(self):
        valid = json.dumps({
            "summary": "Teste de regressão",
            "files": [{
                "path": "tests/test_sermax_core_regression.py",
                "content": "import unittest\\n",
            }],
            "tests": ["unittest"],
        })
        with patch.dict(os.environ, {"SERMAX_DEV_TEST_ONLY": "1"}):
            proposal = parse_proposal(valid)
            self.assertEqual(
                proposal.files[0].path,
                "tests/test_sermax_core_regression.py",
            )
            for path in (
                "sermax_core.py",
                "sermax_jarvis_adapter.py",
                "tests/test_sermax_core.py",
                "docs/notes.md",
            ):
                raw = json.dumps({
                    "summary": "Teste de regressão",
                    "files": [{"path": path, "content": "x"}],
                    "tests": ["unittest"],
                })
                with self.subTest(path=path), self.assertRaises(ProposalError):
                    parse_proposal(raw)

    def test_test_only_mode_rejects_overwriting_existing_regression_test(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tests").mkdir()
            target = root / "tests" / "test_sermax_core_regression.py"
            target.write_text("ORIGINAL = True\\n", encoding="utf-8")
            workspace = WorkspaceAdapter(root)
            raw = json.dumps({
                "summary": "Teste de regressão",
                "files": [{
                    "path": "tests/test_sermax_core_regression.py",
                    "content": "CHANGED = True\\n",
                }],
                "tests": ["unittest"],
            })
            with patch.dict(os.environ, {"SERMAX_DEV_TEST_ONLY": "1"}):
                proposal = parse_proposal(raw)
                with self.assertRaises(ProposalError):
                    preview_proposal(workspace, proposal)
            self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL = True\\n")

    def test_exact_match_edits_preview_and_apply(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sermax_core.py").write_text(
                "def command():\n    return old_value\n", encoding="utf-8"
            )
            workspace = WorkspaceAdapter(root)
            raw = json.dumps({
                "summary": "Corrige um trecho localizado",
                "files": [{
                    "path": "sermax_core.py",
                    "content": None,
                    "edits": [{
                        "old": "    return old_value\n",
                        "new": "    return new_value\n",
                    }],
                }],
                "tests": ["unittest"],
            })
            proposal = parse_proposal(raw)
            diff = preview_proposal(workspace, proposal)[0]["diff"]
            self.assertIn("-    return old_value", diff)
            self.assertIn("+    return new_value", diff)
            self.assertEqual(apply_proposal(workspace, proposal), ["sermax_core.py"])
            self.assertEqual(
                workspace.read_text("sermax_core.py"),
                "def command():\n    return new_value\n",
            )

    def test_exact_match_edits_reject_missing_or_ambiguous_old_text(self):
        for source, expected_count in (
            ("value = 2\n", 0),
            ("value = 1\nvalue = 1\n", 2),
        ):
            with self.subTest(expected_count=expected_count), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "module.py").write_text(source, encoding="utf-8")
                workspace = WorkspaceAdapter(root)
                proposal = parse_proposal(json.dumps({
                    "summary": "Edição exata",
                    "files": [{
                        "path": "module.py",
                        "content": None,
                        "edits": [{"old": "value = 1\n", "new": "value = 2\n"}],
                    }],
                    "tests": ["unittest"],
                }))
                with self.assertRaisesRegex(
                    ProposalError, f"ocorrências encontradas: {expected_count}"
                ):
                    preview_proposal(workspace, proposal)

    def test_edit_proposal_rejects_both_content_and_edits(self):
        raw = json.dumps({
            "summary": "Ambíguo",
            "files": [{
                "path": "module.py",
                "content": "value = 1\\n",
                "edits": [{"old": "value = 1", "new": "value = 2"}],
            }],
            "tests": ["unittest"],
        })
        with self.assertRaises(ProposalError):
            parse_proposal(raw)

    def test_proposal_path_allowlist_enforces_exact_paths(self):
        allowed = "sermax_core.py;tests/test_sermax_core_command_regression.py"
        with patch.dict(os.environ, {"SERMAX_DEV_ALLOWED_PATHS": allowed}):
            proposal = parse_proposal(json.dumps({
                "summary": "Correção permitida",
                "files": [{
                    "path": "sermax_core.py",
                    "content": None,
                    "edits": [{"old": "old", "new": "new"}],
                }],
                "tests": ["unittest"],
            }))
            self.assertEqual(proposal.files[0].path, "sermax_core.py")
            for path in ("sermax_executor.py", "docs/notes.md"):
                with self.subTest(path=path), self.assertRaises(ProposalError):
                    parse_proposal(json.dumps({
                        "summary": "Fora do escopo",
                        "files": [{"path": path, "content": "x"}],
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
