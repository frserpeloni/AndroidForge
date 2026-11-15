import json
import threading
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
             patch.object(launcher.time, "monotonic", side_effect=[0.0, 1.0]), \
             patch.object(launcher.time, "sleep"):
            self.assertFalse(launcher.wait_for_health("http://127.0.0.1:8765", stop, timeout=0.5))

    def test_wait_for_health_stops_when_requested(self):
        stop = threading.Event()
        stop.set()
        with patch.object(launcher.urllib.request, "urlopen") as open_url:
            self.assertFalse(launcher.wait_for_health("http://127.0.0.1:8765", stop))
        open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
