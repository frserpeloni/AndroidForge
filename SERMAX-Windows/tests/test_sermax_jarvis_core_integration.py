import unittest
from unittest.mock import patch
import json

import sermax_core as core


class FakeOllamaResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        yield (json.dumps({"message": {"content": "Resposta via Ollama"}, "done": True}) + "\\n").encode("utf-8")


class TestAutomaticJarvisIntegration(unittest.TestCase):
    def setUp(self):
        self.sessao_original = list(core.sessao)
        self.diagnostico_original = dict(core.ultimo_diagnostico_roteamento)
        core.sessao.clear()

    def tearDown(self):
        core.sessao[:] = self.sessao_original
        core.ultimo_diagnostico_roteamento = self.diagnostico_original

    def _isolar_caminho_de_resposta(self, contexto):
        return (
            patch.object(core, "responder_comando_local", return_value=None),
            patch.object(core, "responder_calculo_local", return_value=None),
            patch.object(core, "registrar_memoria"),
            patch.object(core, "montar_contexto", return_value=contexto),
        )

    def test_pergunta_normal_tenta_jarvis_automaticamente_com_contexto_sermax(self):
        contexto = [
            {"role": "system", "content": "IDENTIDADE SERMAX"},
            {"role": "system", "content": "MEMORIA: carro Siena"},
            {"role": "user", "content": "Qual óleo devo usar?"},
        ]
        patches = self._isolar_caminho_de_resposta(contexto)
        with patches[0], patches[1], patches[2], patches[3], patch.object(
            core.sermax_jarvis_adapter, "JarvisAdapter"
        ) as adapter:
            adapter.return_value.responder.return_value = "Resposta OpenJarvis"
            resposta = core._perguntar_impl("Qual óleo devo usar?")
        prompt = adapter.return_value.responder.call_args.args[0]
        self.assertIn("IDENTIDADE SERMAX", prompt)
        self.assertIn("MEMORIA: carro Siena", prompt)
        self.assertIn("Qual óleo devo usar?", prompt)
        self.assertEqual(resposta, "Resposta OpenJarvis")
        self.assertEqual(core.ultimo_diagnostico_roteamento["backend"], "openjarvis")

    def test_falha_jarvis_aciona_ollama_automaticamente(self):
        contexto = [{"role": "system", "content": "IDENTIDADE SERMAX"},
                    {"role": "user", "content": "Explique este assunto"}]
        patches = self._isolar_caminho_de_resposta(contexto)
        with patches[0], patches[1], patches[2], patches[3], patch.object(
            core.sermax_jarvis_adapter, "JarvisAdapter"
        ) as adapter, patch.object(
            core.urllib.request, "urlopen", return_value=FakeOllamaResponse()
        ):
            adapter.return_value.responder.side_effect = RuntimeError("worker indisponível")
            resposta = core._perguntar_impl("Explique este assunto")
        self.assertEqual(resposta, "Resposta via Ollama")
        self.assertEqual(core.ultimo_diagnostico_roteamento["backend"], "ollama")
        self.assertIn("worker indisponível", core.ultimo_diagnostico_roteamento["fallback"])

    def test_comandos_antigos_nao_selecionam_backend(self):
        resposta = core.responder_comando_local("/motor jarvis")
        self.assertIn("automaticamente", resposta)
        self.assertFalse(hasattr(core, "MOTOR_RESPOSTA"))


if __name__ == "__main__":
    unittest.main()
