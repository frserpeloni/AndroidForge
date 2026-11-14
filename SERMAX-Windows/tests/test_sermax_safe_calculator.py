import unittest

import sermax_core


class SafeCalculatorTests(unittest.TestCase):
    def test_supports_arithmetic_and_localized_multiplication(self):
        cases = {
            "2 + 3 * 4": "Resultado: 14",
            "125 x 87": "Resultado: 10.875",
            "10% de 250": "Resultado: 25",
            "(8 + 4) / 3": "Resultado: 4",
            "2 ** 10": "Resultado: 1.024",
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(
                    sermax_core.responder_calculo_local(expression), expected
                )

    def test_rejects_python_and_attribute_execution(self):
        expressions = [
            "__import__('os').system('whoami')",
            "open('memoria_sermax.json').read()",
            "().__class__.__mro__",
            "math.sqrt(9)",
            "[x for x in range(5)]",
        ]
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assertIsNone(
                    sermax_core.responder_calculo_local(expression)
                )

    def test_handles_division_by_zero_without_crashing(self):
        self.assertEqual(
            sermax_core.responder_calculo_local("10 / 0"),
            "Não consigo dividir por zero.",
        )

    def test_rejects_excessive_exponents_and_results(self):
        for expression in ("2 ** 11", "1000001 ** 2", "9999999999999999 * 100"):
            with self.subTest(expression=expression):
                self.assertIsNone(
                    sermax_core.responder_calculo_local(expression)
                )

    def test_rejects_empty_long_and_non_arithmetic_input(self):
        for expression in ("", "x" * 101, "12", "2 + os.system(1)"):
            with self.subTest(expression=expression):
                self.assertIsNone(
                    sermax_core.responder_calculo_local(expression)
                )


if __name__ == "__main__":
    unittest.main()
