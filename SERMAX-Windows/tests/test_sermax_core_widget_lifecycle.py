import unittest
from unittest.mock import patch
import sermax_core


class FakeController:
    def __init__(self):
        self.events = []
        self.saved = 0
        self.state = type("State", (), {"name": "idle"})()

    def set_event(self, event):
        self.events.append(event)
        self.state = type("State", (), {"name": event})()
        return self.state

    def salvar_estado_neural(self):
        self.saved += 1
        return True


class TestCoreWidgetLifecycle(unittest.TestCase):
    def setUp(self):
        self.old = (
            sermax_core._widget_controller,
            sermax_core._widget_adapter,
            sermax_core._widget_init_error,
        )
        self.fake = FakeController()
        sermax_core._widget_controller = self.fake
        sermax_core._widget_adapter = type("Adapter", (), {"available": True})()
        sermax_core._widget_init_error = None

    def tearDown(self):
        (sermax_core._widget_controller,
         sermax_core._widget_adapter,
         sermax_core._widget_init_error) = self.old

    def test_request_lifecycle_and_neural_persistence(self):
        with patch.object(sermax_core, "_perguntar_impl", return_value="resposta"):
            self.assertEqual(sermax_core.perguntar("teste"), "resposta")
        self.assertEqual(self.fake.events, ["processing", "completed"])
        self.assertEqual(self.fake.saved, 1)

    def test_error_fallback_preserves_original_exception(self):
        with patch.object(sermax_core, "_perguntar_impl", side_effect=RuntimeError("falha original")):
            with self.assertRaisesRegex(RuntimeError, "falha original"):
                sermax_core.perguntar("teste")
        self.assertEqual(self.fake.events, ["processing", "error"])
        self.assertEqual(self.fake.saved, 1)


if __name__ == "__main__":
    unittest.main()
