import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import server


class MemoryCore:
    historico = [
        {"role": "user", "content": "Meu carro é um Fiat Siena 2008."},
        {"role": "assistant", "content": "Resposta que não deve aparecer."},
        {"role": "user", "content": "Prefiro respostas em português."},
        {"role": "user", "content": "   "},
        {"role": "system", "content": "Instrução interna."},
    ]


class ReadOnlyMemoryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "memory.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        self.client = TestClient(server.app, client=("127.0.0.1", 50131))
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_memory_panel_does_not_load_core_or_read_a_file(self):
        with patch.object(server, "load_core", side_effect=AssertionError("não deve carregar o núcleo")):
            response = self.client.get("/api/memory", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "core_not_loaded")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["items"], [])

    def test_memory_endpoint_returns_only_user_memory_entries(self):
        server.CORE_MODULE = MemoryCore
        response = self.client.get("/api/memory", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "available")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["total"], 2)
        self.assertEqual(
            [item["content"] for item in payload["items"]],
            ["Prefiro respostas em português.", "Meu carro é um Fiat Siena 2008."],
        )

    def test_memory_search_and_limit_are_applied(self):
        server.CORE_MODULE = MemoryCore
        response = self.client.get(
            "/api/memory?q=Fiat&limit=1",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["items"][0]["content"], "Meu carro é um Fiat Siena 2008.")

    def test_invalid_limit_and_query_length_are_rejected(self):
        self.assertEqual(
            self.client.get("/api/memory?limit=101", headers=self.headers).status_code,
            422,
        )
        self.assertEqual(
            self.client.get("/api/memory?q=" + ("x" * 201), headers=self.headers).status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
