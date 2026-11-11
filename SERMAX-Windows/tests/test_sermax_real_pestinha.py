import tempfile
import unittest
from pathlib import Path

try:
    from pestinha.core.nervous_system import LIFBrain
except ImportError:
    LIFBrain = None
from sermax_pestinha_adapter import PestinhaAdapter
from sermax_widget_state import ESTADOS_VISUAIS


class TestRealPestinhaRuntime(unittest.TestCase):
    @unittest.skipIf(LIFBrain is None, "Pestinha não instalado neste ambiente.")
    def test_lifbrain_runs_and_persists_its_own_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memoria_neural_pestinha.json"
            adapter = PestinhaAdapter(str(path), brain_factory=LIFBrain)
            self.assertTrue(adapter.available)
            self.assertIn(adapter.processar_evento("processing"), ESTADOS_VISUAIS)
            self.assertTrue(adapter.salvar())
            self.assertTrue(path.is_file())
            restored = PestinhaAdapter(str(path), brain_factory=LIFBrain)
            self.assertTrue(restored.available)

    @unittest.skipIf(LIFBrain is None, "Pestinha não instalado neste ambiente.")
    def test_explicit_learning_and_habituation_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memoria_neural_pestinha.json"
            first = PestinhaAdapter(str(path), brain_factory=LIFBrain)
            self.assertTrue(first.available)

            for _ in range(12):
                result = first.registrar_contexto({"WORK": 1.0, "TYPING": 0.5}, dt_ms=400)
                self.assertTrue(result["available"])
            self.assertTrue(first.registrar_feedback(1))
            learned_before = first._brain.learned_summary(top=20)
            efficacy_before = first._brain.efficacy()["WORK"]
            self.assertTrue(learned_before)
            self.assertLess(efficacy_before, 1.0)
            self.assertTrue(first.salvar())

            restored = PestinhaAdapter(str(path), brain_factory=LIFBrain)
            self.assertTrue(restored.available)
            learned_after = restored._brain.learned_summary(top=20)
            efficacy_after = restored._brain.efficacy()["WORK"]
            # O formato JSON persiste pesos com seis casas decimais.
            self.assertEqual(learned_after, [
                (canal, alvo, round(peso, 6))
                for canal, alvo, peso in learned_before
            ])
            self.assertLess(efficacy_after, 1.0)

    @unittest.skipIf(LIFBrain is None, "Pestinha não instalado neste ambiente.")
    def test_corrupted_neural_state_fails_closed_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memoria_neural_pestinha.json"
            original = "{arquivo neural corrompido"
            path.write_text(original, encoding="utf-8")

            adapter = PestinhaAdapter(str(path), brain_factory=LIFBrain)
            self.assertFalse(adapter.available)
            # read_json preserva o arquivo inválido em quarentena .corrompido.
            quarantined = path.with_name(path.name + ".corrompido")
            self.assertTrue(quarantined.is_file())
            self.assertEqual(quarantined.read_text(encoding="utf-8"), original)
            self.assertFalse(path.exists())


class TestFeedbackPeloNucleoSERMAX(unittest.TestCase):
    @unittest.skipIf(LIFBrain is None, "Pestinha não instalado neste ambiente.")
    def test_feedback_do_core_persiste_e_restaura_rede_real(self):
        import sermax_core as core
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memoria_neural_pestinha.json"
            controller_original = core._widget_controller
            adapter_original = core._widget_adapter
            error_original = core._widget_init_error
            base_original = core.BASE_DIR
            try:
                core.BASE_DIR = folder
                core._widget_controller = None
                core._widget_adapter = None
                core._widget_init_error = None

                contexto = core.registrar_contexto_neural(
                    "Estou trabalhando em uma tarefa de execução e análise"
                )
                self.assertTrue(contexto["available"])
                resultado = core.registrar_feedback_neural(1)
                self.assertTrue(resultado["accepted"])
                self.assertTrue(resultado["persisted"])
                self.assertTrue(path.is_file())

                pesos_antes = core._widget_adapter._brain.learned.copy()
                # Um único contexto de 80 ms gera atualização pequena, abaixo
                # do limiar de exibição de learned_summary (1e-4). Validamos
                # os pesos internos, sem confundir ausência no resumo com
                # ausência de plasticidade.
                self.assertTrue(any(float(valor) != 0.0 for linha in pesos_antes for valor in linha))

                core._widget_controller = None
                core._widget_adapter = None
                core._widget_init_error = None
                diagnostico = core.diagnostico_widget()
                self.assertTrue(diagnostico["neural_ativa"])
                pesos_depois = core._widget_adapter._brain.learned.copy()
                self.assertEqual(pesos_depois.tolist(), [
                    [round(float(valor), 6) for valor in linha]
                    for linha in pesos_antes
                ])
            finally:
                core.BASE_DIR = base_original
                core._widget_controller = controller_original
                core._widget_adapter = adapter_original
                core._widget_init_error = error_original


if __name__ == "__main__":
    unittest.main()
