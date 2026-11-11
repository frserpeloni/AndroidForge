import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from sermax_jarvis_adapter import JarvisAdapter


class OllamaMockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/tags":
            self.send_error(404)
            return
        body = json.dumps({
            "models": [{"name": "sermax", "model": "sermax"}]
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if self.path != "/api/chat":
            self.send_error(404)
            return
        self.server.last_request = request
        payload = {
            "model": request.get("model", "sermax"),
            "message": {"role": "assistant", "content": "SERMAX JARVIS CI OK"},
            "done": True,
            "prompt_eval_count": 4,
            "eval_count": 5,
            "total_duration": 1000000,
            "load_duration": 100000,
            "prompt_eval_duration": 100000,
            "eval_duration": 800000,
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


class TestRealOpenJarvisWorker(unittest.TestCase):
    def test_sdk_runs_in_separate_python_process_against_ollama_protocol(self):
        python = os.environ.get("SERMAX_JARVIS_PYTHON")
        if not python or not Path(python).is_file():
            self.skipTest("Ambiente Python 3.13 do OpenJarvis não configurado.")

        root = Path(__file__).resolve().parents[1]
        server = ThreadingHTTPServer(("127.0.0.1", 0), OllamaMockHandler)
        server.last_request = None
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host = f"http://127.0.0.1:{server.server_port}"
        try:
            with patch.dict(os.environ, {
                "OLLAMA_HOST": host,
                "SERMAX_ROOT": str(root),
                "SERMAX_JARVIS_PYTHON": python,
            }):
                adapter = JarvisAdapter(
                    model="sermax",
                    python_executable=python,
                    worker_path=str(root / "sermax_jarvis_worker.py"),
                    timeout=60,
                )
                answer = adapter.responder("Responda com uma confirmação curta.")
            self.assertEqual(answer, "SERMAX JARVIS CI OK")
            self.assertEqual(server.last_request["model"], "sermax")
            tool_defs = server.last_request.get("tools") or []
            tool_names = {item.get("function", {}).get("name") for item in tool_defs}
            self.assertTrue({"calculator", "think"}.issubset(tool_names))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
