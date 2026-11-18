import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import server
import ocr_service


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
        })) as mocked, patch.object(server, "get_ocr_engine_status", return_value={
            "status": "ready", "languages": ["eng", "por"], "missing_languages": [],
            "detail": "Tesseract pronto."
        }):
            response = self.client.get("/api/engines/status", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ollama"]["reachable"])
        self.assertEqual(payload["ollama"]["models"], ["sermax:latest", "qwen2.5:7b"])
        self.assertFalse(payload["inference_started"])
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["ocr"]["status"], "ready")
        self.assertEqual(payload["ocr"]["languages"], ["eng", "por"])
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/tags")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(mocked.call_args.kwargs["timeout"], 1.5)

    def test_status_reports_ollama_offline_without_failing_endpoint(self):
        with patch.object(server.urllib.request, "urlopen", side_effect=server.urllib.error.URLError("offline")), \
             patch.object(server, "get_ocr_engine_status", return_value={
                 "status": "engine_unavailable", "languages": [],
                 "missing_languages": ["por", "eng"], "detail": "Tesseract não encontrado."
             }):
            response = self.client.get("/api/engines/status", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ollama"]["reachable"])
        self.assertFalse(payload["inference_started"])


    def test_ocr_diagnostic_reports_missing_executable_without_running_process(self):
        with patch.object(ocr_service, "_tesseract_path", return_value=None), \
             patch.object(ocr_service.subprocess, "run") as run:
            status = ocr_service.get_ocr_engine_status()
        self.assertEqual(status["status"], "engine_unavailable")
        run.assert_not_called()

    def test_ocr_diagnostic_checks_required_languages(self):
        result = type("Result", (), {
            "returncode": 0,
            "stdout": 'List of available languages (2):\\neng\\npor\\n',
            "stderr": "",
        })()
        with patch.object(ocr_service, "_tesseract_path", return_value="C:/fake/tesseract.exe"), \
             patch.object(ocr_service.subprocess, "run", return_value=result) as run:
            status = ocr_service.get_ocr_engine_status()
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["languages"], ["eng", "por"])
        self.assertEqual(run.call_args.args[0], ["C:/fake/tesseract.exe", "--list-langs"])
        self.assertEqual(run.call_args.kwargs["timeout"], 2)

    def test_ocr_diagnostic_identifies_missing_portuguese_data(self):
        result = type("Result", (), {
            "returncode": 0, "stdout": "List of available languages (1):\\neng\\n", "stderr": ""
        })()
        with patch.object(ocr_service, "_tesseract_path", return_value="C:/fake/tesseract.exe"), \
             patch.object(ocr_service.subprocess, "run", return_value=result):
            status = ocr_service.get_ocr_engine_status()
        self.assertEqual(status["status"], "language_unavailable")
        self.assertEqual(status["missing_languages"], ["por"])

    def test_ocr_diagnostic_timeout_is_bounded(self):
        with patch.object(ocr_service, "_tesseract_path", return_value="C:/fake/tesseract.exe"), \
             patch.object(ocr_service.subprocess, "run", side_effect=ocr_service.subprocess.TimeoutExpired("tesseract", 2)):
            status = ocr_service.get_ocr_engine_status()
        self.assertEqual(status["status"], "timeout")

    def test_status_reports_last_backend_without_exposing_session(self):
        class Core:
            sessao = [{"role": "user", "content": "conteúdo privado da conversa"}]
            ultimo_diagnostico_roteamento = {
                "backend": "openjarvis",
                "fallback": None,
            }

        server.CORE_MODULE = Core
        with patch.object(server.urllib.request, "urlopen", side_effect=server.urllib.error.URLError("offline")), \
             patch.object(server, "get_ocr_engine_status", return_value={
                 "status": "engine_unavailable", "languages": [],
                 "missing_languages": ["por", "eng"], "detail": "Tesseract não encontrado."
             }):
            response = self.client.get("/api/engines/status", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["last_route"]["backend"], "openjarvis")
        self.assertNotIn("conteúdo privado", response.text)


if __name__ == "__main__":
    unittest.main()
