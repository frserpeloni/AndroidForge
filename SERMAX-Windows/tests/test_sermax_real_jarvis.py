import os
import unittest
from pathlib import Path
from unittest.mock import patch

from sermax_jarvis_adapter import JarvisAdapter


class TestRealOpenJarvisWorker(unittest.TestCase):
    def test_worker_imports_sdk_and_reports_unavailable_ollama(self):
        python = os.environ.get("SERMAX_JARVIS_PYTHON")
        if not python or not Path(python).is_file():
            self.skipTest("Ambiente Python 3.13 do OpenJarvis não configurado.")
        root = Path(__file__).resolve().parents[1]
        with patch.dict(os.environ, {
            "SERMAX_ROOT": str(root),
            "SERMAX_JARVIS_PYTHON": python,
            "OLLAMA_HOST": "http://127.0.0.1:1",
        }):
            adapter = JarvisAdapter(
                model="sermax",
                python_executable=python,
                worker_path=str(root / "sermax_jarvis_worker.py"),
                timeout=30,
            )
            with self.assertRaises(RuntimeError) as error:
                adapter.responder("Teste de comunicação.")
        self.assertIn("Ollama", str(error.exception))


if __name__ == "__main__":
    unittest.main()
