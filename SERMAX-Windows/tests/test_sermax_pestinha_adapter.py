import tempfile
import unittest
from pathlib import Path

from sermax_pestinha_adapter import PestinhaAdapter


class FakeBrain:
    def __init__(self):
        self.inputs = []
        self.steps = []
        self.loaded = []
        self.saved = []
        self.sensory_names = ["SOCIAL", "TYPING", "WORK"]
        self.learn_calls = []

    def load(self, path):
        self.loaded.append(path)
        return False

    def stimulate(self, values):
        self.inputs.append(values)

    def step(self, dt):
        self.steps.append(dt)

    def motor_activity(self):
        return {"WATCH": 4.0, "CHEER": 1.0, "FUGIR": 99.0}

    def learn(self, reward, dt_s, rate):
        self.learn_calls.append((reward, dt_s, rate))

    def pool_rates(self):
        return {"FOCUS": 2.5}

    def efficacy(self):
        return {"WORK": 0.9}

    def learned_summary(self, top=5):
        return [("WORK", "CALM", 0.01)]

    def save(self, path):
        self.saved.append(path)
        with open(path, "w", encoding="utf-8") as state_file:
            state_file.write("{}")


class TestPestinhaAdapter(unittest.TestCase):
    def test_receives_only_allowlisted_lifecycle_events(self):
        with tempfile.TemporaryDirectory() as folder:
            brain = FakeBrain()
            path = str(Path(folder) / "sermax_neural_state.json")
            adapter = PestinhaAdapter(path, brain_factory=lambda: brain)

            self.assertTrue(adapter.available)
            self.assertEqual(adapter.processar_evento("processing"), "attention")
            self.assertEqual(brain.inputs, [{"WORK": 0.80, "TYPING": 0.20}])
            self.assertEqual(brain.steps, [80])
            self.assertEqual(adapter.processar_evento("error"), "error")
            self.assertEqual(adapter.processar_evento("unknown"), "error")

    def test_persistence_is_separate_and_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            brain = FakeBrain()
            path = str(Path(folder) / "sermax_neural_state.json")
            adapter = PestinhaAdapter(path, brain_factory=lambda: brain)
            self.assertTrue(adapter.salvar())
            self.assertEqual(brain.saved, [path])

    def test_context_updates_metrics_and_eligibility_without_reward(self):
        with tempfile.TemporaryDirectory() as folder:
            brain = FakeBrain()
            adapter = PestinhaAdapter(str(Path(folder) / "state.json"), brain_factory=lambda: brain)
            result = adapter.registrar_contexto({"SOCIAL": 0.35, "WORK": 0.65})
            self.assertTrue(result["available"])
            self.assertEqual(brain.inputs[-1], {"SOCIAL": 0.35, "WORK": 0.65})
            self.assertEqual(brain.learn_calls[-1][0], 0.0)
            self.assertIn("pools", result["metrics"])
            self.assertIn("efficacy", result["metrics"])
            self.assertIn("learned", result["metrics"])

    def test_context_rejects_unknown_channels_and_invalid_intensity(self):
        with tempfile.TemporaryDirectory() as folder:
            brain = FakeBrain()
            adapter = PestinhaAdapter(str(Path(folder) / "state.json"), brain_factory=lambda: brain)
            self.assertFalse(adapter.registrar_contexto({"NOT_A_SENSOR": 0.5})["available"])
            self.assertFalse(adapter.registrar_contexto({"WORK": 1.5})["available"])
            self.assertEqual(brain.inputs, [])

    def test_learning_requires_explicit_binary_feedback(self):
        with tempfile.TemporaryDirectory() as folder:
            brain = FakeBrain()
            adapter = PestinhaAdapter(str(Path(folder) / "state.json"), brain_factory=lambda: brain)
            self.assertFalse(adapter.registrar_feedback(0.5))
            self.assertFalse(adapter.registrar_feedback(True))
            self.assertTrue(adapter.registrar_feedback(1))
            self.assertEqual(brain.learn_calls[-1][0], 1.0)

    def test_failure_falls_back_without_crashing(self):
        class BrokenBrain(FakeBrain):
            def step(self, dt):
                raise RuntimeError("neural failure")

        with tempfile.TemporaryDirectory() as folder:
            adapter = PestinhaAdapter(
                str(Path(folder) / "state.json"), brain_factory=BrokenBrain
            )
            self.assertEqual(adapter.processar_evento("processing"), "processing")
            self.assertFalse(adapter.available)


if __name__ == "__main__":
    unittest.main()
