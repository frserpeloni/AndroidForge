"""Launcher isolado da Plataforma SERMAX. Ainda em fase de desenvolvimento."""
from __future__ import annotations

import argparse
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
    server=None,
) -> bool:
    """Wait for health and verify this launcher's own Uvicorn server started."""
    deadline = time.monotonic() + timeout
    health_url = url.rstrip("/") + "/api/health"
    while time.monotonic() < deadline and not stop.is_set():
        # A different SERMAX process may already own the port. Its health
        # endpoint must not make this launcher report a successful startup.
        if worker is not None and not worker.is_alive():
            return False
        if server is not None and not server.started:
            time.sleep(0.1)
            continue
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if (
                    response.status == 200
                    and isinstance(payload, dict)
                    and payload.get("service") == "sermax-platform-api"
                    and (worker is None or worker.is_alive())
                    and (server is None or server.started)
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


def _serve_server(server, stop: threading.Event, failed: threading.Event) -> None:
    """Run Uvicorn and distinguish an expected shutdown from an unexpected exit."""
    try:
        server.run()
    except BaseException:
        failed.set()
        logging.exception("Falha não tratada no servidor da Plataforma.")
    else:
        if not stop.is_set():
            failed.set()
            logging.error("Servidor Uvicorn encerrou sem solicitação de parada.")
    finally:
        stop.set()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Inicializador local da Plataforma SERMAX.")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Mantém a API local em execução sem abrir uma janela do navegador.",
    )
    parser.add_argument(
        "--install-autostart", action="store_const", const="install", dest="autostart_action",
        help="Registra inicialização no logon do usuário atual do Windows.",
    )
    parser.add_argument(
        "--remove-autostart", action="store_const", const="remove", dest="autostart_action",
        help="Remove a tarefa de inicialização automática do SERMAX.",
    )
    parser.add_argument(
        "--autostart-status", action="store_const", const="status", dest="autostart_action",
        help="Consulta se a tarefa de inicialização automática está registrada.",
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=30.0,
        help="Tempo máximo em segundos para aguardar a inicialização da API.",
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=float,
        default=15.0,
        help="Tempo máximo em segundos para aguardar o encerramento do servidor.",
    )
    raw_args = list(sys.argv[1:] if argv is None else argv)
    autostart_flags = {"--install-autostart", "--remove-autostart", "--autostart-status"}
    if sum(flag in raw_args for flag in autostart_flags) > 1:
        parser.error("Escolha somente uma operação de inicialização automática.")
    args = parser.parse_args(raw_args)
    if args.health_timeout <= 0 or args.shutdown_timeout <= 0:
        parser.error("Os tempos de health check e encerramento devem ser positivos.")
    return args


def _run_server(args, root: Path, data_dir: Path) -> int:
    backend_candidates = (root / "backend", root / "SERMAX-Platform" / "backend")
    backend = next((candidate for candidate in backend_candidates if (candidate / "server.py").is_file()), None)
    if backend is None:
        raise FileNotFoundError("Backend da Plataforma não encontrado nas pastas esperadas.")

    configure_logging(data_dir)
    os.environ.setdefault("SERMAX_PLATFORM_DATA", str(data_dir))
    core_candidates = (root / "SERMAX-Windows", root.parent / "SERMAX-Windows")
    core_dir = next((candidate for candidate in core_candidates if (candidate / "sermax_core.py").is_file()), core_candidates[0])
    os.environ.setdefault("SERMAX_CORE_DIR", str(core_dir))

    sys.path.insert(0, str(backend))
    os.chdir(backend)

    import uvicorn

    config = uvicorn.Config("server:app", host=HOST, port=PORT, reload=False,
                            log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    stop = threading.Event()
    worker_failed = threading.Event()

    def request_shutdown(signum=None, frame=None):
        logging.info("Solicitação de encerramento recebida: %s", signum)
        stop.set()
        server.should_exit = True

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(signum, request_shutdown)
        except (ValueError, OSError):
            pass

    worker = threading.Thread(
        target=_serve_server,
        args=(server, stop, worker_failed),
        name="SERMAX-Platform-API",
        daemon=True,
    )
    logging.info("Iniciando API local em %s", URL)
    worker.start()

    if not wait_for_health(URL, stop, timeout=args.health_timeout, worker=worker, server=server):
        logging.error("API não ficou saudável dentro do prazo.")
        if not shutdown_server(server, worker, timeout=10):
            logging.error("Servidor não encerrou após falha no health check.")
        return 2

    if args.no_browser:
        logging.info("API saudável. Modo sem navegador ativo.")
    else:
        logging.info("API saudável. Abrindo interface.")
        webbrowser.open(URL)

    try:
        while worker.is_alive() and not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        request_shutdown()

    if not shutdown_server(server, worker, timeout=args.shutdown_timeout):
        logging.error("Servidor não encerrou dentro do prazo.")
        return 3
    if worker_failed.is_set():
        logging.error("Plataforma encerrou por falha do servidor; o Agendador poderá aplicar a política de reinício.")
        return 3
    logging.info("Plataforma encerrada.")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    root = platform_root()
    if args.autostart_action:
        backend = root / "backend"
        if not (backend / "windows_autostart.py").is_file():
            backend = root / "SERMAX-Platform" / "backend"
        if not (backend / "windows_autostart.py").is_file():
            print("Módulo de inicialização automática não encontrado.", file=sys.stderr)
            return 5
        sys.path.insert(0, str(backend))
        from windows_autostart import autostart_status, install_autostart, remove_autostart
        try:
            if args.autostart_action == "install":
                install_autostart(root)
                print("Inicialização automática registrada para o logon do usuário atual.")
            elif args.autostart_action == "remove":
                removed = remove_autostart()
                print("Tarefa de inicialização removida." if removed else "Nenhuma tarefa registrada.")
            else:
                print("Tarefa registrada." if autostart_status() else "Tarefa não registrada.")
            return 0
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 5
    data_dir = Path(os.environ.get("SERMAX_PLATFORM_DATA", Path.home() / ".sermax-platform")).expanduser()
    backend_candidates = (root / "backend", root / "SERMAX-Platform" / "backend")
    backend = next((candidate for candidate in backend_candidates if (candidate / "server.py").is_file()), None)
    if backend is None:
        raise FileNotFoundError("Backend da Plataforma não encontrado nas pastas esperadas.")
    sys.path.insert(0, str(backend))
    configure_logging(data_dir)
    from instance_lock import acquire_instance_lock

    try:
        lock_handle = acquire_instance_lock(data_dir)
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 4
    try:
        return _run_server(args, root, data_dir)
    finally:
        lock_handle.close()

if __name__ == "__main__":
    raise SystemExit(main())
