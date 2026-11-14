import unittest

import sermax_executor
import sermax_tarefas


class FakeExecutor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def analisar_pedido(self, pedido):
        return sermax_executor.analisar_pedido(pedido)

    def executar(self, pedido, *, core, ferramenta):
        self.calls.append(pedido)
        return self.results.pop(0)


class FakeCore:
    def __init__(self, results):
        self.sermax_executor = FakeExecutor(results)


class ExecutorSecurityTests(unittest.TestCase):
    def test_accepts_only_allowlisted_actions(self):
        self.assertEqual(
            sermax_executor.analisar_pedido("sistema"),
            {"acao": "sistema", "argumento": ""},
        )
        self.assertEqual(
            sermax_executor.analisar_pedido("memoria Siena"),
            {"acao": "memoria", "argumento": "Siena"},
        )
        self.assertEqual(
            sermax_executor.analisar_pedido("calcular 12 x 3"),
            {"acao": "calcular", "argumento": "12 x 3"},
        )

    def test_rejects_shell_actions_and_metacharacters(self):
        for pedido in ("shell dir", "python script.py", "sistema & whoami",
                       "memoria Siena; apagar", "calcular 2 | more"):
            with self.subTest(pedido=pedido):
                with self.assertRaises(ValueError):
                    sermax_executor.analisar_pedido(pedido)

    def test_rejects_empty_oversized_and_control_character_input(self):
        for pedido in ("", "x" * (sermax_executor.MAX_ENTRADA + 1), "sistema\\nwhoami"):
            with self.subTest(pedido=pedido):
                with self.assertRaises(ValueError):
                    sermax_executor.analisar_pedido(pedido)

    def test_requires_arguments_for_memory_and_calculation(self):
        for pedido in ("memoria", "calcular"):
            with self.subTest(pedido=pedido):
                with self.assertRaises(ValueError):
                    sermax_executor.analisar_pedido(pedido)


class TaskExecutionTests(unittest.TestCase):
    def test_plan_limits_and_empty_items_are_enforced(self):
        with self.assertRaises(ValueError):
            sermax_tarefas.analisar_plano("sistema;")
        with self.assertRaises(ValueError):
            sermax_tarefas.analisar_plano(";".join(["sistema"] * 6))

    def test_successful_plan_executes_each_task_and_verifies_results(self):
        core = FakeCore([
            "Diagnóstico local do computador\\nWindows: 11\\nDisco C: OK",
            "Resultado: 36",
        ])
        result = sermax_tarefas.executar_plano(
            "sistema; calcular 6 x 6", core=core
        )
        self.assertIn("Plano concluído", result)
        self.assertEqual(core.sermax_executor.calls, ["sistema", "calcular 6 x 6"])

    def test_plan_stops_after_first_failed_verification(self):
        core = FakeCore(["Falha ao consultar sistema", "Resultado: 99"])
        result = sermax_tarefas.executar_plano(
            "sistema; calcular 9 x 11", core=core
        )
        self.assertIn("Execução interrompida", result)
        self.assertEqual(core.sermax_executor.calls, ["sistema"])

    def test_invalid_action_stops_before_execution(self):
        core = FakeCore(["Resultado: 1"])
        result = sermax_tarefas.executar_plano(
            "shell whoami; calcular 1 + 1", core=core
        )
        self.assertIn("INTERROMPIDO", result)
        self.assertEqual(core.sermax_executor.calls, [])


if __name__ == "__main__":
    unittest.main()
