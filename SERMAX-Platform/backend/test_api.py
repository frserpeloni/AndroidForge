import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
import server


class PlatformApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "test.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        self.client = TestClient(server.app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_health_reports_service(self):
        response = self.client.get("/api/health", headers={"host": "127.0.0.1:8765"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "online")

    def test_empty_message_is_rejected(self):
        response = self.client.post(
            "/api/chat",
            json={"message": " "},
            headers={"host": "127.0.0.1:8765"},
        )
        self.assertEqual(response.status_code, 422)

    def test_untrusted_origin_is_rejected(self):
        response = self.client.get(
            "/api/health",
            headers={"host": "127.0.0.1:8765", "origin": "https://example.invalid"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
