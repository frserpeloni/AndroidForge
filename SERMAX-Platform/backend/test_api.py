import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import server


class FakeCore:
    @staticmethod
    def perguntar(message):
        return "Resposta de teste: " + message


class PlatformApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "test.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        self.client = TestClient(server.app)
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_health_reports_service(self):
        response = self.client.get("/api/health", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "online")

    def test_empty_message_is_rejected(self):
        response = self.client.post(
            "/api/chat", json={"message": " "}, headers=self.headers
        )
        self.assertEqual(response.status_code, 422)

    def test_untrusted_origin_is_rejected(self):
        response = self.client.get(
            "/api/health",
            headers={**self.headers, "origin": "https://example.invalid"},
        )
        self.assertEqual(response.status_code, 403)

    def test_chat_is_saved_and_can_be_reopened(self):
        server.CORE_MODULE = FakeCore
        response = self.client.post(
            "/api/chat", json={"message": "Olá MAX"}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]
        history = self.client.get(
            f"/api/conversations/{conversation_id}", headers=self.headers
        )
        self.assertEqual(history.status_code, 200)
        messages = history.json()["messages"]
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertTrue(all(item["status"] == "complete" for item in messages))

    def test_failed_core_marks_user_message_as_error(self):
        with patch.object(server, "load_core", side_effect=RuntimeError("núcleo offline")):
            response = self.client.post(
                "/api/chat", json={"message": "Teste falha"}, headers=self.headers
            )
        self.assertEqual(response.status_code, 503)
        conversations = self.client.get("/api/conversations", headers=self.headers).json()
        conversation_id = conversations[0]["id"]
        history = self.client.get(
            f"/api/conversations/{conversation_id}", headers=self.headers
        ).json()
        self.assertEqual(history["messages"][0]["status"], "error")

    def test_project_create_update_and_archive(self):
        created = self.client.post(
            "/api/projects",
            json={"name": "Projeto SERMAX", "description": "Teste", "instructions": "Contexto"},
            headers=self.headers,
        )
        self.assertEqual(created.status_code, 201)
        project_id = created.json()["id"]
        updated = self.client.put(
            f"/api/projects/{project_id}",
            json={"description": "Descrição atualizada"},
            headers=self.headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["description"], "Descrição atualizada")
        archived = self.client.post(
            f"/api/projects/{project_id}/archive", headers=self.headers
        )
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.json()["archived"], 1)
        self.assertEqual(
            self.client.get("/api/projects", headers=self.headers).json(), []
        )
        self.assertEqual(
            self.client.get(f"/api/projects/{project_id}", headers=self.headers).status_code,
            404,
        )

    def test_conversation_is_associated_with_project(self):
        project = self.client.post(
            "/api/projects", json={"name": "Projeto A"}, headers=self.headers
        ).json()
        server.CORE_MODULE = FakeCore
        response = self.client.post(
            "/api/chat",
            json={"message": "Mensagem do projeto", "project_id": project["id"]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]
        history = self.client.get(
            f"/api/conversations/{conversation_id}", headers=self.headers
        ).json()
        self.assertEqual(history["conversation"]["project_id"], project["id"])
        project_conversations = self.client.get(
            f"/api/projects/{project['id']}/conversations", headers=self.headers
        ).json()
        self.assertEqual(project_conversations[0]["id"], conversation_id)

    def test_archived_project_rejects_new_conversation(self):
        project = self.client.post(
            "/api/projects", json={"name": "Projeto arquivado"}, headers=self.headers
        ).json()
        self.client.post(f"/api/projects/{project['id']}/archive", headers=self.headers)
        response = self.client.post(
            "/api/chat",
            json={"message": "Não deve entrar", "project_id": project["id"]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
