import json
import threading
import urllib.error
import unittest
from unittest.mock import patch

import sermax_platform_launcher as launcher


class _Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class LauncherHealthTests(unittest.TestCase):
    def test_wait_for_health_accepts_only_sermax_platform_api(self):
        stop = threading.Event()
        with patch.object(launcher.urllib.request, "urlopen",
                          return_value=_Response({"service": "sermax-platform-api"})) as open_url:
            self.assertTrue(launcher.wait_for_health("http://127.0.0.1:8765/", stop, timeout=0.2))
        open_url.assert_called_once_with(
            "http://127.0.0.1:8765/api/health", timeout=1.5
        )

    def test_wait_for_health_rejects_another_service(self):
        stop = threading.Event()
        with patch.object(launcher.urllib.request, "urlopen",
                          return_value=_Response({"service": "different-service"})), \
             patch.object(launcher.time, "monotonic", side_effect=[0.0, 0.1, 1.0]), \
             patch.object(launcher.time, "sleep"):
            self.assertFalse(launcher.wait_for_health("http://127.0.0.1:8765", stop, timeout=0.5))

    def test_wait_for_health_retries_after_malformed_json(self):
        stop = threading.Event()
        responses = [
            _Response(None),
            _Response({"service": "sermax-platform-api"}),
        ]
        with patch.object(launcher.urllib.request, "urlopen",
                          side_effect=responses), patch.object(launcher.time, "sleep"):
            self.assertTrue(launcher.wait_for_health("http://127.0.0.1:8765", stop, timeout=1.0))

    def test_wait_for_health_times_out_after_unavailable_service(self):
        stop = threading.Event()
        with patch.object(launcher.time, "monotonic", side_effect=[0.0, 0.6]), \
             patch.object(launcher.urllib.request, "urlopen",
                          side_effect=urllib.error.URLError("offline")), \
             patch.object(launcher.time, "sleep"):
            self.assertFalse(launcher.wait_for_health("http://127.0.0.1:8765", stop, timeout=0.5))

    def test_wait_for_health_stops_when_requested(self):
        stop = threading.Event()
        stop.set()
        with patch.object(launcher.urllib.request, "urlopen") as open_url:
            self.assertFalse(launcher.wait_for_health("http://127.0.0.1:8765", stop))
        open_url.assert_not_called()


class LauncherShutdownTests(unittest.TestCase):
    def test_shutdown_requests_exit_and_joins_worker(self):
        class Server:
            should_exit = False

        class Worker:
            joined = None
            def join(self, timeout):
                self.joined = timeout
            def is_alive(self):
                return False

        server = Server()
        worker = Worker()
        self.assertTrue(launcher.shutdown_server(server, worker, timeout=7))
        self.assertTrue(server.should_exit)
        self.assertEqual(worker.joined, 7)

    def test_shutdown_reports_worker_that_did_not_stop(self):
        class Server:
            should_exit = False

        class Worker:
            def join(self, timeout):
                pass
            def is_alive(self):
                return True

        server = Server()
        self.assertFalse(launcher.shutdown_server(server, Worker(), timeout=0))
        self.assertTrue(server.should_exit)


if __name__ == "__main__":
    unittest.main()
