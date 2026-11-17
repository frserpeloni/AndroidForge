import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class CoreStreamingIntegrationTests(unittest.TestCase):
    def test_real_core_emits_cumulative_ollama_snapshots_after_openjarvis_fallback(self):
        repository_root = Path(__file__).resolve().parents[2]
        core_dir = repository_root / "SERMAX-Windows"
        self.assertTrue((core_dir / "sermax_core.py").is_file())

        with tempfile.TemporaryDirectory(prefix="sermax-stream-core-") as isolated_root:
            with patch.dict(
                os.environ,
                {
                    "SERMAX_ROOT": isolated_root,
                    "SERMAX_CORE_DIR": str(core_dir),
                },
            ):
                sys.path.insert(0, str(core_dir))
                try:
                    import sermax_core as core

                    core.sessao = []
                    payloads = [
                        {"message": {"content": "Olá "}, "done": False},
                        {"message": {"content": "MAX"}, "done": False},
                        {"message": {"content": ""}, "done": True},
                    ]
                    response = io.BytesIO(
                        b"".join(
                            (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8")
                            for item in payloads
                        )
                    )
                    snapshots = []

                    with (
                        patch.object(core, "responder_comando_local", return_value=None),
                        patch.object(core, "responder_calculo_local", return_value=None),
                        patch.object(core, "registrar_memoria"),
                        patch.object(core, "montar_contexto", return_value=[
                            {"role": "user", "content": "Teste"}
                        ]),
                        patch.object(core, "selecionar_agente_max", return_value="orchestrator"),
                        patch.object(
                            core.sermax_jarvis_adapter.JarvisAdapter,
                            "responder",
                            side_effect=RuntimeError("OpenJarvis indisponível no teste"),
                        ),
                        patch.object(core.urllib.request, "urlopen", return_value=response),
                    ):
                        answer = core._perguntar_impl("Teste", receber_parte=snapshots.append)

                    self.assertEqual(answer, "Olá MAX")
                    self.assertEqual(snapshots, ["Olá ", "Olá MAX"])
                    self.assertEqual(core.ultimo_diagnostico_roteamento["backend"], "ollama")
                    self.assertIn("OpenJarvis indisponível no teste", core.ultimo_diagnostico_roteamento["fallback"])
                    self.assertEqual(core.sessao[-1], {"role": "assistant", "content": "Olá MAX"})
                    self.assertFalse((Path(isolated_root) / "memoria_sermax.json").exists())
                finally:
                    sys.path.remove(str(core_dir))


if __name__ == "__main__":
    unittest.main()
