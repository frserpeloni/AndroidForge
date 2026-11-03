import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sermax_cognitive import SermaxCognitiveEngine
from sermax_pestinha.pestinha.config import DEFAULT_PERMISSIONS
import sermax_core


class SermaxCognitiveEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = SermaxCognitiveEngine(Path(self.temp.name) / "neural")

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def test_system_sensors_are_off_by_default(self):
        self.assertFalse(DEFAULT_PERMISSIONS["sensor_atividade"])
        self.assertFalse(DEFAULT_PERMISSIONS["sensor_mouse_teclado"])
        self.assertFalse(DEFAULT_PERMISSIONS["sensor_tela_cheia"])
        self.assertFalse(DEFAULT_PERMISSIONS["pousar_janelas"])
        self.assertFalse(DEFAULT_PERMISSIONS["rotina"])

    def test_loads_full_pestinha_network(self):
        state = self.engine.snapshot()
        self.assertEqual(state["neurons"], 470)
        self.assertGreater(state["synapses"], 10000)
        self.assertIn("PEDIDO", self.engine.brain.sensory_names)
        self.assertIn("FUGIR", self.engine.brain.motor_names)

    def test_external_sensors_are_permission_gated(self):
        self.assertFalse(self.engine.submit_event("user_attention"))
        self.engine.set_sensor_permission("SOCIAL", True)
        self.assertTrue(self.engine.submit_event("user_attention"))
        self.assertFalse(self.engine.stimulate("BOREDOM", 1.0))

    def test_explicit_events_advance_neural_cycle(self):
        self.assertTrue(self.engine.submit_event("user_request"))
        state = self.engine.tick(100)
        self.assertIn(state["emotion"], {
            "observando", "feliz", "contente", "curioso", "bravo", "triste"
        })
        self.assertIn("STARTLE", state["motors"])
        self.assertIn("decision", state)

    def test_explicit_feedback_updates_neural_and_episodic_learning(self):
        self.engine.begin_decision("SERMAX|observando", "responder")
        self.assertTrue(self.engine.record_feedback("usuário aprovou", 0.8))
        self.assertEqual(
            self.engine.choose_action(
                "SERMAX|observando", ["responder", "planejar"], epsilon=0
            ),
            "responder",
        )

    def test_sermax_core_sensor_and_feedback_commands(self):
        with patch("sermax_core.obter_motor_cognitivo", return_value=self.engine):
            sensor_reply = sermax_core.responder_comando_local("/cog sensor SOCIAL on")
            self.assertIn("ativada", sensor_reply)
            self.assertTrue(self.engine.sensor_permissions["SOCIAL"])
            self.engine.begin_decision("SERMAX|observando", "responder")
            feedback_reply = sermax_core.responder_comando_local("/cog feedback positivo")
            self.assertIn("Feedback registrado", feedback_reply)

    def test_sermax_core_includes_neural_context_for_ollama(self):
        with patch("sermax_core.obter_motor_cognitivo", return_value=self.engine):
            context = sermax_core.montar_contexto("pergunta de teste")
        self.assertTrue(any("ESTADO COGNITIVO INTERNO" in item["content"] for item in context))

    def test_episode_learning_is_recorded(self):
        self.engine.record_decision(
            "WORK|observando", "consultar_memoria", "resultado útil", 0.8
        )
        self.assertEqual(
            self.engine.choose_action(
                "WORK|observando", ["consultar_memoria", "responder"], epsilon=0
            ),
            "consultar_memoria",
        )

    def test_neural_state_persists_separately(self):
        self.engine.set_sensor_permission("SOCIAL", True)
        self.engine.submit_event("task_started")
        self.engine.tick(100)
        self.engine.feedback(1.0, 2.0)
        self.engine.record_decision("WORK|observando", "planejar", "plano concluído", 0.6)
        self.engine.save()
        restored = SermaxCognitiveEngine(Path(self.temp.name) / "neural")
        try:
            self.assertTrue((Path(self.temp.name) / "neural" / "nervous.json").exists())
            self.assertTrue((Path(self.temp.name) / "neural" / "drives.json").exists())
            self.assertTrue((Path(self.temp.name) / "neural" / "episodes.jsonl").exists())
            self.assertTrue((Path(self.temp.name) / "neural" / "sensor_permissions.json").exists())
            self.assertTrue(restored.sensor_permissions["SOCIAL"])
            self.assertEqual(restored.brain.N, self.engine.brain.N)
        finally:
            restored.close()


if __name__ == "__main__":
    unittest.main()
