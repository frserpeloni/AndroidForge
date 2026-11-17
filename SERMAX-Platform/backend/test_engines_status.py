import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import server


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class EngineStatusApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = server.DATA_DIR / "engines.sqlite3"
        server.CORE_MODULE = None
        server.CORE_ERROR = None
        server.initialize_database()
        self.client = TestClient(server.app, client=("127.0.0.1", 50141))
        self.headers = {"host": "127.0.0.1:8765"}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_status_probes_only_local_ollama_and_does_not_start_inference(self):
        with patch.object(server.urllib.request, "urlopen", return_value=FakeResponse({
            "models": [{"name": "sermax:latest"}, {"name": "qwen2.5:7b"}]
        })) as mocked:
            response = self.client.get("/api/engines/status", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ollama"]["reachable"])
        self.assertEqual(payload["ollama"]["models"], ["sermax:latest", "qwen2.5:7b"])
        self.assertFalse(payload["inference_started"])
        self.assertTrue(payload["read_only"])
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/tags")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(mocked.call_args.kwargs["timeout"], 1.5)

    def test_status_reports_ollama_offline_without_failing_endpoint(self):
        with patch.object(server.urllib.request, "urlopen", side_effect=server.urllib.error.URLError("offline")):
            response = self.client.get("/api/engines/status", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ollama"]["reachable"])
        self.assertFalse(payload["inference_started"])

    def test_status_reports_last_backend_without_exposing_session(self):
        class Core:
            sessao = [{"role": "user", "content": "conteúdo privado da conversa"}]
            ultimo_diagnostico_roteamento = {
                "backend": "openjarvis",
                "fallback": None,
            }

        server.CORE_MODULE = Core
        with patch.object(server.urllib.request, "urlopen", side_effect=server.urllib.error.URLError("offline")):
            response = self.client.get("/api/engines/status", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["last_route"]["backend"], "openjarvis")
        self.assertNotIn("conteúdo privado", response.text)


if __name__ == "__main__":
    unittest.main()
