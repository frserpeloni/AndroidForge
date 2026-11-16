import unittest
from unittest.mock import patch
import sermax_core

class TestSermaxCoreCommandRegression(unittest.TestCase):
    @patch('sermax_planejador.planejar')
    def test_plano_with_multiple_spaces(self, mock_planejar):
        # comando com espaços múltiplos após o prefixo
        mensagem = "/plano   fazer algo"
        sermax_core.responder_comando_local(mensagem)
        mock_planejar.assert_called_once_with(
            "fazer algo",
            modelo=sermax_core.MODELO,
            url=sermax_core.OLLAMA_URL
        )

    @patch('sermax_planejador.planejar')
    def test_planejar_with_tab(self, mock_planejar):
        # comando com tabulação após o prefixo
        mensagem = "/planejar\tfazer algo"
        sermax_core.responder_comando_local(mensagem)
        mock_planejar.assert_called_once_with(
            "fazer algo",
            modelo=sermax_core.MODELO,
            url=sermax_core.OLLAMA_URL
        )

if __name__ == "__main__":
    unittest.main()
