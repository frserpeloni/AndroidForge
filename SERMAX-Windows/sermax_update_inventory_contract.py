"""Planejamento somente de leitura entre inventário por handles e manifesto validado.

Este módulo não abre arquivos, não escreve no filesystem e não instala releases.
A entrada deve ser um inventário produzido por uma camada de leitura confiável
e um ValidatedManifest cuja assinatura já tenha sido verificada.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping, Sequence

from sermax_update_inventory import InventoryError, _normalize_relative, is_protected_path
from sermax_update_manifest import ValidatedManifest

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_ALLOWED_TYPES = {"file", "directory", "reparse", "special"}
_ALLOWED_CLASSIFICATIONS = {"managed", "unknown", "protected", "blocked"}


class InventoryContractError(ValueError):
    """Inventário e manifesto não formam um plano seguro."""


@dataclass(frozen=True)
class InventoryPlanEntry:
    path: str
    action: str
    expected_size: int
    expected_sha256: str
    current_file_id: str | None


@dataclass(frozen=True)
class InventoryPlan:
    release_version: str
    entries: tuple[InventoryPlanEntry, ...]


def _path_key(value: object) -> tuple[str, str]:
    try:
        normalized = _normalize_relative(value)
    except (InventoryError, TypeError) as exc:
        raise InventoryContractError("Caminho de inventário inválido.") from exc
    return normalized, unicodedata.normalize("NFC", normalized).casefold()


def classify_inventory(
    inventory: Sequence[Mapping[str, object]],
    managed_paths: Sequence[str],
) -> list[dict[str, object]]:
    """Aplica allowlist explícita ao inventário, sem ler nem alterar arquivos.

    Somente arquivos regulares listados na allowlist recebem classificação
    managed. Diretórios permanecem unknown, dados protegidos permanecem
    protected e entradas bloqueadas nunca viram managed.
    """
    if not isinstance(inventory, (list, tuple)):
        raise InventoryContractError("Inventário deve ser uma sequência.")
    if not isinstance(managed_paths, (list, tuple)):
        raise InventoryContractError("Allowlist deve ser uma sequência.")

    allowed: set[str] = set()
    for raw_path in managed_paths:
        _, key = _path_key(raw_path)
        if key in allowed:
            raise InventoryContractError("Allowlist contém caminho duplicado.")
        if is_protected_path(raw_path):
            raise InventoryContractError("Allowlist inclui caminho protegido.")
        allowed.add(key)

    seen: set[str] = set()
    classified: list[dict[str, object]] = []
    found_managed: set[str] = set()
    for index, record in enumerate(inventory):
        if not isinstance(record, Mapping):
            raise InventoryContractError(f"Registro {index} inválido.")
        path, key = _path_key(record.get("path"))
        if key in seen:
            raise InventoryContractError(f"Colisão de caminhos no inventário: {path}")
        seen.add(key)
        entry_type = record.get("type")
        if entry_type not in _ALLOWED_TYPES:
            raise InventoryContractError(f"Tipo inválido no inventário: {path}")
        protected = is_protected_path(path)
        if protected:
            classification = "protected"
        elif entry_type in {"reparse", "special"}:
            classification = "blocked"
        elif entry_type == "directory":
            classification = "unknown"
        elif key in allowed:
            classification = "managed"
            found_managed.add(key)
        else:
            classification = "unknown"
        item = dict(record)
        item["classification"] = classification
        classified.append(item)

    missing = allowed - found_managed
    if missing:
        raise InventoryContractError(
            "Allowlist aponta para arquivo regular ausente ou não elegível: "
            + ", ".join(sorted(missing))
        )
    return classified


def build_inventory_plan(
    inventory: Sequence[Mapping[str, object]],
    manifest: ValidatedManifest,
) -> InventoryPlan:
    """Confronta destinos assinados com inventário e retorna plano sem mutações.

    Ação create exige destino ausente. Ação replace exige arquivo regular
    existente. Destinos ambíguos, protegidos, bloqueados ou com colisão
    case-insensitive abortam o plano inteiro.
    """
    if not isinstance(inventory, (list, tuple)):
        raise InventoryContractError("Inventário deve ser uma sequência.")
    if not isinstance(manifest, ValidatedManifest):
        raise InventoryContractError("Manifesto precisa estar validado e autenticado.")

    current: dict[str, tuple[str, Mapping[str, object]]] = {}
    for index, record in enumerate(inventory):
        if not isinstance(record, Mapping):
            raise InventoryContractError(f"Registro {index} inválido.")
        path, key = _path_key(record.get("path"))
        if key in current:
            raise InventoryContractError(f"Colisão de caminhos no inventário: {path}")
        entry_type = record.get("type")
        classification = record.get("classification")
        if entry_type not in _ALLOWED_TYPES:
            raise InventoryContractError(f"Tipo inválido no inventário: {path}")
        if classification not in _ALLOWED_CLASSIFICATIONS:
            raise InventoryContractError(f"Classificação inválida: {path}")
        if is_protected_path(path) and classification != "protected":
            raise InventoryContractError(f"Caminho protegido mal classificado: {path}")
        current[key] = (path, record)

    planned: list[InventoryPlanEntry] = []
    seen_targets: set[str] = set()
    for item in manifest.files:
        path, key = _path_key(item.path)
        if key in seen_targets:
            raise InventoryContractError(f"Colisão de destinos do manifesto: {path}")
        seen_targets.add(key)
        if is_protected_path(path):
            raise InventoryContractError(f"Destino protegido: {path}")

        existing = current.get(key)
        if item.action == "create":
            if existing is not None:
                raise InventoryContractError(f"Destino create já existe: {path}")
            file_id = None
        elif item.action == "replace":
            if existing is None:
                raise InventoryContractError(f"Destino replace não existe: {path}")
            existing_path, record = existing
            if record["type"] != "file":
                raise InventoryContractError(
                    f"Destino replace não é arquivo regular: {existing_path}"
                )
            if record["classification"] != "managed":
                raise InventoryContractError(
                    f"Destino replace não consta na allowlist managed: {existing_path}"
                )
            size = record.get("size")
            digest = record.get("sha256")
            if type(size) is not int or size < 0:
                raise InventoryContractError(
                    f"Tamanho atual ausente ou inválido: {existing_path}"
                )
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                raise InventoryContractError(
                    f"Hash atual ausente ou inválido: {existing_path}"
                )
            raw_file_id = record.get("file_id")
            if not isinstance(raw_file_id, str) or not _FILE_ID.fullmatch(raw_file_id):
                raise InventoryContractError(
                    f"FileId de 128 bits ausente ou inválido: {existing_path}"
                )
            file_id = raw_file_id.lower()
        else:
            raise InventoryContractError(f"Ação não suportada: {item.action}")

        planned.append(InventoryPlanEntry(
            path=path,
            action=item.action,
            expected_size=item.size,
            expected_sha256=item.sha256,
            current_file_id=file_id,
        ))

    # Um destino de arquivo não pode substituir um diretório com filhos.
    # Também não pode ter como ancestral um arquivo, reparse ou diretório
    # protegido/bloqueado no inventário.
    for entry in planned:
        target_key = unicodedata.normalize("NFC", entry.path).casefold()
        prefix = target_key + "/"
        if any(existing_key.startswith(prefix) for existing_key in current):
            raise InventoryContractError(
                f"Destino do manifesto é ancestral de entradas existentes: {entry.path}"
            )
        parts = target_key.split("/")
        for end in range(1, len(parts)):
            ancestor = "/".join(parts[:end])
            found = current.get(ancestor)
            if found is None:
                continue
            ancestor_path, record = found
            if record["type"] != "directory" or record["classification"] in {
                "protected", "blocked"
            }:
                raise InventoryContractError(
                    f"Ancestral impede destino do manifesto: {ancestor_path}"
                )

    return InventoryPlan(
        release_version=manifest.release_version,
        entries=tuple(sorted(planned, key=lambda entry: entry.path.casefold())),
    )
