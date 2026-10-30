import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "SERMAX_terminal"))
import sermax_launcher
import sermax_voz


class TestEmpacotamentoSERMAX(unittest.TestCase):
    def test_modulos_necessarios_existem(self):
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

    def test_spec_declara_interface_e_dependencias(self):
        spec = (ROOT / "SERMAX.spec").read_text(encoding="utf-8")
        for marcador in (
            "sermax_launcher.py",
            '"sermax_terminal.py"',
            '"sermax_voz.py"',
            '"sermax_integracao_comandos.py"',
            '"SERMAX_terminal"',
            '"sermax_core"',
            '"sermax_historico_comandos"',
            '"sermax_planejador"',
            '"sermax_executor"',
            '"sermax_tarefas"',
            '"ferramenta_windows"',
        ):
            self.assertIn(marcador, spec, f"SERMAX.spec não declara: {marcador}")

    def test_memoria_fica_na_pasta_da_instalacao(self):
        launcher = (ROOT / "sermax_launcher.py").read_text(encoding="utf-8")
        core = (ROOT / "sermax_core.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["SERMAX_ROOT"] = root', launcher)
        self.assertIn('os.environ.get("SERMAX_ROOT")', core)
        self.assertIn('ARQUIVO_MEMORIA = os.path.join(BASE_DIR, "memoria_sermax.json")', core)

    def test_diagnostico_usa_raiz_da_instalacao_em_executavel(self):
        integracao = (ROOT / "SERMAX_terminal" / "sermax_integracao_comandos.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("SERMAX_ROOT"', integracao)
        self.assertIn("from sermax_voz import localizar_whisper_e_modelo", integracao)
        self.assertIn("whisper, modelo_voz = localizar_whisper_e_modelo()", integracao)

    def test_launcher_separa_instalacao_do_bundle_temporario(self):
        root, bundle, terminal_dir, terminal_script = sermax_launcher.resolver_caminhos(
            True,
            r"C:\SERMAX\SERMAX.exe",
            r"C:\fontes\sermax_launcher.py",
            r"C:\Users\Teste\AppData\Local\Temp\_MEI12345",
        )
        self.assertEqual(root, str(Path(r"C:\SERMAX").resolve()))
        self.assertEqual(bundle, r"C:\Users\Teste\AppData\Local\Temp\_MEI12345")
        self.assertEqual(terminal_dir, bundle + r"\SERMAX_terminal")
        self.assertEqual(terminal_script, terminal_dir + r"\sermax_terminal.py")

    def test_launcher_em_codigo_fonte_usa_pasta_do_projeto(self):
        root, bundle, terminal_dir, terminal_script = sermax_launcher.resolver_caminhos(
            False,
            r"C:\Python\python.exe",
            r"C:\SERMAX\sermax_launcher.py",
        )
        self.assertEqual(root, str(Path(r"C:\SERMAX").resolve()))
        self.assertEqual(bundle, root)
        self.assertEqual(terminal_dir, str(Path(root) / "SERMAX_terminal"))
        self.assertEqual(terminal_script, str(Path(root) / "SERMAX_terminal" / "sermax_terminal.py"))

    def test_launcher_empacotado_define_raiz_e_abre_interface_do_bundle(self):
        raiz_instalacao = r"C:\SERMAX"
        script_interface = r"C:\Temp\_MEI12345\SERMAX_terminal\sermax_terminal.py"
        with patch.object(sermax_launcher.sys, "frozen", True, create=True), \
             patch.object(sermax_launcher.sys, "executable", r"C:\SERMAX\SERMAX.exe"), \
             patch.object(sermax_launcher.sys, "_MEIPASS", r"C:\Temp\_MEI12345", create=True), \
             patch.object(sermax_launcher, "resolver_caminhos",
                          return_value=(raiz_instalacao, r"C:\Temp\_MEI12345",
                                        os.path.dirname(script_interface), script_interface)), \
             patch.object(sermax_launcher.os.path, "isfile", return_value=True), \
             patch.object(sermax_launcher.os, "chdir") as mudar_diretorio, \
             patch.object(sermax_launcher.runpy, "run_path") as executar_interface:
            sermax_launcher.main()

        self.assertEqual(os.environ.get("SERMAX_ROOT"), raiz_instalacao)
        mudar_diretorio.assert_called_once_with(raiz_instalacao)
        executar_interface.assert_called_once_with(script_interface, run_name="__main__")

    def test_localizador_de_voz_prioriza_arquivos_da_instalacao(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            exe = raiz / "voz" / "whisper-cli.exe"
            modelo = raiz / "voz" / "modelos" / "ggml-tiny.bin"
            exe.parent.mkdir(parents=True)
            modelo.parent.mkdir(parents=True)
            exe.write_bytes(b"teste")
            modelo.write_bytes(b"teste")

            with patch.object(sermax_voz, "SERMAX_DIR", raiz), \
                 patch.object(sermax_voz, "USER_DOWNLOADS", raiz / "Downloads"):
                localizado_exe, localizado_modelo = sermax_voz.localizar_whisper_e_modelo()

            self.assertEqual(localizado_exe, str(exe))
            self.assertEqual(localizado_modelo, str(modelo))

    def test_memoria_pessoal_nao_esta_no_repositorio(self):
        self.assertFalse((ROOT / "memoria_sermax.json").exists(),
                         "Memória pessoal não deve ser versionada no pacote de fontes.")


if __name__ == "__main__":
    unittest.main()
