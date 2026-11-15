"""Launcher isolado da Plataforma SERMAX. Ainda em fase de desenvolvimento."""
from __future__ import annotations

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


def wait_for_health(url: str, stop: threading.Event, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    health_url = url.rstrip("/") + "/api/health"
    while time.monotonic() < deadline and not stop.is_set():
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    return False


def main() -> int:
    root = platform_root()
    backend = root / "backend"
    if not (backend / "server.py").is_file():
        # Source-tree entrypoint lives at SERMAX-Platform/ and backend is a child.
        backend = root / "backend"
    if not (backend / "server.py").is_file():
        raise FileNotFoundError(f"Backend da Plataforma não encontrado: {backend}")

    data_dir = Path(os.environ.get("SERMAX_PLATFORM_DATA", Path.home() / ".sermax-platform")).expanduser()
    configure_logging(data_dir)
    os.environ.setdefault("SERMAX_PLATFORM_DATA", str(data_dir))
    os.environ.setdefault("SERMAX_CORE_DIR", str(root.parent / "SERMAX-Windows"))

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

    if not wait_for_health(URL, stop):
        logging.error("API não ficou saudável dentro do prazo.")
        server.should_exit = True
        worker.join(timeout=10)
        return 2

    logging.info("API saudável. Abrindo interface.")
    webbrowser.open(URL)

    try:
        while worker.is_alive() and not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        request_shutdown()

    server.should_exit = True
    worker.join(timeout=15)
    if worker.is_alive():
        logging.error("Servidor não encerrou dentro do prazo.")
        return 3
    logging.info("Plataforma encerrada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
