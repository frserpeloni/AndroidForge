"""Backup verificável de arquivos substituídos, sem caminhos de destino.

O módulo mantém os handles de origem durante a cópia, verifica FileId/volume/
links, calcula SHA-256 antes e depois da cópia e grava o backup por handles
relativos com ACL explícita e readback. Não altera a instalação ativa.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import io
import json
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
FILE_WRITE_DATA = 0x0002
FILE_READ_ATTRIBUTES = 0x00000080
FILE_WRITE_ATTRIBUTES = 0x00000100
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000
READ_CONTROL = 0x00020000
SYNCHRONIZE = 0x00100000
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_READONLY = 0x00000001
FILE_ATTRIBUTE_HIDDEN = 0x00000002
FILE_ATTRIBUTE_SYSTEM = 0x00000004
FILE_ATTRIBUTE_ARCHIVE = 0x00000020
FILE_ATTRIBUTE_TEMPORARY = 0x00000100
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED = 0x00002000
RESTORABLE_FILE_ATTRIBUTES = (
    FILE_ATTRIBUTE_READONLY | FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
    | FILE_ATTRIBUTE_ARCHIVE | FILE_ATTRIBUTE_TEMPORARY
    | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
)
_BACKUP_CATALOG = "__sermax_backup_catalog__.json"
MAX_BACKUP_CATALOG_BYTES = 64 * 1024 * 1024
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
    catalog: dict[str, object] | None = None

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


def _open_source_file(
    root_handle, relative_path: str, expected_volume: int, *,
    desired_access: int = FILE_READ_DATA | READ_CONTROL,
):
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
            desired_access=desired_access,
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
    from sermax_windows_effective_access import read_security_descriptor_binary
    from sermax_windows_handle_io import close_handle
    from sermax_update_staging import _preflight_handle_paths

    try:
        _preflight_handle_paths(manifest)
        protected_files = {name.casefold() for name in PROTECTED_FILES}
        for item in manifest.files:
            normalized = _normalize_relative(item.path)
            if normalized.casefold() == _BACKUP_CATALOG.casefold():
                raise BackupError("Caminho reservado para o catálogo interno de backup.")
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
                original_security_descriptor = read_security_descriptor_binary(
                    source_handle, require_directory=False
                )
                original_security_descriptor_b64 = base64.b64encode(
                    original_security_descriptor
                ).decode("ascii")
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
                    "source_attributes": source_metadata["attributes"],
                    "source_security_descriptor_b64": original_security_descriptor_b64,
                    "source_security_descriptor_sha256": hashlib.sha256(
                        original_security_descriptor
                    ).hexdigest(),
                    "size": source_metadata["end_of_file"],
                    "sha256": source_hash,
                    "backup": backup_result,
                    "source_stable_after_copy": True,
                })
            finally:
                _close_source(source_handle, source_parents)

        catalog_document = {
            "schema_version": 1,
            "backup_component": component,
            "files": [
                {
                    "path": item["path"],
                    "source_file_id_128": item["source_file_id_128"],
                    "source_volume_serial_number": item["source_volume_serial_number"],
                    "source_attributes": item["source_attributes"],
                    "source_security_descriptor_b64": item["source_security_descriptor_b64"],
                    "source_security_descriptor_sha256": item["source_security_descriptor_sha256"],
                    "size": item["size"],
                    "sha256": item["sha256"],
                    "backup_file_id_128": item["backup"]["file_id_128"],
                    "backup_volume_serial_number": item["backup"]["volume_serial_number"],
                    "backup_number_of_links": item["backup"]["number_of_links"],
                    "backup_size": item["backup"]["size"],
                    "backup_sha256": item["backup"]["sha256"],
                }
                for item in results
            ],
        }
        catalog_bytes = json.dumps(
            catalog_document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(catalog_bytes) > MAX_BACKUP_CATALOG_BYTES:
            raise BackupError("Catálogo de backup excede o limite de segurança.")
        catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
        catalog_result = write_verified_file_component(
            root_handle,
            _BACKUP_CATALOG,
            io.BytesIO(catalog_bytes),
            expected_size=len(catalog_bytes),
            expected_sha256=catalog_hash,
        )

        for handle in reversed(nested_handles):
            close_handle(handle)
        nested_handles.clear()
        return BackupSnapshot(
            component=component,
            root_handle=root_handle,
            files=tuple(results),
            catalog=catalog_result,
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


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BackupError(f"Chave JSON duplicada no catálogo: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise BackupError(f"Constante JSON não permitida: {value}")


def _read_bounded_handle(reader: NativeHandleReader, expected_size: int) -> bytes:
    if isinstance(expected_size, bool) or not isinstance(expected_size, int):
        raise BackupError("Tamanho do catálogo inválido.")
    if expected_size < 1 or expected_size > MAX_BACKUP_CATALOG_BYTES:
        raise BackupError("Tamanho do catálogo fora dos limites.")
    reader.seek_start()
    chunks = []
    measured = 0
    while True:
        chunk = reader.read(min(DEFAULT_CHUNK_SIZE, MAX_CHUNK_SIZE))
        if not chunk:
            break
        measured += len(chunk)
        if measured > expected_size or measured > MAX_BACKUP_CATALOG_BYTES:
            raise BackupError("Catálogo excedeu o tamanho autenticado.")
        chunks.append(chunk)
    if measured != expected_size:
        raise BackupError("Leitura do catálogo terminou com tamanho divergente.")
    return b"".join(chunks)


def _validate_backup_catalog(document: object, component: str, root_volume: int):
    if not isinstance(document, dict) or set(document) != {
        "schema_version", "backup_component", "files"
    }:
        raise BackupError("Estrutura do catálogo incompatível.")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise BackupError("Versão do catálogo não suportada.")
    if document["backup_component"] != component:
        raise BackupError("O catálogo pertence a outro componente de backup.")
    records = document["files"]
    if not isinstance(records, list) or not records or len(records) > 100000:
        raise BackupError("Lista de arquivos do catálogo inválida ou excessiva.")

    required = {
        "path", "source_file_id_128", "source_volume_serial_number",
        "source_attributes", "source_security_descriptor_b64",
        "source_security_descriptor_sha256", "size", "sha256",
        "backup_file_id_128", "backup_volume_serial_number",
        "backup_number_of_links", "backup_size", "backup_sha256",
    }
    seen = set()
    normalized_records = []
    for record in records:
        if not isinstance(record, dict) or set(record) != required:
            raise BackupError("Registro do catálogo contém campos ausentes ou extras.")
        path = record["path"]
        try:
            normalized = _normalize_relative(path)
        except Exception as exc:
            raise BackupError(f"Caminho inválido no catálogo: {path!r}") from exc
        if not isinstance(path, str) or normalized != path or path.casefold() == _BACKUP_CATALOG.casefold():
            raise BackupError("Caminho não canônico ou reservado no catálogo.")
        protected_files = {name.casefold() for name in PROTECTED_FILES}
        if (
            normalized.rsplit("/", 1)[-1].casefold() in protected_files
            or any(part.casefold() in PROTECTED_DIRECTORY_SEGMENTS for part in normalized.split("/"))
        ):
            raise BackupError("Catálogo contém caminho protegido.")
        folded = path.casefold()
        if folded in seen:
            raise BackupError("Caminho duplicado no catálogo.")
        seen.add(folded)

        for key in ("source_file_id_128", "backup_file_id_128"):
            value = record[key]
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", value):
                raise BackupError(f"{key} inválido no catálogo.")
        for key in (
            "source_volume_serial_number", "source_attributes", "size",
            "backup_volume_serial_number", "backup_number_of_links", "backup_size",
        ):
            value = record[key]
            if type(value) is not int or value < 0:
                raise BackupError(f"{key} inválido no catálogo.")
        if record["backup_volume_serial_number"] != root_volume:
            raise BackupError("Arquivo de backup registrado em volume divergente.")
        if record["backup_number_of_links"] != 1:
            raise BackupError("Catálogo registra backup com hardlinks.")
        if record["backup_size"] != record["size"]:
            raise BackupError("Tamanho do backup diverge do arquivo de origem.")
        if record["sha256"].lower() != record["backup_sha256"].lower():
            raise BackupError("Hash do backup diverge do hash da origem.")
        for key in ("sha256", "backup_sha256", "source_security_descriptor_sha256"):
            value = record[key]
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
                raise BackupError(f"{key} inválido no catálogo.")
        encoded = record["source_security_descriptor_b64"]
        if not isinstance(encoded, str):
            raise BackupError("Descritor de segurança original ausente.")
        try:
            descriptor = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise BackupError("Descritor de segurança original não é Base64 válido.") from exc
        if not 20 <= len(descriptor) <= 1024 * 1024:
            raise BackupError("Descritor de segurança original fora dos limites.")
        if hashlib.sha256(descriptor).hexdigest() != record["source_security_descriptor_sha256"].lower():
            raise BackupError("Hash do descritor de segurança original divergente.")
        normalized_records.append(record)

    file_paths = {record["path"].casefold() for record in normalized_records}
    for record in normalized_records:
        parts = record["path"].split("/")
        for index in range(1, len(parts)):
            parent_path = "/".join(parts[:index]).casefold()
            if parent_path in file_paths:
                raise BackupError("Catálogo contém colisão entre arquivo e diretório.")
    return tuple(normalized_records)


def verify_backup_by_handle(
    backups_parent_handle,
    component: str,
    *,
    expected_catalog_sha256: str,
) -> dict[str, object]:
    """Reabre e verifica integralmente um backup sem confiar no snapshot de criação.

    expected_catalog_sha256 deve vir de um evento previamente validado do
    journal. A função não consulta caminhos absolutos, não altera arquivos e
    não restaura conteúdo. Confere catálogo canônico, namespace exato, FileIds,
    volumes, links, tamanhos, hashes e ACL/Authz de diretórios e arquivos.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise BackupError("Verificação independente exige Windows x64.")
    if not isinstance(component, str) or not _BACKUP_NAME.fullmatch(component):
        raise BackupError("Nome do componente de backup inválido.")
    if (
        not isinstance(expected_catalog_sha256, str)
        or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_catalog_sha256)
    ):
        raise BackupError("Hash do catálogo ancorado no journal é obrigatório.")

    from sermax_windows_directory_handle import (
        enumerate_stable_directory_handle,
        open_verified_child_component,
    )
    from sermax_windows_private_area import validate_private_directory_handle
    from sermax_windows_file_writer import _validate_file_acl
    from sermax_windows_handle_io import close_handle
    from sermax_windows_private_area import _prepare_private_security_descriptor

    parent_meta = query_handle_metadata(backups_parent_handle)
    if (
        not parent_meta["is_directory"] or parent_meta["is_reparse_point"]
        or parent_meta["delete_pending"]
    ):
        raise BackupError("Handle pai de backups não é diretório regular.")
    parent_acl = validate_private_directory_handle(
        backups_parent_handle, require_empty=False
    )
    if parent_acl.get("valid") is not True or parent_acl.get("mutated") is not False:
        raise BackupError("ACL/Authz do diretório pai de backups inválida.")

    matches = [
        entry for entry in _real_entries(backups_parent_handle)
        if entry.name.casefold() == component.casefold()
    ]
    if len(matches) != 1 or matches[0].name != component:
        raise BackupError("Componente de backup ausente, ambíguo ou com caixa divergente.")
    root_entry = matches[0]
    if not root_entry.is_directory or root_entry.is_reparse_point:
        raise BackupError("Raiz do backup não é diretório regular.")

    root_handle = None
    token = None
    close_token = None
    opened_directories = []
    opened_files = []
    try:
        root_handle = open_verified_child_component(
            backups_parent_handle, root_entry,
            desired_access=0x0001 | 0x00020000,
        )
        root_meta = query_handle_metadata(root_handle)
        if (
            not root_meta["is_directory"] or root_meta["is_reparse_point"]
            or root_meta["delete_pending"]
            or root_meta["volume_serial_number"] != parent_meta["volume_serial_number"]
        ):
            raise BackupError("Identidade ou volume da raiz do backup inválido.")
        root_acl = validate_private_directory_handle(root_handle, require_empty=False)
        if root_acl.get("valid") is not True or root_acl.get("mutated") is not False:
            raise BackupError("ACL/Authz da raiz do backup inválida.")

        token, close_token, _descriptor_buffer, owner_sid = (
            _prepare_private_security_descriptor()
        )
        catalog_handle, catalog_parents, catalog_meta = _open_source_file(
            root_handle, _BACKUP_CATALOG, root_meta["volume_serial_number"]
        )
        if catalog_handle is None or catalog_meta is None:
            raise BackupError("Catálogo do backup ausente.")
        opened_files.append((catalog_handle, catalog_parents))
        _validate_file_acl(catalog_handle, token, owner_sid)
        catalog_bytes = _read_bounded_handle(
            NativeHandleReader(catalog_handle), catalog_meta["end_of_file"]
        )
        catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
        if catalog_hash.lower() != expected_catalog_sha256.lower():
            raise BackupError("Hash do catálogo diverge do hash ancorado no journal.")
        try:
            document = json.loads(
                catalog_bytes.decode("utf-8", errors="strict"),
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_reject_json_constant,
            )
        except BackupError:
            raise
        except Exception as exc:
            raise BackupError(f"Catálogo JSON inválido: {exc}") from exc
        canonical = json.dumps(
            document, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        if canonical != catalog_bytes:
            raise BackupError("Catálogo não está serializado em JSON canônico.")

        records = _validate_backup_catalog(
            document, component, root_meta["volume_serial_number"]
        )
        expected_files = {record["path"]: record for record in records}
        expected_dirs = {""}
        expected_children: dict[str, dict[str, str]] = {"": {
            _BACKUP_CATALOG: "file"
        }}
        for record in records:
            path = record["path"]
            parts = path.split("/")
            parent = ""
            for part in parts[:-1]:
                expected_children.setdefault(parent, {})[part] = "directory"
                parent = f"{parent}/{part}" if parent else part
                expected_dirs.add(parent)
                expected_children.setdefault(parent, {})
            expected_children.setdefault(parent, {})[parts[-1]] = "file"

        def walk(directory_handle, relative_dir: str):
            expected = expected_children.get(relative_dir, {})
            entries = tuple(
                entry for entry in enumerate_stable_directory_handle(directory_handle)
                if entry.name not in {".", ".."}
            )
            observed = {entry.name: entry for entry in entries}
            if set(observed) != set(expected):
                raise BackupError(
                    f"Árvore do backup contém arquivos ausentes ou extras em {relative_dir!r}."
                )
            for name, kind in expected.items():
                entry = observed[name]
                if entry.is_reparse_point:
                    raise BackupError(f"Reparse point no backup: {name}")
                relative_path = f"{relative_dir}/{name}" if relative_dir else name
                if kind == "directory":
                    if not entry.is_directory:
                        raise BackupError(f"Diretório esperado ausente: {relative_path}")
                    child = open_verified_child_component(
                        directory_handle, entry,
                        desired_access=0x0001 | 0x00020000,
                    )
                    opened_directories.append(child)
                    metadata = query_handle_metadata(child)
                    if (
                        not metadata["is_directory"] or metadata["is_reparse_point"]
                        or metadata["delete_pending"]
                        or metadata["volume_serial_number"] != root_meta["volume_serial_number"]
                    ):
                        raise BackupError(f"Diretório de backup inválido: {relative_path}")
                    acl = validate_private_directory_handle(child, require_empty=False)
                    if acl.get("valid") is not True or acl.get("mutated") is not False:
                        raise BackupError(f"ACL/Authz inválida: {relative_path}")
                    walk(child, relative_path)
                    continue

                if entry.is_directory:
                    raise BackupError(f"Arquivo esperado é diretório: {relative_path}")
                if relative_path == _BACKUP_CATALOG:
                    continue
                record = expected_files[relative_path]
                file_handle, parent_handles, metadata = _open_source_file(
                    root_handle, relative_path, root_meta["volume_serial_number"]
                )
                if file_handle is None or metadata is None:
                    raise BackupError(f"Arquivo do backup ausente: {relative_path}")
                opened_files.append((file_handle, parent_handles))
                if (
                    metadata["file_id_128"].lower() != record["backup_file_id_128"].lower()
                    or metadata["volume_serial_number"] != record["backup_volume_serial_number"]
                    or metadata["number_of_links"] != record["backup_number_of_links"]
                    or metadata["end_of_file"] != record["backup_size"]
                ):
                    raise BackupError(f"Metadados do backup divergentes: {relative_path}")
                _validate_file_acl(file_handle, token, owner_sid)
                digest = _hash_and_rewind(
                    NativeHandleReader(file_handle), metadata["end_of_file"]
                )
                if digest.lower() != record["backup_sha256"].lower():
                    raise BackupError(f"SHA-256 do backup divergente: {relative_path}")

        walk(root_handle, "")
        return {
            "valid": True,
            "component": component,
            "catalog_sha256": catalog_hash,
            "file_count": len(records),
            "directory_count": len(expected_dirs),
            "acl_validated": True,
            "authz_validated": True,
            "namespace_exact": True,
            "read_only": True,
        }
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"Falha na verificação independente do backup: {exc}") from exc
    finally:
        close_errors = []
        for file_handle, parents in reversed(opened_files):
            try:
                _close_source(file_handle, parents)
            except Exception as exc:
                close_errors.append(exc)
        for handle in reversed(opened_directories):
            try:
                close_handle(handle)
            except Exception as exc:
                close_errors.append(exc)
        if root_handle is not None:
            try:
                close_handle(root_handle)
            except Exception as exc:
                close_errors.append(exc)
        if token is not None and close_token is not None:
            try:
                close_token(token)
            except Exception as exc:
                close_errors.append(exc)
        if close_errors:
            raise BackupError(
                "Falha ao fechar handles durante verificação: "
                + "; ".join(map(str, close_errors))
            )


class _FILE_BASIC_INFO(ctypes.Structure):
    _fields_ = [
        ("CreationTime", ctypes.c_longlong),
        ("LastAccessTime", ctypes.c_longlong),
        ("LastWriteTime", ctypes.c_longlong),
        ("ChangeTime", ctypes.c_longlong),
        ("FileAttributes", wintypes.DWORD),
    ]


def _set_file_attributes_by_handle(handle, attributes: int) -> None:
    if type(attributes) is not int or attributes < 0 or attributes > 0xFFFFFFFF:
        raise BackupError("Atributos originais inválidos.")
    unsupported = attributes & ~RESTORABLE_FILE_ATTRIBUTES
    if unsupported and attributes != FILE_ATTRIBUTE_NORMAL:
        raise BackupError(
            f"Atributos de arquivo não suportados para restauração: 0x{unsupported:08X}"
        )
    if attributes == 0:
        attributes = FILE_ATTRIBUTE_NORMAL
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_info = kernel32.SetFileInformationByHandle
    set_info.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    set_info.restype = wintypes.BOOL
    info = _FILE_BASIC_INFO()
    info.FileAttributes = attributes
    if not set_info(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
        raise BackupError(
            "SetFileInformationByHandle(FileBasicInfo) falhou, "
            f"WinError={ctypes.get_last_error()}."
        )


def _restore_security_descriptor_by_handle(handle, descriptor_bytes: bytes) -> None:
    if not isinstance(descriptor_bytes, bytes) or not 20 <= len(descriptor_bytes) <= 1024 * 1024:
        raise BackupError("Descritor de segurança para restauração inválido.")
    try:
        import win32security
        descriptor = win32security.SECURITY_DESCRIPTOR(descriptor_bytes)
        if not descriptor.IsValid() or not descriptor.IsSelfRelative():
            raise BackupError("Descritor original não é válido/self-relative.")
        owner = descriptor.GetSecurityDescriptorOwner()
        group = descriptor.GetSecurityDescriptorGroup()
        control, _revision = descriptor.GetSecurityDescriptorControl()
        dacl_present = bool(control & 0x0004)
        if owner is None or group is None or not dacl_present:
            raise BackupError(
                "Descritor original sem owner, group ou DACL presente; restauração recusada."
            )
        dacl = descriptor.GetSecurityDescriptorDacl()
        flags = (
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.GROUP_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION
        )
        if control & 0x1000:
            flags |= 0x80000000
        else:
            flags |= 0x20000000
        native = handle.value if isinstance(handle, ctypes.c_void_p) else int(handle)
        win32security.SetSecurityInfo(
            native, win32security.SE_FILE_OBJECT, flags,
            owner, group, dacl, None,
        )
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"Falha ao restaurar ACL original por handle: {exc}") from exc


def _security_descriptor_matches(handle, expected_bytes: bytes) -> bool:
    try:
        import win32security
        expected = win32security.SECURITY_DESCRIPTOR(expected_bytes)
        native = handle.value if isinstance(handle, ctypes.c_void_p) else int(handle)
        actual = win32security.GetSecurityInfo(
            native,
            win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.GROUP_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION,
        )

        def sid_text(sid):
            return None if sid is None else win32security.ConvertSidToStringSid(sid)

        expected_control, _ = expected.GetSecurityDescriptorControl()
        actual_control, _ = actual.GetSecurityDescriptorControl()
        control_mask = 0x0004 | 0x1000
        if (expected_control & control_mask) != (actual_control & control_mask):
            return False
        if sid_text(expected.GetSecurityDescriptorOwner()) != sid_text(actual.GetSecurityDescriptorOwner()):
            return False
        if sid_text(expected.GetSecurityDescriptorGroup()) != sid_text(actual.GetSecurityDescriptorGroup()):
            return False

        expected_dacl = expected.GetSecurityDescriptorDacl()
        actual_dacl = actual.GetSecurityDescriptorDacl()
        if (expected_dacl is None) != (actual_dacl is None):
            return False
        if expected_dacl is None:
            return True

        def canonical_ace(ace):
            def canonical(value):
                if isinstance(value, (tuple, list)):
                    return tuple(canonical(item) for item in value)
                if isinstance(value, (bytes, str, int, bool)) or value is None:
                    return value
                try:
                    return ("sid", win32security.ConvertSidToStringSid(value))
                except Exception:
                    return repr(value)
            return canonical(ace)

        if expected_dacl.GetAceCount() != actual_dacl.GetAceCount():
            return False
        return all(
            canonical_ace(expected_dacl.GetAce(index))
            == canonical_ace(actual_dacl.GetAce(index))
            for index in range(expected_dacl.GetAceCount())
        )
    except Exception as exc:
        raise BackupError(f"Falha ao conferir ACL restaurada: {exc}") from exc


def _restore_file_content_by_handle(
    destination_handle,
    backup_reader: NativeHandleReader,
    *,
    expected_size: int,
    expected_sha256: str,
    original_attributes: int,
    original_security_descriptor: bytes,
) -> dict[str, object]:
    from sermax_windows_file_writer import _write_apis, _write_all, _readback

    _set_file_attributes_by_handle(destination_handle, FILE_ATTRIBUTE_NORMAL)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    seek = kernel32.SetFilePointerEx
    seek.argtypes = [
        wintypes.HANDLE, ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
    ]
    seek.restype = wintypes.BOOL
    set_eof = kernel32.SetEndOfFile
    set_eof.argtypes = [wintypes.HANDLE]
    set_eof.restype = wintypes.BOOL
    native = destination_handle.value if isinstance(destination_handle, ctypes.c_void_p) else destination_handle
    position = ctypes.c_longlong()
    if not seek(native, ctypes.c_longlong(0), ctypes.byref(position), 0) or position.value != 0:
        raise BackupError(f"Não foi possível posicionar o destino, WinError={ctypes.get_last_error()}.")
    if not set_eof(native):
        raise BackupError(f"Não foi possível truncar o destino, WinError={ctypes.get_last_error()}.")

    write_file, read_file, flush, seek = _write_apis()
    digest = hashlib.sha256()
    measured = 0
    backup_reader.seek_start()
    while True:
        chunk = backup_reader.read(DEFAULT_CHUNK_SIZE)
        if not chunk:
            break
        measured += len(chunk)
        if measured > expected_size:
            raise BackupError("Backup excedeu o tamanho autenticado durante restauração.")
        digest.update(chunk)
        _write_all(native, chunk, write_file)
    if measured != expected_size or digest.hexdigest().lower() != expected_sha256.lower():
        raise BackupError("Conteúdo do backup divergiu durante restauração.")
    if not flush(native):
        raise BackupError(f"FlushFileBuffers falhou, WinError={ctypes.get_last_error()}.")

    readback_hash, readback_size = _readback(
        native, expected_size, read_file, seek
    )
    if readback_size != expected_size or readback_hash.lower() != expected_sha256.lower():
        raise BackupError("Readback do arquivo restaurado divergiu.")

    _restore_security_descriptor_by_handle(
        destination_handle, original_security_descriptor
    )
    if not _security_descriptor_matches(destination_handle, original_security_descriptor):
        raise BackupError("ACL/owner/group restaurados divergem do descritor original.")

    _set_file_attributes_by_handle(destination_handle, original_attributes)
    metadata = query_handle_metadata(destination_handle)
    if metadata["end_of_file"] != expected_size or metadata["attributes"] != original_attributes:
        if not (
            metadata["end_of_file"] == expected_size
            and original_attributes == FILE_ATTRIBUTE_NORMAL
            and metadata["attributes"] == 0
        ):
            raise BackupError("Tamanho ou atributos finais divergem do catálogo.")
    return {
        "sha256": readback_hash,
        "size": readback_size,
        "attributes": metadata["attributes"],
        "security_descriptor_verified": True,
    }


def restore_backup_files_by_handle(
    active_root_handle,
    backups_parent_handle,
    backup_component: str,
    journal_session,
) -> dict[str, object]:
    """Restaura arquivos replace e registra cada sucesso no journal.

    Exige evento ROLLBACK_STARTED já persistido. O componente e hash do
    catálogo são obtidos de BACKUP_COMPLETE na própria cadeia validada.
    A rotina verifica o backup antes de qualquer escrita. A restauração é
    feita por handle no arquivo existente; se o destino estiver ausente, ele
    é recriado exclusivamente e recebe o descritor/atributos originais.

    A escrita in-place não é atômica. Uma falha durante a cópia deixa o
    journal sem FILE_RESTORED para aquele arquivo; o chamador deve registrar
    RECOVERY_REQUIRED e executar nova verificação antes de prosseguir.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise BackupError("Restauração verificável exige Windows x64.")
    if not isinstance(backup_component, str) or not _BACKUP_NAME.fullmatch(backup_component):
        raise BackupError("Componente de backup inválido.")
    if journal_session is None or not hasattr(journal_session, "read_events") or not hasattr(journal_session, "append_event"):
        raise BackupError("Sessão de journal válida é obrigatória.")

    from sermax_windows_directory_handle import open_verified_child_component
    from sermax_windows_file_writer import write_verified_file_component

    events = journal_session.read_events()
    if not events or events[-1]["event"] not in {"ROLLBACK_STARTED", "FILE_RESTORED"}:
        raise BackupError("Journal precisa estar em ROLLBACK_STARTED/FILE_RESTORED.")
    backup_events = [
        item for item in events
        if item["event"] == "BACKUP_COMPLETE"
    ]
    if not backup_events:
        raise BackupError("Journal não contém BACKUP_COMPLETE.")
    backup_payload = backup_events[-1]["payload"]
    expected_catalog_sha256 = backup_payload.get("catalog_sha256")
    if backup_payload.get("backup_component") != backup_component or not expected_catalog_sha256:
        raise BackupError("Componente/hash do backup diverge do journal.")

    verification = verify_backup_by_handle(
        backups_parent_handle,
        backup_component,
        expected_catalog_sha256=expected_catalog_sha256,
    )
    if verification.get("valid") is not True:
        raise BackupError("Verificação independente do backup não foi confirmada.")

    backup_entries = [
        entry for entry in _real_entries(backups_parent_handle)
        if entry.name == backup_component
    ]
    if len(backup_entries) != 1 or not backup_entries[0].is_directory:
        raise BackupError("Raiz do backup desapareceu após verificação.")
    backup_root = open_verified_child_component(
        backups_parent_handle,
        backup_entries[0],
        desired_access=FILE_LIST_DIRECTORY | READ_CONTROL,
    )
    backup_root_metadata = query_handle_metadata(backup_root)
    active_root_metadata = query_handle_metadata(active_root_handle)
    if (
        not active_root_metadata["is_directory"]
        or active_root_metadata["is_reparse_point"]
        or active_root_metadata["delete_pending"]
        or active_root_metadata["volume_serial_number"] != backup_root_metadata["volume_serial_number"]
    ):
        close_handle(backup_root)
        raise BackupError("Raiz ativa e backup não pertencem ao mesmo volume regular.")

    catalog_handle = None
    catalog_parents = []
    opened_backup_files = []
    opened_active_files = []
    created_count = 0
    restored_count = 0
    already_restored_count = 0
    try:
        catalog_handle, catalog_parents, catalog_meta = _open_source_file(
            backup_root, _BACKUP_CATALOG, backup_root_metadata["volume_serial_number"]
        )
        if catalog_handle is None or catalog_meta is None:
            raise BackupError("Catálogo desapareceu após verificação.")
        raw_catalog = _read_bounded_handle(
            NativeHandleReader(catalog_handle), catalog_meta["end_of_file"]
        )
        document = json.loads(
            raw_catalog.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_json_constant,
        )
        records = _validate_backup_catalog(
            document, backup_component, backup_root_metadata["volume_serial_number"]
        )
        restored_paths = {
            item["payload"]["path"]: item["payload"]["sha256"]
            for item in events if item["event"] == "FILE_RESTORED"
        }
        for record in records:
            path = record["path"]
            expected_hash = record["sha256"].lower()
            if path in restored_paths:
                if restored_paths[path].lower() != expected_hash:
                    raise BackupError(f"Journal registra hash divergente para {path}.")
            descriptor_bytes = base64.b64decode(
                record["source_security_descriptor_b64"], validate=True
            )
            source_handle, source_parents, source_meta = _open_source_file(
                backup_root, path, backup_root_metadata["volume_serial_number"]
            )
            if source_handle is None or source_meta is None:
                raise BackupError(f"Arquivo do backup ausente: {path}")
            opened_backup_files.append((source_handle, source_parents))
            source_reader = NativeHandleReader(source_handle)
            if (
                source_meta["end_of_file"] != record["backup_size"]
                or _hash_and_rewind(source_reader, record["backup_size"]).lower() != expected_hash
            ):
                raise BackupError(f"Arquivo de backup não confere: {path}")

            target_access = (
                FILE_READ_DATA | FILE_WRITE_DATA | FILE_READ_ATTRIBUTES
                | FILE_WRITE_ATTRIBUTES | READ_CONTROL | WRITE_DAC
                | WRITE_OWNER | SYNCHRONIZE
            )
            target_handle, target_parents, target_meta = _open_source_file(
                active_root_handle, path, active_root_metadata["volume_serial_number"],
                desired_access=target_access,
            )
            if target_handle is None:
                parent_handle = target_parents[-1] if target_parents else active_root_handle
                leaf_name = path.rsplit("/", 1)[-1]
                write_verified_file_component(
                    parent_handle, leaf_name, source_reader,
                    expected_size=record["size"], expected_sha256=expected_hash,
                )
                created_count += 1
                target_handle, target_parents, target_meta = _open_source_file(
                    active_root_handle, path, active_root_metadata["volume_serial_number"],
                    desired_access=target_access,
                )
            if target_handle is None or target_meta is None:
                raise BackupError(f"Não foi possível abrir destino para restauração: {path}")
            opened_active_files.append((target_handle, target_parents))
            _validate_regular_source(target_meta, active_root_metadata["volume_serial_number"])
            if target_meta["number_of_links"] != 1:
                raise BackupError(f"Destino possui hardlinks: {path}")

            current_hash = _hash_and_rewind(
                NativeHandleReader(target_handle), target_meta["end_of_file"]
            )
            if path in restored_paths:
                if (
                    current_hash.lower() != expected_hash
                    or target_meta["attributes"] != record["source_attributes"]
                    or not _security_descriptor_matches(target_handle, descriptor_bytes)
                ):
                    raise BackupError(
                        f"Arquivo registrado como restaurado diverge no disco: {path}"
                    )
                already_restored_count += 1
                continue

            result = _restore_file_content_by_handle(
                target_handle,
                source_reader,
                expected_size=record["size"],
                expected_sha256=expected_hash,
                original_attributes=record["source_attributes"],
                original_security_descriptor=descriptor_bytes,
            )
            journal_session.append_event(
                "FILE_RESTORED",
                {"path": path, "sha256": result["sha256"].lower()},
            )
            restored_count += 1

        return {
            "valid": True,
            "backup_component": backup_component,
            "file_count": len(records),
            "restored_count": restored_count,
            "already_restored_count": already_restored_count,
            "recreated_missing_count": created_count,
            "journal_last_event": journal_session.read_events()[-1]["event"],
            "read_only_backup": True,
        }
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(
            "Restauração interrompida. Preserve backup e journal; "
            "registre RECOVERY_REQUIRED antes de nova tentativa: " + str(exc)
        ) from exc
    finally:
        close_errors = []
        if catalog_handle is not None:
            try:
                _close_source(catalog_handle, catalog_parents)
            except Exception as exc:
                close_errors.append(exc)
        for file_handle, parents in reversed(opened_backup_files):
            try:
                _close_source(file_handle, parents)
            except Exception as exc:
                close_errors.append(exc)
        for file_handle, parents in reversed(opened_active_files):
            try:
                _close_source(file_handle, parents)
            except Exception as exc:
                close_errors.append(exc)
        try:
            close_handle(backup_root)
        except Exception as exc:
            close_errors.append(exc)
        if close_errors:
            raise BackupError(
                "Falha ao fechar handles da restauração: "
                + "; ".join(map(str, close_errors))
            )
