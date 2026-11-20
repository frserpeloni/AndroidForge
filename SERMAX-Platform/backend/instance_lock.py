"""Bloqueio de instância única da Plataforma SERMAX."""
from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class InstanceLockError(RuntimeError):
    """A Plataforma já possui uma instância ativa neste diretório de dados."""


def acquire_instance_lock(data_dir: Path) -> BinaryIO:
    """Adquire bloqueio exclusivo liberado automaticamente ao fechar o handle."""
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / "platform-instance.lock"
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(bytes([0]))
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise InstanceLockError(
            "Já existe uma instância da Plataforma usando este diretório de dados. "
            "Encerre a instância ativa antes de iniciar outra."
        ) from exc
    return handle
