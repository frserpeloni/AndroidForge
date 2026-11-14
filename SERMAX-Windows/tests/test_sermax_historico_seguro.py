import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sermax_historico_comandos


class TestHistoricoComandosSeguro(unittest.TestCase):
    def test_registrar_nao_substitui_json_corrompido(self):
        estado_anterior = os.environ.get("SERMAX_ROOT")
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            arquivo = raiz / "historico_comandos.json"
            arquivo.write_bytes(b"{json invalido original")
            original = arquivo.read_bytes()
            try:
                with patch.dict(os.environ, {"SERMAX_ROOT": str(raiz)}):
                    importlib.reload(sermax_historico_comandos)
                    self.assertFalse(
                        sermax_historico_comandos.registrar("nova consulta")
                    )
                    self.assertEqual(arquivo.read_bytes(), original)
            finally:
                if estado_anterior is None:
                    os.environ.pop("SERMAX_ROOT", None)
                else:
                    os.environ["SERMAX_ROOT"] = estado_anterior
                importlib.reload(sermax_historico_comandos)

    def test_registrar_nao_substitui_estrutura_json_invalida(self):
        estado_anterior = os.environ.get("SERMAX_ROOT")
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            arquivo = raiz / "historico_comandos.json"
            arquivo.write_text('{"outro_campo": []}', encoding="utf-8")
            original = arquivo.read_bytes()
            try:
                with patch.dict(os.environ, {"SERMAX_ROOT": str(raiz)}):
                    importlib.reload(sermax_historico_comandos)
                    self.assertFalse(
                        sermax_historico_comandos.registrar("nova consulta")
                    )
                    self.assertEqual(arquivo.read_bytes(), original)
            finally:
                if estado_anterior is None:
                    os.environ.pop("SERMAX_ROOT", None)
                else:
                    os.environ["SERMAX_ROOT"] = estado_anterior
                importlib.reload(sermax_historico_comandos)


if __name__ == "__main__":
    unittest.main()
