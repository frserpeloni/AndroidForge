import unittest
from sermax_widget_state import WidgetStateController


class FakeNeuralAdapter:
    def __init__(self, result="attention"):
        self.result = result
        self.events = []
        self.saved = False

    def processar_evento(self, event):
        self.events.append(event)
        return self.result

    def salvar(self):
        self.saved = True
        return True


class TestWidgetNeuralIntegration(unittest.TestCase):
    def test_routes_events_through_optional_neural_adapter(self):
        adapter = FakeNeuralAdapter("completed")
        controller = WidgetStateController(neural_adapter=adapter)
        state = controller.set_event("processing")
        self.assertEqual(state.name, "completed")
        self.assertEqual(adapter.events, ["processing"])
        self.assertTrue(controller.salvar_estado_neural())
        self.assertTrue(adapter.saved)

    def test_rejects_invalid_neural_state(self):
        adapter = FakeNeuralAdapter({"command": "run"})
        controller = WidgetStateController(neural_adapter=adapter)
        self.assertEqual(controller.set_event("processing").name, "error")

    def test_keeps_deterministic_fallback_without_adapter(self):
        controller = WidgetStateController()
        self.assertEqual(controller.set_event("processing").name, "processing")
        self.assertFalse(controller.salvar_estado_neural())


if __name__ == "__main__":
    unittest.main()
