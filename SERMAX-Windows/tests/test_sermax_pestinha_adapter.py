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


def test_pestinha_receives_only_allowlisted_lifecycle_events(tmp_path):
    brain = FakeBrain()
    path = tmp_path / "sermax_neural_state.json"
    adapter = PestinhaAdapter(str(path), brain_factory=lambda: brain)

    assert adapter.available
    assert adapter.processar_evento("processing") == "attention"
    assert brain.inputs == [{"WORK": 0.80, "TYPING": 0.20}]
    assert brain.steps == [80]
    assert adapter.processar_evento("error") == "error"
    assert adapter.processar_evento("unknown") == "error"


def test_pestinha_persistence_is_separate_and_explicit(tmp_path):
    brain = FakeBrain()
    path = tmp_path / "sermax_neural_state.json"
    adapter = PestinhaAdapter(str(path), brain_factory=lambda: brain)
    assert adapter.salvar()
    assert brain.saved == [str(path)]


def test_pestinha_failure_falls_back_without_crashing(tmp_path):
    class BrokenBrain(FakeBrain):
        def step(self, dt):
            raise RuntimeError("neural failure")

    adapter = PestinhaAdapter(
        str(tmp_path / "state.json"), brain_factory=BrokenBrain
    )
    assert adapter.processar_evento("processing") == "processing"
    assert not adapter.available
