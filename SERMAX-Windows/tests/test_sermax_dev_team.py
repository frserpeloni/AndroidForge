import tempfile
import unittest
from pathlib import Path

from sermax_dev_team import DevelopmentTeam
from sermax_workspace import WorkspaceAdapter, TestRunner


class DevelopmentTeamTests(unittest.TestCase):
    def test_roles_share_one_model_callback_and_run_sequentially(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def model_call(role, prompt):
                calls.append((role, prompt))
                return f"resultado-{role}"

            team = DevelopmentTeam(Path(folder) / "team.sqlite3", model_call)
            task_id = team.enqueue(
                "Corrigir teste", "Falha reproduzida",
                roles=("analista", "programador", "testador"),
            )
            self.assertEqual(team.run_next(), task_id)
            task = team.get_task(task_id)
            self.assertEqual(task["status"], "completed")
            self.assertEqual([role for role, _ in calls],
                             ["analista", "programador", "testador"])
            self.assertTrue(all("Corrigir teste" in prompt for _, prompt in calls))
            self.assertEqual(len(team.events(task_id)), 6)

    def test_queue_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "team.sqlite3"
            first = DevelopmentTeam(path, lambda role, prompt: "ok")
            task_id = first.enqueue("Inspecionar código")
            second = DevelopmentTeam(path, lambda role, prompt: "ok")
            self.assertEqual(second.get_task(task_id)["status"], "queued")

    def test_rejects_unknown_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            team = DevelopmentTeam(Path(folder) / "team.sqlite3", lambda r, p: "ok")
            with self.assertRaises(ValueError):
                team.enqueue("Tarefa", roles=("shell",))

    def test_missing_model_does_not_claim_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            team = DevelopmentTeam(Path(folder) / "team.sqlite3")
            task_id = team.enqueue("Tarefa")
            with self.assertRaises(RuntimeError):
                team.run_next()
            self.assertEqual(team.get_task(task_id)["status"], "queued")

    def test_programmer_proposal_is_applied_and_testador_must_approve(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tests").mkdir()
            (root / "tests" / "test_generated.py").write_text(
                "import unittest\\nclass GeneratedTests(unittest.TestCase):\\n"
                "    def test_value(self):\\n        self.assertEqual(2 + 2, 4)\\n",
                encoding="utf-8")
            workspace = WorkspaceAdapter(root)
            runner = TestRunner(workspace)
            def model_call(role, prompt):
                if role == "programador":
                    return '{"summary":"Gera módulo","files":[{"path":"generated.py",'
                    '"content":"VALUE = 42\\\\n"}],"tests":["unittest"]}'
                if role == "testador":
                    self.assertIn('"status": "passed"', prompt)
                    return '{"verdict":"PASS","evidence":"unittest retornou passed"}'
                return f"resultado-{role}"
            team = DevelopmentTeam(Path(folder) / "team.sqlite3", model_call,
                                   workspace_adapter=workspace, test_runner=runner)
            task_id = team.enqueue("Criar módulo")
            team.run_next()
            self.assertEqual(team.get_task(task_id)["status"], "completed")
            self.assertEqual(workspace.read_text("generated.py"), "VALUE = 42\\n")
            self.assertTrue(any(event["role"] == "testador" for event in team.events(task_id)))

    def test_testador_rejection_fails_autonomous_task(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tests").mkdir()
            (root / "tests" / "test_ok.py").write_text(
                "import unittest\\nclass T(unittest.TestCase):\\n"
                "    def test_ok(self): self.assertTrue(True)\\n",
                encoding="utf-8")
            workspace = WorkspaceAdapter(root)
            runner = TestRunner(workspace)
            def model_call(role, prompt):
                if role == "programador":
                    return '{"summary":"gera","files":[{"path":"created.py",'
                    '"content":"OK = True\\\\n"}],"tests":["unittest"]}'
                if role == "testador":
                    return '{"verdict":"FAIL","evidence":"revisão reprovada"}'
                return "análise"
            team = DevelopmentTeam(Path(folder) / "team.sqlite3", model_call,
                                   workspace_adapter=workspace, test_runner=runner)
            task_id = team.enqueue("Criar arquivo")
            with self.assertRaises(RuntimeError):
                team.run_next()
            self.assertEqual(team.get_task(task_id)["status"], "failed")

    def test_workspace_and_runner_must_be_configured_together(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = WorkspaceAdapter(folder)
            with self.assertRaises(ValueError):
                DevelopmentTeam(Path(folder) / "team.sqlite3", lambda r, p: "ok",
                                workspace_adapter=workspace)


if __name__ == "__main__":
    unittest.main()
