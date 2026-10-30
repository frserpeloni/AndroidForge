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


if __name__ == "__main__":
    unittest.main()
