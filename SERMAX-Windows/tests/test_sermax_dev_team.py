import tempfile
import unittest
from pathlib import Path

from sermax_dev_team import DevelopmentTeam


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


if __name__ == "__main__":
    unittest.main()
