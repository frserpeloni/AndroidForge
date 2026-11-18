"""Backup verificável de arquivos substituídos, sem caminhos de destino.

O módulo mantém os handles de origem durante a cópia, verifica FileId/volume/
links, calcula SHA-256 antes e depois da cópia e grava o backup por handles
relativos com ACL explícita e readback. Não altera a instalação ativa.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import re
import secrets
from ctypes import wintypes
from dataclasses import dataclass

from sermax_windows_handle_io import close_handle, query_handle_metadata
from sermax_update_inventory import (
    PROTECTED_FILES,
    PROTECTED_DIRECTORY_SEGMENTS,
    _normalize_relative,
)

FILE_LIST_DIRECTORY = 0x0001
FILE_READ_DATA = 0x0001
READ_CONTROL = 0x00020000
DEFAULT_CHUNK_SIZE = 1024 * 1024
MAX_CHUNK_SIZE = 16 * 1024 * 1024
_BACKUP_NAME = re.compile(r"^backup-[0-9a-f]{24}$")


class BackupError(RuntimeError):
    """Falha fechada ao verificar ou preservar arquivos da instalação."""


class NativeHandleReader:
    """Adaptador read(n) para um handle Windows aberto em leitura síncrona."""

    def __init__(self, handle):
        if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise BackupError("Leitura de backup por handle exige Windows x64.")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._read_file = kernel32.ReadFile
        self._read_file.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        self._read_file.restype = wintypes.BOOL
        self._seek = kernel32.SetFilePointerEx
        self._seek.argtypes = [
            wintypes.HANDLE, ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
        ]
        self._seek.restype = wintypes.BOOL
        self.handle = handle

    def seek_start(self) -> None:
        position = ctypes.c_longlong()
        if not self._seek(
            self.handle, ctypes.c_longlong(0), ctypes.byref(position), 0
        ) or position.value != 0:
            raise BackupError(
                f"Não foi possível reposicionar o arquivo de origem, "
                f"WinError={ctypes.get_last_error()}"
            )

    def read(self, size: int = DEFAULT_CHUNK_SIZE) -> bytes:
        if isinstance(size, bool) or not isinstance(size, int):
            raise BackupError("Tamanho de leitura inválido.")
        if size < 1 or size > MAX_CHUNK_SIZE:
            raise BackupError("Tamanho de leitura fora dos limites.")
        buffer = ctypes.create_string_buffer(size)
        read_count = wintypes.DWORD()
        if not self._read_file(
            self.handle, ctypes.byref(buffer), size,
            ctypes.byref(read_count), None,
        ):
            raise BackupError(
                f"ReadFile falhou durante backup, WinError={ctypes.get_last_error()}"
            )
        count = int(read_count.value)
        if count > size:
            raise BackupError("ReadFile excedeu o buffer solicitado.")
        return buffer.raw[:count]


@dataclass
class BackupSnapshot:
    """Backup completo ou parcial mantido sob handle privado."""

    component: str | None
    root_handle: object | None
    files: tuple[dict[str, object], ...]

    def close(self) -> None:
        if self.root_handle is not None:
            close_handle(self.root_handle)
            self.root_handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def _real_entries(handle):
    from sermax_windows_directory_handle import enumerate_stable_directory_handle
    return tuple(
        entry for entry in enumerate_stable_directory_handle(handle)
        if entry.name not in {".", ".."}
    )


def _validate_regular_source(metadata, expected_volume: int) -> None:
    if (
        metadata["is_directory"]
        or metadata["is_reparse_point"]
        or metadata["delete_pending"]
    ):
        raise BackupError("Origem não é arquivo regular estável.")
    if metadata["volume_serial_number"] != expected_volume:
        raise BackupError("Arquivo de origem pertence a volume divergente.")
    if metadata["number_of_links"] != 1:
        raise BackupError("Arquivo de origem possui hardlinks e foi rejeitado.")
    file_id = metadata.get("file_id_128")
    if (
        not isinstance(file_id, str)
        or len(file_id) != 32
        or any(ch not in "0123456789abcdefABCDEF" for ch in file_id)
    ):
        raise BackupError("FileId de origem inválido.")


def _open_source_file(root_handle, relative_path: str, expected_volume: int):
    from sermax_windows_directory_handle import open_verified_child_component

    parts = relative_path.split("/")
    parent_handle = root_handle
    opened_directories = []
    file_handle = None
    try:
        for part in parts[:-1]:
            matches = [
                entry for entry in _real_entries(parent_handle)
                if entry.name.casefold() == part.casefold()
            ]
            if not matches:
                return None, opened_directories, None
            if len(matches) != 1 or matches[0].name != part:
                raise BackupError(
                    f"Diretório de origem ausente, ambíguo ou com caixa divergente: {part}"
                )
            entry = matches[0]
            if not entry.is_directory or entry.is_reparse_point:
                raise BackupError(f"Componente pai não é diretório regular: {part}")
            child = open_verified_child_component(
                parent_handle,
                entry,
                desired_access=FILE_LIST_DIRECTORY,
            )
            opened_directories.append(child)
            metadata = query_handle_metadata(child)
            if (
                not metadata["is_directory"]
                or metadata["is_reparse_point"]
                or metadata["delete_pending"]
                or metadata["volume_serial_number"] != expected_volume
            ):
                raise BackupError(f"Diretório de origem instável: {part}")
            parent_handle = child

        leaf = parts[-1]
        matches = [
            entry for entry in _real_entries(parent_handle)
            if entry.name.casefold() == leaf.casefold()
        ]
        if not matches:
            return None, opened_directories, None
        if len(matches) != 1 or matches[0].name != leaf:
            raise BackupError(
                f"Arquivo de origem ausente, ambíguo ou com caixa divergente: {leaf}"
            )
        entry = matches[0]
        if entry.is_directory or entry.is_reparse_point:
            raise BackupError(f"Destino de origem não é arquivo regular: {relative_path}")
        file_handle = open_verified_child_component(
            parent_handle,
            entry,
            desired_access=FILE_READ_DATA,
        )
        metadata = query_handle_metadata(file_handle)
        _validate_regular_source(metadata, expected_volume)
        if (
            metadata["file_id_128"].lower() != entry.file_id.lower()
            or metadata["end_of_file"] != entry.end_of_file
        ):
            raise BackupError("Identidade ou tamanho da origem mudou durante a abertura.")
        return file_handle, opened_directories, metadata
    except Exception:
        if file_handle is not None:
            try:
                close_handle(file_handle)
            except Exception:
                pass
        for handle in reversed(opened_directories):
            try:
                close_handle(handle)
            except Exception:
                pass
        raise


def _close_source(file_handle, directory_handles) -> None:
    errors = []
    if file_handle is not None:
        try:
            close_handle(file_handle)
        except Exception as exc:
            errors.append(exc)
    for handle in reversed(directory_handles):
        try:
            close_handle(handle)
        except Exception as exc:
            errors.append(exc)
    if errors:
        raise BackupError(
            "Falha ao fechar handles de origem: " + "; ".join(map(str, errors))
        )


def _hash_and_rewind(reader: NativeHandleReader, expected_size: int) -> str:
    reader.seek_start()
    digest = hashlib.sha256()
    measured = 0
    while True:
        chunk = reader.read(DEFAULT_CHUNK_SIZE)
        if not chunk:
            break
        measured += len(chunk)
        if measured > expected_size:
            raise BackupError("Arquivo de origem cresceu durante a leitura.")
        digest.update(chunk)
    if measured != expected_size:
        raise BackupError("Tamanho efetivo da origem diverge dos metadados.")
    reader.seek_start()
    return digest.hexdigest()


def _preflight_targets(active_root_handle, manifest, root_volume):
    plan = {}
    for item in manifest.files:
        if item.action not in {"create", "replace"}:
            raise BackupError(f"Ação de manifesto não suportada: {item.action}")
        handle, parents, metadata = _open_source_file(
            active_root_handle, item.path, root_volume
        )
        try:
            if item.action == "create" and handle is not None:
                raise BackupError(
                    f"Manifesto exige create, mas o destino já existe: {item.path}"
                )
            if item.action == "replace" and handle is None:
                raise BackupError(
                    f"Manifesto exige replace, mas o arquivo não existe: {item.path}"
                )
            plan[item.path] = None if metadata is None else {
                "file_id_128": metadata["file_id_128"],
                "volume_serial_number": metadata["volume_serial_number"],
                "size": metadata["end_of_file"],
                "number_of_links": metadata["number_of_links"],
            }
        finally:
            _close_source(handle, parents)
    return plan


def backup_existing_files_by_handle(
    active_root_handle,
    backups_parent_handle,
    manifest,
) -> BackupSnapshot:
    """Preserva todos os destinos replace antes da fase de instalação.

    A operação é somente leitura na instalação ativa. O backup é criado sob
    backups_parent_handle por handles relativos, com ACL protegida. Destinos
    create precisam estar ausentes; destinos replace precisam existir e ser
    arquivos comuns sem reparse point ou hardlinks.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise BackupError("Backup verificável exige Windows x64.")
    from sermax_windows_private_area import (
        create_backup_directory_component,
        validate_private_directory_handle,
    )
    from sermax_windows_file_writer import write_verified_file_component
    from sermax_windows_handle_io import close_handle
    from sermax_update_staging import _preflight_handle_paths

    try:
        _preflight_handle_paths(manifest)
        protected_files = {name.casefold() for name in PROTECTED_FILES}
        for item in manifest.files:
            normalized = _normalize_relative(item.path)
            if (
                normalized.rsplit("/", 1)[-1].casefold() in protected_files
                or any(
                    part.casefold() in PROTECTED_DIRECTORY_SEGMENTS
                    for part in normalized.split("/")
                )
            ):
                raise BackupError(
                    f"Destino protegido não entra no fluxo de backup: {normalized}"
                )
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"Manifesto contém caminhos incompatíveis: {exc}") from exc

    active_metadata = query_handle_metadata(active_root_handle)
    if (
        not active_metadata["is_directory"]
        or active_metadata["is_reparse_point"]
        or active_metadata["delete_pending"]
    ):
        raise BackupError("Raiz ativa não é diretório regular validado.")
    root_volume = active_metadata["volume_serial_number"]

    parent_validation = validate_private_directory_handle(
        backups_parent_handle, require_empty=False
    )
    if parent_validation.get("valid") is not True:
        raise BackupError("Área backups não passou na validação ACL/Authz.")
    for entry in _real_entries(backups_parent_handle):
        if (
            not entry.is_directory
            or entry.is_reparse_point
            or not _BACKUP_NAME.fullmatch(entry.name)
        ):
            raise BackupError("Área backups contém objeto desconhecido ou reparse point.")

    plan = _preflight_targets(active_root_handle, manifest, root_volume)
    replacements = [
        item for item in manifest.files if item.action == "replace"
    ]
    if not replacements:
        return BackupSnapshot(component=None, root_handle=None, files=())

    component = "backup-" + secrets.token_hex(12)
    root_handle = None
    nested_handles = []
    directories = {}
    results = []

    try:
        root_handle = create_backup_directory_component(
            backups_parent_handle, component
        )
        directories[""] = root_handle

        def ensure_directory(relative: str):
            if not relative:
                return root_handle
            cached = directories.get(relative)
            if cached is not None:
                return cached
            current_relative = ""
            parent = root_handle
            for part in relative.split("/"):
                current_relative = (
                    f"{current_relative}/{part}" if current_relative else part
                )
                child = directories.get(current_relative)
                if child is None:
                    child = create_backup_directory_component(parent, part)
                    directories[current_relative] = child
                    nested_handles.append(child)
                parent = child
            return parent

        for item in replacements:
            expected = plan[item.path]
            source_handle, source_parents, source_metadata = _open_source_file(
                active_root_handle, item.path, root_volume
            )
            if source_handle is None or source_metadata is None:
                raise BackupError(f"Arquivo sumiu após o preflight: {item.path}")
            try:
                if (
                    source_metadata["file_id_128"].lower()
                    != expected["file_id_128"].lower()
                    or source_metadata["end_of_file"] != expected["size"]
                    or source_metadata["volume_serial_number"]
                    != expected["volume_serial_number"]
                    or source_metadata["number_of_links"] != 1
                ):
                    raise BackupError(
                        f"Identidade da origem mudou após o preflight: {item.path}"
                    )

                reader = NativeHandleReader(source_handle)
                source_hash = _hash_and_rewind(
                    reader, source_metadata["end_of_file"]
                )
                parent_path, leaf_name = (
                    item.path.rsplit("/", 1) if "/" in item.path else ("", item.path)
                )
                destination_parent = ensure_directory(parent_path)
                backup_result = write_verified_file_component(
                    destination_parent,
                    leaf_name,
                    reader,
                    expected_size=source_metadata["end_of_file"],
                    expected_sha256=source_hash,
                )

                after_copy = query_handle_metadata(source_handle)
                _validate_regular_source(after_copy, root_volume)
                if (
                    after_copy["file_id_128"].lower()
                    != source_metadata["file_id_128"].lower()
                    or after_copy["end_of_file"] != source_metadata["end_of_file"]
                ):
                    raise BackupError(
                        f"Identidade da origem mudou durante o backup: {item.path}"
                    )
                final_hash = _hash_and_rewind(
                    reader, after_copy["end_of_file"]
                )
                if final_hash != source_hash:
                    raise BackupError(
                        f"Conteúdo da origem mudou durante o backup: {item.path}"
                    )

                results.append({
                    "path": item.path,
                    "source_file_id_128": source_metadata["file_id_128"],
                    "source_volume_serial_number": source_metadata["volume_serial_number"],
                    "size": source_metadata["end_of_file"],
                    "sha256": source_hash,
                    "backup": backup_result,
                    "source_stable_after_copy": True,
                })
            finally:
                _close_source(source_handle, source_parents)

        for handle in reversed(nested_handles):
            close_handle(handle)
        nested_handles.clear()
        return BackupSnapshot(
            component=component,
            root_handle=root_handle,
            files=tuple(results),
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
        if isinstance(exc, BackupError):
            raise
        raise BackupError(
            f"Falha no backup; área parcial preservada: {component}"
        ) from exc
