import importlib
import os
import struct
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
import sermax_historico_comandos


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

    def test_historico_persistente_usa_raiz_da_instalacao(self):
        estado_anterior = os.environ.get("SERMAX_ROOT")
        with tempfile.TemporaryDirectory() as temporario:
            base = Path(temporario)
            instalacao = base / "instalacao"
            bundle = base / "_MEI12345"
            instalacao.mkdir()
            bundle.mkdir()
            try:
                with patch.dict(os.environ, {"SERMAX_ROOT": str(instalacao)}):
                    importlib.reload(sermax_historico_comandos)
                    self.assertEqual(sermax_historico_comandos.ROOT, instalacao.resolve())
                    self.assertTrue(sermax_historico_comandos.registrar("consulta persistente de teste"))
                    self.assertTrue((instalacao / "historico_comandos.json").is_file())
                    self.assertFalse((bundle / "historico_comandos.json").exists())
                    self.assertEqual(sermax_historico_comandos.obter(1), "consulta persistente de teste")
            finally:
                if estado_anterior is None:
                    os.environ.pop("SERMAX_ROOT", None)
                else:
                    os.environ["SERMAX_ROOT"] = estado_anterior
                importlib.reload(sermax_historico_comandos)

    def test_historico_ignora_comandos_de_controle_e_duplicata_imediata(self):
        estado_anterior = os.environ.get("SERMAX_ROOT")
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            try:
                with patch.dict(os.environ, {"SERMAX_ROOT": str(raiz)}):
                    importlib.reload(sermax_historico_comandos)
                    self.assertFalse(sermax_historico_comandos.registrar("/historico"))
                    self.assertFalse(sermax_historico_comandos.registrar("/repetir 1"))
                    self.assertTrue(sermax_historico_comandos.registrar("consulta de teste"))
                    self.assertFalse(sermax_historico_comandos.registrar("consulta de teste"))
                    dados = sermax_historico_comandos.carregar()["comandos"]
                    self.assertEqual(len(dados), 1)
                    self.assertEqual(dados[0]["comando"], "consulta de teste")
            finally:
                if estado_anterior is None:
                    os.environ.pop("SERMAX_ROOT", None)
                else:
                    os.environ["SERMAX_ROOT"] = estado_anterior
                importlib.reload(sermax_historico_comandos)

    def test_historico_invalido_nao_apaga_arquivo_original_ao_carregar(self):
        estado_anterior = os.environ.get("SERMAX_ROOT")
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            arquivo = raiz / "historico_comandos.json"
            arquivo.write_text("{json inválido", encoding="utf-8")
            original = arquivo.read_bytes()
            try:
                with patch.dict(os.environ, {"SERMAX_ROOT": str(raiz)}):
                    importlib.reload(sermax_historico_comandos)
                    self.assertEqual(sermax_historico_comandos.carregar(), {"comandos": []})
                    self.assertEqual(arquivo.read_bytes(), original)
            finally:
                if estado_anterior is None:
                    os.environ.pop("SERMAX_ROOT", None)
                else:
                    os.environ["SERMAX_ROOT"] = estado_anterior
                importlib.reload(sermax_historico_comandos)

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

    def test_localizador_de_voz_retorna_vazio_quando_recursos_nao_existirem(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "instalacao"
            downloads = Path(temporario) / "Downloads"
            raiz.mkdir()
            downloads.mkdir()
            with patch.object(sermax_voz, "SERMAX_DIR", raiz), \
                 patch.object(sermax_voz, "USER_DOWNLOADS", downloads):
                exe, modelo = sermax_voz.localizar_whisper_e_modelo()
            self.assertIsNone(exe)
            self.assertIsNone(modelo)

    def test_localizador_de_voz_busca_recursos_em_downloads(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "instalacao"
            downloads = Path(temporario) / "Downloads"
            raiz.mkdir()
            pasta_voz = downloads / "whisper-build"
            pasta_voz.mkdir(parents=True)
            exe = pasta_voz / "whisper-cli.exe"
            modelo = pasta_voz / "ggml-tiny.bin"
            exe.write_bytes(b"teste")
            modelo.write_bytes(b"teste")
            with patch.object(sermax_voz, "SERMAX_DIR", raiz), \
                 patch.object(sermax_voz, "USER_DOWNLOADS", downloads):
                localizado_exe, localizado_modelo = sermax_voz.localizar_whisper_e_modelo()
            self.assertEqual(localizado_exe, str(exe))
            self.assertEqual(localizado_modelo, str(modelo))


    def _wav_pcm_minimo(self, caminho):
        fmt = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
        dados = b"\x00\x00\x01\x00"
        chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
        chunks += b"data" + struct.pack("<I", len(dados)) + dados
        conteudo = b"WAVE" + chunks
        caminho.write_bytes(b"RIFF" + struct.pack("<I", len(conteudo)) + conteudo)

    def test_validacao_de_voz_rejeita_audio_que_nao_e_wav(self):
        with tempfile.TemporaryDirectory() as temporario:
            audio = Path(temporario) / "gravacao.wav"
            audio.write_bytes(b"arquivo M4A renomeado")
            with self.assertRaisesRegex(ValueError, "Arquivo inválido"):
                sermax_voz._validar_wav(audio)

    def test_validacao_de_voz_aceita_wav_pcm(self):
        with tempfile.TemporaryDirectory() as temporario:
            audio = Path(temporario) / "teste.wav"
            self._wav_pcm_minimo(audio)
            sermax_voz._validar_wav(audio)

    def test_voz_sem_recursos_nao_tenta_executar_whisper(self):
        with tempfile.TemporaryDirectory() as temporario:
            audio = Path(temporario) / "teste.wav"
            self._wav_pcm_minimo(audio)
            with patch.object(sermax_voz, "localizar_whisper_e_modelo", return_value=(None, None)) as localizar, patch.object(sermax_voz.subprocess, "run") as executar:
                with self.assertRaisesRegex(FileNotFoundError, "Whisper/modelo não localizados"):
                    sermax_voz.transcrever_arquivo(audio)
            executar.assert_not_called()

    def test_memoria_pessoal_nao_esta_no_repositorio(self):
        self.assertFalse((ROOT / "memoria_sermax.json").exists(),
                         "Memória pessoal não deve ser versionada no pacote de fontes.")


if __name__ == "__main__":
    unittest.main()
