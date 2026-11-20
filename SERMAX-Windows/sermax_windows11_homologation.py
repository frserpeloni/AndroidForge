"""Relatório somente leitura para homologação local do SERMAX no Windows 11.

Não inicia o SERMAX, não altera arquivos, não cria diretórios e não escreve
relatórios no disco. O conteúdo de memoria_sermax.json nunca é lido nem exibido.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import ntpath

_REPARSE_POINT = 0x0400
_INSTALL_FILES = {
    "executable": "SERMAX.exe",
    "terminal": "SERMAX_terminal/sermax_terminal.py",
    "memory": "memoria_sermax.json",
}


def _utc_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _inspect_file(root: Path, relative: str, *, hash_content: bool = False) -> dict[str, Any]:
    path = root.joinpath(*relative.split("/"))
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return {"path": relative, "exists": False, "regular_file": False}
    except OSError as exc:
        return {
            "path": relative,
            "exists": None,
            "regular_file": False,
            "inspection_error": type(exc).__name__,
        }

    is_reparse = bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)
    is_regular = stat.S_ISREG(info.st_mode) and not is_reparse
    result: dict[str, Any] = {
        "path": relative,
        "exists": True,
        "regular_file": is_regular,
        "reparse_point": is_reparse,
        "size_bytes": info.st_size,
        "modified_utc": _utc_timestamp(info.st_mtime),
    }
    if hash_content and is_regular:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError as exc:
            result["hash_error"] = type(exc).__name__
        else:
            result["sha256"] = digest.hexdigest()
    return result


def _is_root_installation(root: str) -> bool:
    normalized = ntpath.normcase(ntpath.normpath(ntpath.abspath(root)))
    drive, _ = ntpath.splitdrive(normalized)
    expected = ntpath.normcase(ntpath.join(drive + ntpath.sep, "SERMAX"))
    return bool(drive) and normalized == expected


def _windows_11_status(system: str, version: str) -> bool | None:
    if system != "Windows":
        return False
    try:
        build = int(version.split(".")[-1])
    except (AttributeError, TypeError, ValueError):
        return None
    return build >= 22000


def _inspect_recovery(root: str, inspector: Callable[[str], dict[str, Any]] | None):
    if platform.system() != "Windows" or not _is_root_installation(root):
        return {"status": "NOT_APPLICABLE"}
    if inspector is None:
        try:
            from sermax_startup_gate import inspect_update_recovery_at_startup
        except Exception as exc:
            return {"status": "UNAVAILABLE", "error": type(exc).__name__}
        inspector = inspect_update_recovery_at_startup
    try:
        assessment = inspector(root)
    except Exception as exc:
        return {"status": "BLOCKED_OR_UNAVAILABLE", "error": type(exc).__name__}

    transactions = []
    for item in assessment.get("transactions", []):
        if not isinstance(item, dict):
            continue
        transactions.append({
            "transaction_id": item.get("transaction_id"),
            "state": item.get("state"),
            "startup_action": item.get("startup_action"),
            "last_event": item.get("last_event"),
        })
    return {
        "status": "ASSESSED",
        "configured": assessment.get("configured"),
        "startup_allowed": assessment.get("startup_allowed"),
        "pending_count": assessment.get("pending_count"),
        "automatic_rollback_performed": assessment.get("automatic_rollback_performed"),
        "transactions": transactions,
    }


def collect_report(
    install_root: str,
    *,
    system: str | None = None,
    release: str | None = None,
    version: str | None = None,
    machine: str | None = None,
    recovery_inspector: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Coleta metadados locais sem modificar a instalação."""
    root_text = os.path.abspath(os.fspath(install_root))
    root = Path(root_text)
    system = platform.system() if system is None else system
    release = platform.release() if release is None else release
    version = platform.version() if version is None else version
    machine = platform.machine() if machine is None else machine

    root_error = None
    try:
        root_info = os.lstat(root)
        root_exists = True
        root_is_directory = stat.S_ISDIR(root_info.st_mode)
        root_is_reparse = bool(getattr(root_info, "st_file_attributes", 0) & _REPARSE_POINT)
    except FileNotFoundError:
        root_exists = False
        root_is_directory = False
        root_is_reparse = False
    except OSError as exc:
        root_exists = None
        root_is_directory = False
        root_is_reparse = False
        root_error = type(exc).__name__
    else:
        root_error = None

    files = {
        key: _inspect_file(root, relative, hash_content=(key == "terminal"))
        if root_exists and root_is_directory and not root_is_reparse
        else {"path": relative, "exists": False, "regular_file": False}
        for key, relative in _INSTALL_FILES.items()
    }

    return {
        "schema_version": 1,
        "read_only": True,
        "collected_utc": datetime.now(timezone.utc).isoformat(),
        "host": {
            "system": system,
            "release": release,
            "version": version,
            "machine": machine,
            "python": sys.version.split()[0],
            "windows_11": _windows_11_status(system, version),
        },
        "installation": {
            "root": root_text,
            "root_exists": root_exists,
            "root_is_directory": root_is_directory,
            "root_is_reparse_point": root_is_reparse,
            "root_inspection_error": root_error,
            "files": files,
            "recovery": _inspect_recovery(root_text, recovery_inspector),
        },
        "privacy": {
            "memory_file_content_read": False,
            "memory_file_content_included": False,
            "file_contents_included": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera um relatório local somente leitura do SERMAX."
    )
    parser.add_argument(
        "--root",
        default=r"C:\SERMAX",
        help=r"Diretório da instalação (padrão: C:\SERMAX).",
    )
    args = parser.parse_args(argv)
    report = collect_report(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
