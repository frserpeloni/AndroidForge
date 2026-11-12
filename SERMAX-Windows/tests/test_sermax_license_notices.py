import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
TERMINAL_DIR = ROOT / "SERMAX_terminal"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TERMINAL_DIR))

sermax_terminal = importlib.import_module("sermax_terminal")


class TestAvisosLicencaTerminal(unittest.TestCase):
    def _avisos(self, base):
        pasta = Path(base) / "THIRD_PARTY_NOTICES"
        pasta.mkdir(parents=True)
        (pasta / "Pestinha-GPL-3.0.txt").write_text("GPL", encoding="utf-8")
        (pasta / "Pestinha-ORIGIN.md").write_text("Origem", encoding="utf-8")
        return pasta

    def test_localiza_avisos_no_bundle_pyinstaller(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "_MEI123"
            pasta = self._avisos(bundle)
            with patch.object(sermax_terminal.sys, "_MEIPASS", str(bundle), create=True), \
                 patch.object(sermax_terminal.os, "name", "nt"), \
                 patch.object(sermax_terminal.os, "startfile", create=True) as abrir:
                resultado = sermax_terminal.abrir_avisos_licenca()
            self.assertIn("Avisos legais abertos", resultado)
            self.assertEqual(abrir.call_args_list, [call(str(pasta / "Pestinha-GPL-3.0.txt")),
                                                    call(str(pasta / "Pestinha-ORIGIN.md"))])

    def test_ausencia_de_arquivos_retorna_mensagem_sem_excecao(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(sermax_terminal.sys, "_MEIPASS", str(Path(temp) / "vazio"), create=True):
            resultado = sermax_terminal.abrir_avisos_licenca()
        self.assertIn("não encontrados", resultado)

    def test_sistema_nao_windows_nao_tenta_abrir_arquivos(self):
        with tempfile.TemporaryDirectory() as temp:
            self._avisos(temp)
            with patch.object(sermax_terminal.sys, "_MEIPASS", str(temp), create=True), \
                 patch.object(sermax_terminal.os, "name", "posix"), \
                 patch.object(sermax_terminal.os, "startfile", create=True) as abrir:
                resultado = sermax_terminal.abrir_avisos_licenca()
        self.assertIn("exige Windows", resultado)
        abrir.assert_not_called()

    def test_falha_oserror_e_reportada(self):
        with tempfile.TemporaryDirectory() as temp:
            self._avisos(temp)
            with patch.object(sermax_terminal.sys, "_MEIPASS", str(temp), create=True), \
                 patch.object(sermax_terminal.os, "name", "nt"), \
                 patch.object(sermax_terminal.os, "startfile", create=True,
                              side_effect=OSError("acesso negado")):
                resultado = sermax_terminal.abrir_avisos_licenca()
        self.assertIn("acesso negado", resultado)


if __name__ == "__main__":
    unittest.main()
