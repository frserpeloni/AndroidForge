import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestEmpacotamentoSERMAX(unittest.TestCase):
    def test_modulos_importados_pelo_nucleo_existem(self):
        obrigatorios = (
            "sermax_core.py",
            "ferramenta_windows.py",
            "sermax_planejador.py",
            "sermax_executor.py",
            "sermax_tarefas.py",
            "sermax_historico_comandos.py",
            "sermax_launcher.py",
            "SERMAX.spec",
            "SERMAX_terminal/sermax_terminal.py",
            "SERMAX_terminal/sermax_voz.py",
            "SERMAX_terminal/sermax_integracao_comandos.py",
        )
        ausentes = [item for item in obrigatorios if not (ROOT / item).is_file()]
        self.assertEqual(ausentes, [], f"Arquivos necessários ausentes: {ausentes}")

    def test_spec_empacota_interface_e_dependencias(self):
        spec = (ROOT / "SERMAX.spec").read_text(encoding="utf-8")
        for marcador in (
            "sermax_launcher.py",
            '"SERMAX_terminal/sermax_terminal.py"',
            '"SERMAX_terminal/sermax_voz.py"',
            '"SERMAX_terminal/sermax_integracao_comandos.py"',
            '"sermax_core"',
            '"sermax_historico_comandos"',
            '"sermax_planejador"',
            '"sermax_executor"',
            '"sermax_tarefas"',
            '"ferramenta_windows"',
        ):
            self.assertIn(marcador, spec, f"SERMAX.spec não declara: {marcador}")

    def test_launcher_aponta_memoria_para_pasta_do_executavel(self):
        launcher = (ROOT / "sermax_launcher.py").read_text(encoding="utf-8")
        core = (ROOT / "sermax_core.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["SERMAX_ROOT"] = root', launcher)
        self.assertIn('os.environ.get("SERMAX_ROOT")', core)
        self.assertIn('ARQUIVO_MEMORIA = os.path.join(BASE_DIR, "memoria_sermax.json")', core)

    def test_nao_inclui_memoria_pessoal_no_pacote_versionado(self):
        self.assertFalse((ROOT / "memoria_sermax.json").exists(),
                         "Memória pessoal não deve ser versionada no pacote de fontes.")


if __name__ == "__main__":
    unittest.main()
