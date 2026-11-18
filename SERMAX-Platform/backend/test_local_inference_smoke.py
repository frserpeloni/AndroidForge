import contextlib
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_local_inference


class LocalInferenceSmokeTests(unittest.TestCase):
    def test_smoke_test_uses_fixed_prompt_and_reports_local_backend(self):
        fake_core = types.ModuleType("sermax_core")
        fake_core.ultimo_diagnostico_roteamento = {
            "backend": "ollama", "fallback": "OpenJarvis indisponível"
        }
        fake_core.perguntar = lambda prompt: (
            "SERMAX_LOCAL_OK" if prompt == check_local_inference.PROMPT else "prompt incorreto"
        )
        output = io.StringIO()
        with patch.dict(sys.modules, {"sermax_core": fake_core}), \
             patch.object(check_local_inference.run_homologation, "apply_safety_guards"), \
             contextlib.redirect_stdout(output):
            result = check_local_inference.main()

        self.assertEqual(result, 0)
        report = json.loads(output.getvalue()[output.getvalue().index("{"):])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["backend"], "ollama")
        self.assertFalse(report["personal_memory_accessed"])
        self.assertTrue(report["operational_actions_blocked"])
        self.assertFalse(report["external_services_called"])

    def test_smoke_test_reports_engine_failure_without_accessing_personal_memory(self):
        def fail(_prompt):
            raise RuntimeError("Ollama local indisponível")

        fake_core = types.ModuleType("sermax_core")
        fake_core.ultimo_diagnostico_roteamento = {
            "backend": "ollama", "fallback": "OpenJarvis indisponível"
        }
        fake_core.perguntar = fail
        output = io.StringIO()
        with patch.dict(sys.modules, {"sermax_core": fake_core}), \
             patch.object(check_local_inference.run_homologation, "apply_safety_guards"), \
             contextlib.redirect_stdout(output):
            result = check_local_inference.main()

        report = json.loads(output.getvalue()[output.getvalue().index("{"):])
        self.assertEqual(result, 2)
        self.assertEqual(report["status"], "error")
        self.assertFalse(report["personal_memory_accessed"])
        self.assertTrue(report["operational_actions_blocked"])


if __name__ == "__main__":
    unittest.main()
