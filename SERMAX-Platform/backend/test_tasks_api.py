import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import server


class PersistentTaskApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "tasks.sqlite3"
        server.initialize_database()
        self.client = TestClient(server.app, client=("127.0.0.1", 50121))
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_create_and_list_tasks_with_priority_order(self):
        normal = self.client.post(
            "/api/tasks",
            json={"title": "Tarefa normal"},
            headers=self.headers,
        )
        urgent = self.client.post(
            "/api/tasks",
            json={"title": "Tarefa urgente", "priority": "urgent"},
            headers=self.headers,
        )
        self.assertEqual(normal.status_code, 201)
        self.assertEqual(urgent.status_code, 201)

        tasks = self.client.get("/api/tasks", headers=self.headers).json()
        self.assertEqual([task["title"] for task in tasks], ["Tarefa urgente", "Tarefa normal"])
        self.assertEqual(tasks[0]["status"], "pending")

    def test_update_task_and_complete_status(self):
        created = self.client.post(
            "/api/tasks",
            json={"title": "Revisar Plataforma", "description": "Primeira descrição"},
            headers=self.headers,
        ).json()
        task_id = created["id"]

        updated = self.client.put(
            f"/api/tasks/{task_id}",
            json={"title": "Revisar SERMAX", "priority": "high"},
            headers=self.headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["title"], "Revisar SERMAX")
        self.assertEqual(updated.json()["priority"], "high")

        completed = self.client.patch(
            f"/api/tasks/{task_id}/status",
            json={"status": "completed"},
            headers=self.headers,
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertIsNotNone(completed.json()["completed_at"])

        pending = self.client.get("/api/tasks?status=pending", headers=self.headers)
        self.assertEqual(pending.json(), [])

    def test_invalid_due_date_is_rejected(self):
        response = self.client.post(
            "/api/tasks",
            json={"title": "Data inválida", "due_at": "amanhã"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_invalid_status_filter_is_rejected(self):
        response = self.client.get("/api/tasks?status=executing", headers=self.headers)
        self.assertEqual(response.status_code, 422)

    def test_task_survives_database_reopen(self):
        created = self.client.post(
            "/api/tasks",
            json={"title": "Persistir tarefa", "priority": "high"},
            headers=self.headers,
        ).json()
        task_id = created["id"]

        self.client.close()
        server.initialize_database()
        restarted = TestClient(server.app, client=("127.0.0.1", 50122))
        try:
            response = restarted.get(f"/api/tasks/{task_id}", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["title"], "Persistir tarefa")
            self.assertEqual(response.json()["priority"], "high")
        finally:
            restarted.close()


    def test_null_update_fields_are_rejected_without_corrupting_task(self):
        created = self.client.post(
            "/api/tasks",
            json={"title": "Tarefa íntegra"},
            headers=self.headers,
        ).json()
        task_id = created["id"]

        for payload in ({"title": None}, {"description": None}, {"priority": None}):
            response = self.client.put(
                f"/api/tasks/{task_id}",
                json=payload,
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 422)

        unchanged = self.client.get(f"/api/tasks/{task_id}", headers=self.headers)
        self.assertEqual(unchanged.status_code, 200)
        self.assertEqual(unchanged.json()["title"], "Tarefa íntegra")
        self.assertEqual(unchanged.json()["priority"], "normal")



if __name__ == "__main__":
    unittest.main()
