import unittest
from unittest.mock import patch

import sermax_core as core


class TestJarvisCoreIntegration(unittest.TestCase):
    def setUp(self):
        self.motor_original = core.MOTOR_RESPOSTA
        self.sessao_original = list(core.sessao)
        core.sessao.clear()

    def tearDown(self):
        core.MOTOR_RESPOSTA = self.motor_original
        core.sessao[:] = self.sessao_original

    def test_motor_jarvis_recebe_identidade_memoria_e_pergunta(self):
        contexto = [
            {"role": "system", "content": "IDENTIDADE SERMAX"},
            {"role": "system", "content": "MEMORIA: carro Siena"},
            {"role": "user", "content": "Qual óleo devo usar?"},
        ]
        with patch.object(core, "responder_comando_local", return_value=None), \\
             patch.object(core, "responder_calculo_local", return_value=None), \\
             patch.object(core, "registrar_memoria"), \\
             patch.object(core, "montar_contexto", return_value=contexto), \\
             patch.object(core.sermax_jarvis_adapter, "JarvisAdapter") as adapter:
            adapter.return_value.responder.return_value = "Resposta do Jarvis"
            core.MOTOR_RESPOSTA = "jarvis"
            partes = []
            resposta = core._perguntar_impl("Qual óleo devo usar?", receber_parte=partes.append)

        prompt = adapter.return_value.responder.call_args.args[0]
        self.assertIn("IDENTIDADE SERMAX", prompt)
        self.assertIn("MEMORIA: carro Siena", prompt)
        self.assertIn("Qual óleo devo usar?", prompt)
        self.assertEqual(resposta, "Resposta do Jarvis")
        self.assertEqual(partes, ["Resposta do Jarvis"])

    def test_motor_ollama_permanece_padrao_e_selecionavel(self):
        core.MOTOR_RESPOSTA = "ollama"
        resposta = core.responder_comando_local("/motor jarvis")
        self.assertEqual(core.MOTOR_RESPOSTA, "jarvis")
        self.assertIn("JARVIS", resposta)
        self.assertEqual(core.responder_comando_local("/motor status").startswith("Motor de resposta atual: JARVIS"), True)
        resposta = core.responder_comando_local("/motor ollama")
        self.assertEqual(core.MOTOR_RESPOSTA, "ollama")
        self.assertIn("OLLAMA", resposta)


if __name__ == "__main__":
    unittest.main()
