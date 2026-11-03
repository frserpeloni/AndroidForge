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

    def load(self, path):
        self.loaded.append(path)
        return False

    def stimulate(self, values):
        self.inputs.append(values)

    def step(self, dt):
        self.steps.append(dt)

    def motor_activity(self):
        return {"WATCH": 4.0, "CHEER": 1.0, "FUGIR": 99.0}

    def save(self, path):
        self.saved.append(path)


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
