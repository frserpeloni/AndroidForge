"""Launcher de homologação local com banco e memória temporários."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPOSITORY_ROOT / "SERMAX-Windows"
BACKEND_DIR = REPOSITORY_ROOT / "SERMAX-Platform" / "backend"
WORKER_SOURCE = CORE_DIR / "sermax_jarvis_worker.py"
ENVIRONMENT_KEYS = ("SERMAX_ROOT", "SERMAX_PLATFORM_DATA", "SERMAX_CORE_DIR", "PYTHONDONTWRITEBYTECODE")
REQUIRED_MODULES = ("fastapi", "uvicorn", "pypdf", "pypdfium2", "pytesseract", "PIL")


def prepare_environment(temp_root: Path, base_environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Direciona memória e banco para uma pasta temporária, sem copiar dados pessoais."""
    environment = dict(os.environ if base_environment is None else base_environment)
    temp_root.mkdir(parents=True, exist_ok=True)
    if not (CORE_DIR / "sermax_core.py").is_file():
        raise FileNotFoundError(f"Núcleo não encontrado: {CORE_DIR / 'sermax_core.py'}")
    if not WORKER_SOURCE.is_file():
        raise FileNotFoundError(f"Worker OpenJarvis não encontrado: {WORKER_SOURCE}")

    shutil.copy2(WORKER_SOURCE, temp_root / "sermax_jarvis_worker.py")
    environment["SERMAX_ROOT"] = str(temp_root.resolve())
    environment["SERMAX_PLATFORM_DATA"] = str((temp_root / "platform-data").resolve())
    environment["SERMAX_CORE_DIR"] = str(CORE_DIR.resolve())
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def missing_dependencies() -> list[str]:
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def _block_operational_action(*_args, **_kwargs):
    raise RuntimeError("Ações operacionais estão bloqueadas no modo de homologação isolada.")


def apply_safety_guards() -> None:
    """Bloqueia execução de comandos e planos durante os testes locais."""
    import sermax_executor
    import sermax_tarefas

    sermax_executor.executar = _block_operational_action
    sermax_tarefas.executar_plano = _block_operational_action


def main() -> int:
    if missing := missing_dependencies():
        print("Dependências ausentes: " + ", ".join(missing))
        print("Instale as dependências de SERMAX-Platform/backend/requirements.txt no ambiente Python ativo.")
        return 2
    if not BACKEND_DIR.is_dir():
        print(f"Backend não encontrado: {BACKEND_DIR}")
        return 2

    print("SERMAX Platform, homologação isolada")
    print("O núcleo será lido do repositório atual.")
    print("Memória pessoal e banco da Plataforma serão direcionados a uma pasta temporária.")
    print("Comandos operacionais e execução de planos ficam bloqueados.")
    print("C:\\SERMAX, main e backups não serão alterados.")
    print("Acesse http://127.0.0.1:8765. Pressione Ctrl+C para encerrar.")

    with tempfile.TemporaryDirectory(prefix="sermax-homologacao-") as temporary:
        temp_root = Path(temporary)
        environment = prepare_environment(temp_root)
        previous = {key: os.environ.get(key) for key in ENVIRONMENT_KEYS}
        original_path = list(sys.path)
        original_dont_write_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            for key in ENVIRONMENT_KEYS:
                os.environ[key] = environment[key]
            sys.path.insert(0, str(BACKEND_DIR))
            import server
            server.load_core()
            apply_safety_guards()
            import uvicorn
            print(f"Memória temporária: {temp_root / 'memoria_sermax.json'}")
            print(f"Banco temporário: {temp_root / 'platform-data' / 'platform.sqlite3'}")
            uvicorn.run(server.app, host="127.0.0.1", port=8765, log_level="info")
            return 0
        except KeyboardInterrupt:
            return 130
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            sys.path[:] = original_path
            sys.dont_write_bytecode = original_dont_write_bytecode


if __name__ == "__main__":
    raise SystemExit(main())
