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


def test_widget_controller_routes_events_through_optional_neural_adapter():
    adapter = FakeNeuralAdapter("completed")
    controller = WidgetStateController(neural_adapter=adapter)
    state = controller.set_event("processing")
    assert state.name == "completed"
    assert adapter.events == ["processing"]
    assert controller.salvar_estado_neural()
    assert adapter.saved


def test_widget_controller_rejects_invalid_neural_state():
    adapter = FakeNeuralAdapter({"command": "run"})
    controller = WidgetStateController(neural_adapter=adapter)
    assert controller.set_event("processing").name == "error"


def test_widget_controller_keeps_deterministic_fallback_without_adapter():
    controller = WidgetStateController()
    assert controller.set_event("processing").name == "processing"
    assert controller.salvar_estado_neural() is False
