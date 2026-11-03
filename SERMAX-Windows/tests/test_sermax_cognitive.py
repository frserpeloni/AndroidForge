import tempfile
import unittest
from pathlib import Path

from sermax_cognitive import SermaxCognitiveEngine


class SermaxCognitiveEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = SermaxCognitiveEngine(Path(self.temp.name) / "neural")

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

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
