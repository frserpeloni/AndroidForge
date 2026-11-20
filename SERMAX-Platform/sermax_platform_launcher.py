"""Launcher isolado da Plataforma SERMAX. Ainda em fase de desenvolvimento."""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}/"


def platform_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_logging(data_dir: Path) -> None:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "platform-launcher.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def wait_for_health(
    url: str,
    stop: threading.Event,
    timeout: float = 30.0,
    worker: threading.Thread | None = None,
) -> bool:
    """Wait for health while confirming the API worker belongs to this launcher."""
    deadline = time.monotonic() + timeout
    health_url = url.rstrip("/") + "/api/health"
    while time.monotonic() < deadline and not stop.is_set():
        # A different SERMAX process may already own the port. Its health
        # endpoint must not make this launcher report a successful startup.
        if worker is not None and not worker.is_alive():
            return False
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if (
                    response.status == 200
                    and isinstance(payload, dict)
                    and payload.get("service") == "sermax-platform-api"
                    and (worker is None or worker.is_alive())
                ):
                    return True
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            time.sleep(0.25)
    return False


def shutdown_server(server, worker: threading.Thread, timeout: float = 15.0) -> bool:
    """Request Uvicorn shutdown and report whether its worker stopped in time."""
    server.should_exit = True
    worker.join(timeout=timeout)
    return not worker.is_alive()


def main() -> int:
    root = platform_root()
    backend_candidates = (root / "backend", root / "SERMAX-Platform" / "backend")
    backend = next((candidate for candidate in backend_candidates if (candidate / "server.py").is_file()), None)
    if backend is None:
        raise FileNotFoundError("Backend da Plataforma não encontrado nas pastas esperadas.")

    data_dir = Path(os.environ.get("SERMAX_PLATFORM_DATA", Path.home() / ".sermax-platform")).expanduser()
    configure_logging(data_dir)
    os.environ.setdefault("SERMAX_PLATFORM_DATA", str(data_dir))
    core_candidates = (root / "SERMAX-Windows", root.parent / "SERMAX-Windows")
    core_dir = next((candidate for candidate in core_candidates if (candidate / "sermax_core.py").is_file()), core_candidates[0])
    os.environ.setdefault("SERMAX_CORE_DIR", str(core_dir))

    sys.path.insert(0, str(backend))
    os.chdir(backend)

    import uvicorn

    config = uvicorn.Config(
        "server:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    stop = threading.Event()

    def request_shutdown(signum=None, frame=None):
        logging.info("Solicitação de encerramento recebida: %s", signum)
        stop.set()
        server.should_exit = True

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(signum, request_shutdown)
        except (ValueError, OSError):
            pass

    worker = threading.Thread(target=server.run, name="SERMAX-Platform-API", daemon=True)
    logging.info("Iniciando API local em %s", URL)
    worker.start()

    if not wait_for_health(URL, stop, worker=worker):
        logging.error("API não ficou saudável dentro do prazo.")
        if not shutdown_server(server, worker, timeout=10):
            logging.error("Servidor não encerrou após falha no health check.")
        return 2

    logging.info("API saudável. Abrindo interface.")
    webbrowser.open(URL)

    try:
        while worker.is_alive() and not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        request_shutdown()

    if not shutdown_server(server, worker, timeout=15):
        logging.error("Servidor não encerrou dentro do prazo.")
        return 3
    logging.info("Plataforma encerrada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
