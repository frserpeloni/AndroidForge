import json
import os
import tempfile
import unittest

import sermax_core as core


class TestMemoriaSERMAX(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path_original = core.ARQUIVO_MEMORIA
        self.historico_original = list(core.historico)
        core.ARQUIVO_MEMORIA = os.path.join(self.tmp.name, "memoria_sermax.json")
        core.historico[:] = []

    def tearDown(self):
        core.ARQUIVO_MEMORIA = self.path_original
        core.historico[:] = self.historico_original
        self.tmp.cleanup()

    def test_memoria_pessoal_valida(self):
        self.assertTrue(core.eh_memoria_candidata("Meu nome é Fabiano"))
        self.assertTrue(core.eh_memoria_candidata("Meu carro é um Fiat Siena 2008"))

    def test_nao_grava_pergunta_ou_comando(self):
        self.assertFalse(core.eh_memoria_candidata("Qual óleo uso?"))
        self.assertFalse(core.eh_memoria_candidata("/memoria"))
        self.assertFalse(core.eh_memoria_candidata("continua"))

    def test_persistencia_e_filtro_de_resposta_assistente(self):
        core.historico.extend([
            {"role": "user", "content": "Meu nome é Fabiano"},
            {"role": "assistant", "content": "Seu nome é Fabiano"},
            {"role": "user", "content": "Meu carro é um Fiat Siena 2008"},
        ])
        core.salvar_memoria()
        with open(core.ARQUIVO_MEMORIA, encoding="utf-8") as f:
            dados = json.load(f)
        self.assertEqual([x["content"] for x in dados], [
            "Meu nome é Fabiano", "Meu carro é um Fiat Siena 2008"
        ])
        self.assertTrue(os.path.isfile(core.ARQUIVO_MEMORIA))

    def test_memoria_recarrega_apos_reinicializacao(self):
        core.historico.append({"role": "user", "content": "Meu carro é um Fiat Siena 2008"})
        core.salvar_memoria()
        core.historico[:] = []
        recarregada = core.carregar_memoria()
        self.assertEqual(len(recarregada), 1)
        self.assertEqual(recarregada[0]["content"], "Meu carro é um Fiat Siena 2008")

    def test_falha_ao_substituir_preserva_memoria_anterior(self):
        conteudo_anterior = '[{"role": "user", "content": "Meu nome é Fabiano"}]'
        with open(core.ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
            f.write(conteudo_anterior)
        core.historico[:] = [
            {"role": "user", "content": "Meu carro é um Fiat Siena 2008"}
        ]

        from unittest.mock import patch
        with patch("sermax_core.os.replace", side_effect=OSError("falha simulada")):
            with self.assertRaises(OSError):
                core.salvar_memoria()

        with open(core.ARQUIVO_MEMORIA, encoding="utf-8") as f:
            self.assertEqual(f.read(), conteudo_anterior)
        temporarios = [
            nome for nome in os.listdir(self.tmp.name)
            if nome.startswith("memoria_sermax.json.tmp_")
        ]
        self.assertEqual(temporarios, [])

    def test_memoria_corrompida_preserva_backup(self):
        with open(core.ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
            f.write("{ JSON inválido")

        recarregada = core.carregar_memoria()

        self.assertEqual(recarregada, [])
        backups = [
            nome for nome in os.listdir(self.tmp.name)
            if nome.startswith("memoria_sermax.json.corrompido_") and nome.endswith(".bak")
        ]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.tmp.name, backups[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), "{ JSON inválido")

    def test_busca_memoria_por_termo(self):
        core.historico.extend([
            {"role": "user", "content": "Meu nome é Fabiano"},
            {"role": "user", "content": "Meu carro é um Fiat Siena 2008"},
        ])
        resultado = core.buscar_memorias("carro Siena")
        self.assertTrue(any("Siena" in item["content"] for item in resultado))

    def test_calculo_local(self):
        self.assertEqual(
            core.responder_calculo_local("quanto é 125 x 87"),
            "Resultado: 10.875"
        )

    def test_ollama_indisponivel_nao_crasha_import(self):
        self.assertTrue(callable(core.perguntar))


class TestFeedbackNeural(unittest.TestCase):
    def setUp(self):
        self.adapter_original = core._widget_adapter
        self.controller_original = core._widget_controller
        self.error_original = core._widget_init_error
        self.calls = []
        class FakeAdapter:
            available = True
            def registrar_feedback(inner, reward):
                self.calls.append(("feedback", reward))
                return True
            def salvar(inner):
                self.calls.append(("salvar",))
                return True
        class FakeController:
            def salvar_estado_neural(inner):
                return False
        core._widget_adapter = FakeAdapter()
        core._widget_controller = FakeController()
        core._widget_init_error = None

    def tearDown(self):
        core._widget_adapter = self.adapter_original
        core._widget_controller = self.controller_original
        core._widget_init_error = self.error_original

    def test_feedback_positivo_e_negativo_sao_persistidos(self):
        for reward in (1, -1):
            result = core.registrar_feedback_neural(reward)
            self.assertTrue(result["accepted"])
            self.assertTrue(result["persisted"])
            self.assertEqual(result["reward"], reward)
        self.assertEqual(self.calls, [
            ("feedback", 1), ("salvar",), ("feedback", -1), ("salvar",)
        ])

    def test_feedback_invalido_nao_chama_rede(self):
        for reward in (0, 2, True, False, "1", None, 1.0, -1.0):
            with self.subTest(reward=reward):
                result = core.registrar_feedback_neural(reward)
                self.assertFalse(result["accepted"])
                self.assertFalse(result["persisted"])
        self.assertEqual(self.calls, [])

    def test_rede_indisponivel_recusa_feedback(self):
        core._widget_adapter.available = False
        result = core.registrar_feedback_neural(1)
        self.assertFalse(result["accepted"])
        self.assertFalse(result["persisted"])
        self.assertEqual(self.calls, [])

    def test_falha_ao_salvar_nao_declara_persistencia(self):
        core._widget_adapter.salvar = lambda: False
        result = core.registrar_feedback_neural(1)
        self.assertTrue(result["accepted"])
        self.assertFalse(result["persisted"])
        self.assertIn("persistência falhou", result["reason"])

    def test_excecao_no_feedback_falha_fechada(self):
        core._widget_adapter.registrar_feedback = lambda reward: (_ for _ in ()).throw(RuntimeError("falha"))
        result = core.registrar_feedback_neural(-1)
        self.assertFalse(result["accepted"])
        self.assertFalse(result["persisted"])
        self.assertIn("Falha no feedback", result["reason"])


if __name__ == "__main__":
    unittest.main()
