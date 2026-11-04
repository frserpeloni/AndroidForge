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


if __name__ == "__main__":
    unittest.main()
