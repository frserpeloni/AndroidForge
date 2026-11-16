import unittest
from sermax_core import normalizar

class TestNormalizar(unittest.TestCase):
    def test_normalizar_basic(self):
        # String contendo espaços no início/fim, letras maiúsculas,
        # múltiplos espaços, tabulações e quebras de linha
        input_str = "  Hello   World\tThis\nIs   A Test  "
        result = normalizar(input_str)

        # 1. Espaços no início e fim removidos
        self.assertFalse(result.startswith(' '))
        self.assertFalse(result.endswith(' '))

        # 2. Todas as letras em minúsculas
        self.assertEqual(result, result.lower())

        # 3. Sequências de espaços, tabulações e quebras de linha reduzidas a um único espaço
        self.assertNotIn('  ', result)          # nenhum espaço duplo
        self.assertNotIn('\t', result)          # nenhuma tabulação
        self.assertNotIn('\n', result)          # nenhuma quebra de linha

        # 4. Resultado esperado
        expected = "hello world this is a test"
        self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
