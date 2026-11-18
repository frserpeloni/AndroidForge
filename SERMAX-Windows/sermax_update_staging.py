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
import secrets
import re
import zipfile
from pathlib import Path
from dataclasses import dataclass

from sermax_update_inventory import InventoryError, _normalize_relative, _is_reparse_point
from sermax_update_manifest import ValidatedManifest
from sermax_update_package import PackageError, validate_release_archive


@dataclass
class HandleStagedRelease:
    """Árvore de staging criada por handles; o chamador fecha root_handle."""

    component: str
    root_handle: object
    files: tuple[dict[str, object], ...]

    def close(self) -> None:
        if self.root_handle is not None:
            from sermax_windows_handle_io import close_handle
            close_handle(self.root_handle)
            self.root_handle = None

    def __enter__(self):
        if self.root_handle is None:
            raise StagingError("Handle do staging já foi encerrado.")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def _preflight_handle_paths(manifest: ValidatedManifest) -> None:
    """Rejeita colisões de caixa e conflitos arquivo/diretório antes de gravar."""
    from sermax_windows_handle_io import _validate_component

    spellings: dict[str, str] = {}
    files: set[str] = set()
    directories: set[str] = set()
    for item in manifest.files:
        normalized = _normalize_relative(item.path)
        parts = normalized.split("/")
        for part in parts:
            _validate_component(part)
        for index in range(1, len(parts)):
            directory = "/".join(parts[:index])
            key = directory.casefold()
            previous = spellings.setdefault(key, directory)
            if previous != directory:
                raise StagingError("Colisão de caixa em diretório do manifesto.")
            if key in files:
                raise StagingError("Um arquivo do manifesto também é diretório pai.")
            directories.add(key)
        file_key = normalized.casefold()
        previous = spellings.setdefault(file_key, normalized)
        if previous != normalized:
            raise StagingError("Colisão de caixa em caminho de arquivo do manifesto.")
        if file_key in directories:
            raise StagingError("Um destino do manifesto conflita com diretório.")
        files.add(file_key)


def stage_verified_release_by_handle(
    archive_bytes: bytes,
    manifest: ValidatedManifest,
    *,
    staging_parent_handle,
) -> HandleStagedRelease:
    """Valida e extrai a release inteira sob uma árvore criada por handles.

    O manifesto precisa ter sido autenticado antes da chamada. O pai deve ser
    um diretório privado validado e permanecer aberto. Nenhum caminho é usado
    para criar diretórios ou arquivos. Em caso de falha, a árvore parcial fica
    preservada e seus handles são fechados para inspeção posterior.
    """
    try:
        from sermax_windows_handle_io import HandleIoError
        validate_release_archive(archive_bytes, manifest)
        _preflight_handle_paths(manifest)
    except (PackageError, InventoryError, HandleIoError) as exc:
        raise StagingError("Pacote ou caminhos não passaram na validação integral.") from exc

    from sermax_windows_private_area import (
        create_staging_directory_component,
        validate_private_directory_handle,
    )
    from sermax_windows_directory_handle import enumerate_stable_directory_handle
    from sermax_windows_file_writer import write_verified_file_component
    from sermax_windows_handle_io import close_handle

    stage_component = "stage-" + secrets.token_hex(12)
    root_handle = None
    nested_handles: list[object] = []
    directories: dict[str, object] = {}
    file_results: list[dict[str, object]] = []

    try:
        parent_validation = validate_private_directory_handle(
            staging_parent_handle, require_empty=False
        )
        existing_stages = enumerate_stable_directory_handle(staging_parent_handle)
        for entry in existing_stages:
            if (
                not entry.is_directory
                or entry.is_reparse_point
                or not re.fullmatch(r"stage-[0-9a-f]{24}", entry.name)
            ):
                raise StagingError(
                    "A área staging contém objeto desconhecido, arquivo ou reparse point."
                )
        if parent_validation.get("valid") is not True:
            raise StagingError("A área staging não passou na validação ACL/Authz.")
        root_handle = create_staging_directory_component(
            staging_parent_handle, stage_component
        )
        directories[""] = root_handle

        def ensure_directory(relative: str):
            if not relative:
                return root_handle
            cached = directories.get(relative)
            if cached is not None:
                return cached
            parts = relative.split("/")
            current_relative = ""
            parent_handle = root_handle
            for part in parts:
                current_relative = (
                    f"{current_relative}/{part}" if current_relative else part
                )
                child_handle = directories.get(current_relative)
                if child_handle is None:
                    child_handle = create_staging_directory_component(
                        parent_handle, part
                    )
                    directories[current_relative] = child_handle
                    nested_handles.append(child_handle)
                parent_handle = child_handle
            return parent_handle

        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as package:
            entries = {info.filename: info for info in package.infolist()}
            for item in manifest.files:
                if "/" in item.path:
                    parent_path, leaf_name = item.path.rsplit("/", 1)
                else:
                    parent_path, leaf_name = "", item.path
                parent_handle = ensure_directory(parent_path)
                with package.open(entries[item.path], "r") as source:
                    result = write_verified_file_component(
                        parent_handle,
                        leaf_name,
                        source,
                        expected_size=item.size,
                        expected_sha256=item.sha256,
                    )
                file_results.append(result)

        for handle in reversed(nested_handles):
            close_handle(handle)
        nested_handles.clear()
        return HandleStagedRelease(
            component=stage_component,
            root_handle=root_handle,
            files=tuple(file_results),
        )
    except Exception as exc:
        for handle in reversed(nested_handles):
            try:
                close_handle(handle)
            except Exception:
                pass
        if root_handle is not None:
            try:
                close_handle(root_handle)
            except Exception:
                pass
        if isinstance(exc, StagingError):
            raise
        if root_handle is not None:
            detail = f"árvore parcial preservada: {stage_component}"
        else:
            detail = "a pasta de staging não chegou a ser criada"
        raise StagingError(f"Falha no staging por handles; {detail}") from exc


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
        validate_release_archive(archive_bytes, manifest)
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
