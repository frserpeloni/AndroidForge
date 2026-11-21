import os
import threading
import unittest

from backend import windows_stop


@unittest.skipUnless(os.name == "nt", "Teste de integração Win32 executado somente no Windows.")
class WindowsStopEventIntegrationTests(unittest.TestCase):
    def test_event_can_be_signaled_by_the_same_user_and_session(self):
        event = windows_stop.create_stop_event()
        received = []
        waiter = threading.Thread(target=lambda: received.append(event.wait(5000)), daemon=True)
        try:
            waiter.start()
            windows_stop.signal_stop_event()
            waiter.join(timeout=6)
            self.assertFalse(waiter.is_alive(), "A thread não recebeu o evento dentro do prazo.")
            self.assertEqual(received, [True])
        finally:
            event.close()

    def test_second_creator_does_not_assume_ownership_of_existing_event(self):
        event = windows_stop.create_stop_event()
        try:
            with self.assertRaises(windows_stop.StopEventAlreadyExists):
                windows_stop.create_stop_event()
        finally:
            event.close()

    def test_signal_without_running_instance_reports_not_found(self):
        with self.assertRaises(windows_stop.StopEventNotFound):
            windows_stop.signal_stop_event()


if __name__ == "__main__":
    unittest.main()