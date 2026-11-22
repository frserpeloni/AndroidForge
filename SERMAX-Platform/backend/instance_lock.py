"""Bloqueio de instância única da Plataforma SERMAX."""
from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class InstanceLockError(RuntimeError):
    """A Plataforma já possui uma instância ativa neste diretório de dados."""



def acquire_instance_lock(data_dir: Path) -> BinaryIO:
    """Adquire bloqueio exclusivo liberado automaticamente ao fechar o handle.

    O arquivo de lock é criado em ``data_dir/platform-instance.lock``. Em
    sistemas Windows a API ``msvcrt.locking`` é usada; em Unix/Linux a
    chamada ``fcntl.flock`` garante exclusividade não‑bloqueante.
    """
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

            # ``LOCK_EX`` garante exclusividade; ``LOCK_NB`` evita bloqueio
            # bloqueante, lançando ``BlockingIOError`` se já houver outro
            # processo com o lock.
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as exc:
        handle.close()
        raise InstanceLockError("Another instance is already running.") from exc
    return handle
