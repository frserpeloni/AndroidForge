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
            "/api/chat",
            json={"message": " "},
            headers=self.headers,
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


if __name__ == "__main__":
    unittest.main()
