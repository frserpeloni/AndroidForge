import os
import socket
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import sermax_platform_launcher as launcher
import windows_stop


class WindowsStopSecurityPolicyTests(unittest.TestCase):
    def test_event_dacl_is_protected_and_grants_only_the_current_sid(self):
        sid = "S-1-5-21-100-200-300-1001"
        self.assertEqual(
            windows_stop._event_security_sddl(sid),
            f"D:P(A;;0x00100002;;;{sid})",
        )

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

    def test_real_launcher_stops_uvicorn_gracefully_after_event(self):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", 8765))
            except OSError:
                self.skipTest("A porta local 8765 já está ocupada neste runner.")

        root = Path(__file__).resolve().parents[1]
        previous_directory = os.getcwd()
        results = []
        args = SimpleNamespace(no_browser=True, health_timeout=20.0, shutdown_timeout=10.0)
        try:
            with tempfile.TemporaryDirectory() as directory:
                data_dir = Path(directory)
                with patch.dict(os.environ, {"SERMAX_PLATFORM_DATA": str(data_dir)}):
                    server_thread = threading.Thread(
                        target=lambda: results.append(launcher._run_server(args, root, data_dir)),
                        name="test-sermax-platform-server", daemon=True,
                    )
                    server_thread.start()
                    try:
                        self.assertTrue(
                            launcher.wait_for_health(launcher.URL, threading.Event(), timeout=20, worker=server_thread),
                            "A API não ficou saudável durante o teste de integração.",
                        )
                        windows_stop.signal_stop_event()
                        server_thread.join(timeout=15)
                        self.assertFalse(server_thread.is_alive(), "O launcher não encerrou o Uvicorn dentro do prazo.")
                        self.assertEqual(results, [0])
                    finally:
                        if server_thread.is_alive():
                            try:
                                windows_stop.signal_stop_event()
                            except windows_stop.StopEventError:
                                pass
                            server_thread.join(timeout=10)
        finally:
            os.chdir(previous_directory)
    def test_run_local_batch_signals_event_without_starting_server(self):
        event = windows_stop.create_stop_event()
        batch = Path(__file__).resolve().parents[1] / "backend" / "run_local.bat"
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", str(batch), "--stop"],
                cwd=batch.parent, capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(event.wait(1000), "O batch não sinalizou o evento de parada.")
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