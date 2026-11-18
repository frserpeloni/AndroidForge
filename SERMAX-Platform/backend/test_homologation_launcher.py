import sys
import tempfile
import unittest
from unittest.mock import patch
import types
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import run_homologation


class HomologationLauncherTests(unittest.TestCase):
    def test_launcher_redirects_memory_and_database_to_temp_and_preserves_engine_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory) / "isolated"
            environment = run_homologation.prepare_environment(
                temp_root,
                {
                    "SERMAX_ROOT": "C:/SERMAX",
                    "SERMAX_PLATFORM_DATA": "C:/SERMAX/data",
                    "SERMAX_CORE_DIR": "C:/SERMAX",
                    "SERMAX_JARVIS_PYTHON": "C:/SERMAX/.venv-jarvis/Scripts/python.exe",
                    "SERMAX_TESSERACT_CMD": "C:/Program Files/Tesseract-OCR/tesseract.exe",
                },
            )

            self.assertEqual(Path(environment["SERMAX_ROOT"]), temp_root.resolve())
            self.assertEqual(
                Path(environment["SERMAX_PLATFORM_DATA"]),
                (temp_root / "platform-data").resolve(),
            )
            self.assertEqual(
                Path(environment["SERMAX_CORE_DIR"]),
                run_homologation.CORE_DIR.resolve(),
            )
            self.assertEqual(
                environment["SERMAX_JARVIS_PYTHON"],
                "C:/SERMAX/.venv-jarvis/Scripts/python.exe",
            )
            self.assertEqual(
                environment["SERMAX_TESSERACT_CMD"],
                "C:/Program Files/Tesseract-OCR/tesseract.exe",
            )
            copied_worker = temp_root / "sermax_jarvis_worker.py"
            self.assertTrue(copied_worker.is_file())
            self.assertEqual(copied_worker.read_bytes(), run_homologation.WORKER_SOURCE.read_bytes())
            self.assertFalse((temp_root / "memoria_sermax.json").exists())
            self.assertFalse((temp_root / "memoria_neural_pestinha.json").exists())

    def test_launcher_blocks_commands_and_plan_execution(self):
        executor = types.ModuleType("sermax_executor")
        tasks = types.ModuleType("sermax_tarefas")
        executor.executar = lambda *_args, **_kwargs: "executado"
        tasks.executar_plano = lambda *_args, **_kwargs: "executado"
        with patch.dict(sys.modules, {
            "sermax_executor": executor,
            "sermax_tarefas": tasks,
        }):
            run_homologation.apply_safety_guards()
            with self.assertRaisesRegex(RuntimeError, "bloqueadas"):
                executor.executar("comando")
            with self.assertRaisesRegex(RuntimeError, "bloqueadas"):
                tasks.executar_plano("plano")


if __name__ == "__main__":
    unittest.main()
