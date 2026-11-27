import unittest

from sermax_widget_state import ESTADOS_VISUAIS, WidgetStateController


class WidgetStateControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = WidgetStateController()

    def test_initial_state_is_idle(self):
        self.assertEqual(self.controller.state.name, "idle")

    def test_known_events_map_to_closed_visual_states(self):
        for event in ("idle", "attention", "processing", "completed", "error"):
            with self.subTest(event=event):
                state = self.controller.set_event(event)
                self.assertEqual(state.name, event)
                self.assertIn(state.name, ESTADOS_VISUAIS)

    def test_unknown_or_non_string_event_fails_closed(self):
        self.assertEqual(self.controller.set_event("run_shell").name, "error")
        self.assertEqual(self.controller.set_event(None).name, "error")

    def test_neural_output_is_restricted_to_visual_state_allowlist(self):
        self.assertEqual(self.controller.accept_neural_output(" attention ").name, "attention")
        self.assertEqual(self.controller.accept_neural_output("run_command").name, "error")
        self.assertEqual(self.controller.accept_neural_output({"action": "shutdown"}).name, "error")

    def test_controller_does_not_change_state_outside_explicit_calls(self):
        self.controller.set_event("processing")
        self.assertEqual(self.controller.state.name, "processing")


if __name__ == "__main__":
    unittest.main()
