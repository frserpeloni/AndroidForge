import json
import os
import sys
import tempfile
import threading
import urllib.error
import unittest
from unittest.mock import patch
from pathlib import Path

import sermax_platform_launcher as launcher

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
import instance_lock


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

    def test_wait_for_health_does_not_probe_when_launcher_worker_has_exited(self):
        stop = threading.Event()

        class Worker:
            def is_alive(self):
                return False

        with patch.object(launcher.urllib.request, "urlopen") as open_url:
            self.assertFalse(launcher.wait_for_health(
                "http://127.0.0.1:8765", stop, worker=Worker()
            ))
        open_url.assert_not_called()

    def test_wait_for_health_accepts_api_when_own_worker_is_alive(self):
        stop = threading.Event()

        class Worker:
            def is_alive(self):
                return True

        with patch.object(
            launcher.urllib.request,
            "urlopen",
            return_value=_Response({"service": "sermax-platform-api"}),
        ):
            self.assertTrue(launcher.wait_for_health(
                "http://127.0.0.1:8765", stop, worker=Worker()
            ))

    def test_wait_for_health_waits_until_own_uvicorn_server_started(self):
        stop = threading.Event()

        class Worker:
            def is_alive(self):
                return True

        class Server:
            started = False

        server = Server()
        with patch.object(launcher.time, "monotonic", side_effect=[0.0, 0.2, 1.0]), \
             patch.object(launcher.time, "sleep") as sleep, \
             patch.object(launcher.urllib.request, "urlopen") as open_url:
            self.assertFalse(launcher.wait_for_health(
                "http://127.0.0.1:8765", stop, timeout=0.5,
                worker=Worker(), server=server
            ))
        open_url.assert_not_called()
        sleep.assert_called()

    def test_wait_for_health_requires_own_uvicorn_server_started(self):
        stop = threading.Event()

        class Worker:
            def is_alive(self):
                return True

        class Server:
            started = True

        with patch.object(
            launcher.urllib.request,
            "urlopen",
            return_value=_Response({"service": "sermax-platform-api"}),
        ):
            self.assertTrue(launcher.wait_for_health(
                "http://127.0.0.1:8765", stop, timeout=0.2,
                worker=Worker(), server=Server()
            ))

    def test_wait_for_health_rejects_healthy_endpoint_from_another_process(self):
        stop = threading.Event()

        class Worker:
            alive = True
            def is_alive(self):
                return self.alive

        worker = Worker()

        def foreign_health_response(*args, **kwargs):
            worker.alive = False
            return _Response({"service": "sermax-platform-api"})

        with patch.object(launcher.urllib.request, "urlopen",
                          side_effect=foreign_health_response):
            self.assertFalse(launcher.wait_for_health(
                "http://127.0.0.1:8765", stop, timeout=0.2, worker=worker
            ))

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


class LauncherStatusTests(unittest.TestCase):
    def test_status_without_lock_is_stopped_and_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            status = launcher.inspect_instance_status(data_dir)
            self.assertEqual(status["state"], "stopped")
            self.assertFalse((data_dir / "platform-instance.lock").exists())

    def test_status_cli_loads_backend_lock_module_when_run_standalone(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            module = sys.modules.pop("instance_lock", None)
            backend_path = str(Path(__file__).resolve().parents[1] / "backend")
            had_backend_path = backend_path in sys.path
            if had_backend_path:
                sys.path.remove(backend_path)
            try:
                with (
                    patch.object(launcher, "platform_root", return_value=Path(__file__).resolve().parents[1]),
                    patch.dict(os.environ, {"SERMAX_PLATFORM_DATA": str(data_dir)}),
                    patch("builtins.print"),
                ):
                    self.assertEqual(launcher.main(["--status"]), 0)
                self.assertIn(backend_path, sys.path)
                self.assertFalse((data_dir / "platform-instance.lock").exists())
            finally:
                sys.modules.pop("instance_lock", None)
                if module is not None:
                    sys.modules["instance_lock"] = module
                if had_backend_path and backend_path not in sys.path:
                    sys.path.insert(0, backend_path)

    def test_status_with_free_lock_is_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            (data_dir / "platform-instance.lock").touch()
            status = launcher.inspect_instance_status(data_dir)
            self.assertEqual(status["state"], "stopped")

    def test_status_reports_running_only_when_lock_and_health_match(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            lock = instance_lock.acquire_instance_lock(data_dir)
            try:
                with patch.object(
                    launcher.urllib.request,
                    "urlopen",
                    return_value=_Response({
                        "service": "sermax-platform-api",
                        "version": "0.3.0",
                        "core": "loaded",
                    }),
                ):
                    status = launcher.inspect_instance_status(data_dir)
                self.assertEqual(status["state"], "running")
                self.assertEqual(status["version"], "0.3.0")
            finally:
                lock.close()

    def test_status_reports_unresponsive_without_killing_locked_process(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            lock = instance_lock.acquire_instance_lock(data_dir)
            try:
                with patch.object(
                    launcher.urllib.request,
                    "urlopen",
                    side_effect=urllib.error.URLError("offline"),
                ):
                    status = launcher.inspect_instance_status(data_dir)
                self.assertEqual(status["state"], "unresponsive")
                self.assertIn("Não encerre processos", status["detail"])
                with self.assertRaises(instance_lock.InstanceLockError):
                    instance_lock.acquire_instance_lock(data_dir)
            finally:
                lock.close()


class LauncherWorkerFailureTests(unittest.TestCase):
    def test_unrequested_server_exit_is_marked_as_failure(self):
        class Server:
            def run(self):
                return None

        stop = threading.Event()
        failed = threading.Event()
        launcher._serve_server(Server(), stop, failed)
        self.assertTrue(stop.is_set())
        self.assertTrue(failed.is_set())

    def test_requested_server_shutdown_is_not_marked_as_failure(self):
        class Server:
            def run(self):
                return None

        stop = threading.Event()
        failed = threading.Event()
        stop.set()
        launcher._serve_server(Server(), stop, failed)
        self.assertTrue(stop.is_set())
        self.assertFalse(failed.is_set())

    def test_server_exception_is_logged_and_marked_as_failure(self):
        class Server:
            def run(self):
                raise RuntimeError("simulated uvicorn crash")

        stop = threading.Event()
        failed = threading.Event()
        with patch.object(launcher.logging, "exception") as log_exception:
            launcher._serve_server(Server(), stop, failed)
        self.assertTrue(stop.is_set())
        self.assertTrue(failed.is_set())
        log_exception.assert_called_once()


class LauncherArgumentTests(unittest.TestCase):
    def test_no_browser_mode_is_available_for_background_hosting(self):
        args = launcher.parse_args(["--no-browser"])
        self.assertTrue(args.no_browser)
        self.assertEqual(args.health_timeout, 30.0)
        self.assertEqual(args.shutdown_timeout, 15.0)

    def test_timeouts_can_be_configured(self):
        args = launcher.parse_args([
            "--health-timeout", "45",
            "--shutdown-timeout", "20",
        ])
        self.assertEqual(args.health_timeout, 45.0)
        self.assertEqual(args.shutdown_timeout, 20.0)

    def test_non_positive_timeout_is_rejected(self):
        with self.assertRaises(SystemExit):
            launcher.parse_args(["--health-timeout", "0"])



class LauncherInstanceLockIntegrationTests(unittest.TestCase):
    def test_main_refuses_to_start_server_when_lock_is_already_held(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            held = instance_lock.acquire_instance_lock(data_dir)
            try:
                with (
                    patch.object(launcher, "platform_root", return_value=Path(__file__).resolve().parents[1]),
                    patch.dict(os.environ, {"SERMAX_PLATFORM_DATA": str(data_dir)}),
                    patch.object(launcher, "configure_logging"),
                    patch.object(launcher, "_run_server") as run_server,
                ):
                    self.assertEqual(launcher.main(["--no-browser"]), 4)
                run_server.assert_not_called()
            finally:
                held.close()

    def test_main_keeps_lock_for_the_entire_server_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)

            def fake_run_server(args, root, selected_data_dir):
                self.assertEqual(selected_data_dir, data_dir)
                with self.assertRaises(instance_lock.InstanceLockError):
                    instance_lock.acquire_instance_lock(data_dir)
                return 0

            with (
                patch.object(launcher, "platform_root", return_value=Path(__file__).resolve().parents[1]),
                patch.dict(os.environ, {"SERMAX_PLATFORM_DATA": str(data_dir)}),
                patch.object(launcher, "configure_logging"),
                patch.object(launcher, "_run_server", side_effect=fake_run_server),
            ):
                self.assertEqual(launcher.main(["--no-browser"]), 0)


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
