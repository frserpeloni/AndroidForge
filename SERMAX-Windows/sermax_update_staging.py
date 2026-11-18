"""Extração verificada de releases SERMAX para staging isolado.

Este módulo não toca na instalação ativa, não executa scripts e não confirma
uma atualização. O staging_parent deve ser um diretório privado, controlado
pelo processo e com ACL que impeça escrita por outros usuários.
"""
from __future__ import annotations

import hashlib
import io
import os
import stat
import tempfile
import zipfile
from pathlib import Path

from sermax_update_inventory import InventoryError, _normalize_relative, _is_reparse_point
from sermax_update_manifest import ValidatedManifest
from sermax_update_package import PackageError, validate_release_archive


class StagingError(RuntimeError):
    """Falha ao preparar staging seguro; staging incompleto é preservado."""


def _assert_real_directory(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise StagingError(f"Não foi possível inspecionar diretório: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or _is_reparse_point(info) or not stat.S_ISDIR(info.st_mode):
        raise StagingError(f"Diretório ausente, inválido ou reparse point: {path}")


def _ensure_safe_parents(root: Path, relative: str) -> Path:
    parts = _normalize_relative(relative).split("/")
    current = root
    for part in parts[:-1]:
        current = current / part
        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise StagingError(f"Falha ao preparar diretório do staging: {relative}") from exc
        _assert_real_directory(current)
    return current / parts[-1]


def stage_verified_release(
    archive_bytes: bytes,
    manifest: ValidatedManifest,
    *,
    staging_parent: str | os.PathLike[str],
) -> Path:
    """Valida pacote e extrai seus arquivos para diretório novo e exclusivo.

    A validação estrutural/criptográfica do manifesto deve ocorrer antes desta
    chamada. O pacote é revalidado integralmente aqui. Em caso de erro durante
    a escrita, o diretório parcial é preservado para inspeção, sem tocar na
    instalação ativa.
    """
    parent = Path(staging_parent)
    _assert_real_directory(parent)
    try:
        verified = validate_release_archive(archive_bytes, manifest)
    except PackageError as exc:
        raise StagingError("Pacote não passou na validação integral.") from exc

    try:
        stage = Path(tempfile.mkdtemp(prefix="sermax-stage-", dir=parent))
    except OSError as exc:
        raise StagingError("Não foi possível reservar staging exclusivo.") from exc

    if os.name != "nt":
        try:
            stage.chmod(0o700)
        except OSError as exc:
            raise StagingError(f"Não foi possível restringir permissões do staging: {stage}") from exc

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as package:
            entries = {info.filename: info for info in package.infolist()}
            for item in manifest.files:
                destination = _ensure_safe_parents(stage, item.path)
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                flags |= getattr(os, "O_BINARY", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                try:
                    descriptor = os.open(destination, flags, 0o600)
                except OSError as exc:
                    raise StagingError(f"Não foi possível criar arquivo exclusivo: {item.path}") from exc

                digest = hashlib.sha256()
                measured = 0
                try:
                    with os.fdopen(descriptor, "wb") as output, package.open(entries[item.path], "r") as source:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            measured += len(chunk)
                            if measured > item.size:
                                raise StagingError(f"Arquivo excedeu tamanho autenticado: {item.path}")
                            digest.update(chunk)
                            output.write(chunk)
                        output.flush()
                        os.fsync(output.fileno())
                except Exception:
                    # O staging parcial permanece isolado para inspeção.
                    raise
                if measured != item.size or digest.hexdigest() != item.sha256:
                    raise StagingError(f"Verificação pós-escrita falhou: {item.path}")

        _assert_real_directory(stage)
        return stage
    except StagingError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError, InventoryError) as exc:
        raise StagingError(f"Falha durante extração; staging preservado em: {stage}") from exc
