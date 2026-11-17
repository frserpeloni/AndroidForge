import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import server


class RaisingCore:
    sessao = [{"role": "assistant", "content": "sessao original"}]

    @classmethod
    def perguntar(cls, message):
        cls.sessao.append({"role": "user", "content": message})
        raise RuntimeError("falha simulada depois de alterar a sessao")


class CoreSessionContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "contract.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        self.client = TestClient(server.app, client=("127.0.0.1", 50111))
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_global_core_session_is_restored_when_core_raises(self):
        original_session = RaisingCore.sessao
        server.CORE_MODULE = RaisingCore

        response = self.client.post(
            "/api/chat",
            json={"message": "Solicitacao que falha"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 503)
        self.assertIs(RaisingCore.sessao, original_session)
        self.assertEqual(
            RaisingCore.sessao,
            [{"role": "assistant", "content": "sessao original"}],
        )

        conversations = self.client.get(
            "/api/conversations", headers=self.headers
        ).json()
        history = self.client.get(
            f"/api/conversations/{conversations[0]['id']}",
            headers=self.headers,
        ).json()
        self.assertEqual(history["messages"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
