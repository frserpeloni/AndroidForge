import json
import unittest
from unittest.mock import patch

import sermax_core as core


class FakeOllamaResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        yield (json.dumps({"message": {"content": "Resposta pelo Ollama"}, "done": True}) + "\\n").encode("utf-8")


class TestAutomaticRouting(unittest.TestCase):
    def setUp(self):
        self.motor = core.MOTOR_RESPOSTA
        self.session = list(core.sessao)
        core.sessao.clear()
        core.MOTOR_RESPOSTA = "auto"

    def tearDown(self):
        core.MOTOR_RESPOSTA = self.motor
        core.sessao[:] = self.session

    def _patch_common(self):
        return (
            patch.object(core, "responder_comando_local", return_value=None),
            patch.object(core, "responder_calculo_local", return_value=None),
            patch.object(core, "registrar_memoria"),
            patch.object(core.ferramenta_windows, "responder_consulta", return_value=None),
            patch.object(core, "montar_contexto", return_value=[
                {"role": "system", "content": "Identidade SERMAX"},
                {"role": "user", "content": "Pergunta de teste"},
            ]),
        )

    def test_auto_uses_jarvis_when_adapter_answers(self):
        patches = self._patch_common()
        with patches[0], patches[1], patches[2], patches[3], patches[4], \\
             patch.object(core.sermax_jarvis_adapter, "JarvisAdapter") as adapter, \\
             patch.object(core.urllib.request, "urlopen") as ollama:
            adapter.return_value.responder.return_value = "Resposta pelo Jarvis"
            answer = core._perguntar_impl("Pergunta de teste")
        self.assertEqual(answer, "Resposta pelo Jarvis")
        adapter.return_value.responder.assert_called_once()
        ollama.assert_not_called()

    def test_auto_falls_back_to_ollama_when_jarvis_fails(self):
        patches = self._patch_common()
        with patches[0], patches[1], patches[2], patches[3], patches[4], \\
             patch.object(core.sermax_jarvis_adapter, "JarvisAdapter") as adapter, \\
             patch.object(core.urllib.request, "urlopen", return_value=FakeOllamaResponse()) as ollama:
            adapter.return_value.responder.side_effect = RuntimeError("Jarvis offline")
            answer = core._perguntar_impl("Pergunta de teste")
        self.assertEqual(answer, "Resposta pelo Ollama")
        adapter.return_value.responder.assert_called_once()
        ollama.assert_called_once()

    def test_explicit_jarvis_mode_does_not_silently_fallback(self):
        patches = self._patch_common()
        core.MOTOR_RESPOSTA = "jarvis"
        with patches[0], patches[1], patches[2], patches[3], patches[4], \\
             patch.object(core.sermax_jarvis_adapter, "JarvisAdapter") as adapter, \\
             patch.object(core.urllib.request, "urlopen") as ollama:
            adapter.return_value.responder.side_effect = RuntimeError("Jarvis offline")
            with self.assertRaisesRegex(RuntimeError, "Jarvis offline"):
                core._perguntar_impl("Pergunta de teste")
        ollama.assert_not_called()


if __name__ == "__main__":
    unittest.main()
