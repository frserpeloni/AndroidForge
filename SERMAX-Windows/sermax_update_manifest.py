"""Validação estrita de manifesto assinado para releases SERMAX.

Este módulo não instala arquivos. A assinatura é obrigatória e a verificação
criptográfica é fornecida por um backend confiável. Sem backend ou assinatura
válida, a validação falha fechada.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Mapping

from sermax_update_inventory import InventoryError, PROTECTED_FILES, _normalize_relative

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_FILES = 10000
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
_KEY_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SIGNATURE_ALGORITHM = "Ed25519"


class ManifestError(ValueError):
    """Manifesto ausente, malformado, não autenticado ou inseguro."""


@dataclass(frozen=True)
class ManifestFile:
    path: str
    size: int
    sha256: str
    action: str


@dataclass(frozen=True)
class ValidatedManifest:
    release_version: str
    files: tuple[ManifestFile, ...]
    key_id: str
    manifest_sha256: str


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"Chave JSON duplicada: {key!r}")
        result[key] = value
    return result


def _canonical_payload(document: Mapping[str, object]) -> bytes:
    unsigned = {key: value for key, value in document.items() if key != "signature"}
    try:
        return json.dumps(
            unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ManifestError("Conteúdo do manifesto não é canonicalizável.") from exc


def validate_signed_manifest(
    raw: bytes | str,
    *,
    verify_signature: Callable[[str, bytes, bytes], bool] | None,
) -> ValidatedManifest:
    """Valida schema, destinos e assinatura Ed25519 sem tocar no filesystem.

    verify_signature(key_id, canonical_payload, signature_bytes) deve consultar
    uma chave pública confiável incorporada ao verificador. Não aceitar chaves
    públicas fornecidas pelo próprio manifesto.
    """
    if verify_signature is None:
        raise ManifestError("Verificador de assinatura não configurado.")
    if isinstance(raw, str):
        try:
            raw = raw.encode("utf-8")
        except UnicodeError as exc:
            raise ManifestError("Manifesto não está em UTF-8 válido.") from exc
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_MANIFEST_BYTES:
        raise ManifestError("Tamanho do manifesto inválido.")

    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ManifestError(f"Constante JSON inválida: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("JSON do manifesto inválido.") from exc
    if not isinstance(document, dict):
        raise ManifestError("A raiz do manifesto deve ser um objeto JSON.")

    expected_top = {"schema_version", "release_version", "files", "signature"}
    if set(document) != expected_top:
        raise ManifestError("Campos do manifesto ausentes ou não reconhecidos.")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ManifestError("Versão de schema não suportada.")
    version = document["release_version"]
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ManifestError("Versão de release inválida.")
    prerelease = _VERSION.fullmatch(version).group(4-1)
    if prerelease is not None and any(
        len(identifier) > 1 and identifier.isdigit() and identifier.startswith("0")
        for identifier in prerelease.split(".")
    ):
        raise ManifestError("Identificador numérico de pré-release contém zero à esquerda.")

    files = document["files"]
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise ManifestError("Lista de arquivos vazia ou acima do limite.")

    signature = document["signature"]
    if not isinstance(signature, dict) or set(signature) != {"algorithm", "key_id", "value"}:
        raise ManifestError("Bloco de assinatura inválido.")
    if signature["algorithm"] != _SIGNATURE_ALGORITHM:
        raise ManifestError("Algoritmo de assinatura não permitido.")
    key_id = signature["key_id"]
    encoded_signature = signature["value"]
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise ManifestError("Identificador da chave inválido.")
    if not isinstance(encoded_signature, str) or len(encoded_signature) > 256:
        raise ManifestError("Assinatura codificada inválida.")
    try:
        signature_bytes = base64.b64decode(encoded_signature, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ManifestError("Assinatura não está em Base64 válido.") from exc
    if len(signature_bytes) != 64:
        raise ManifestError("Assinatura Ed25519 deve conter 64 bytes.")

    payload = _canonical_payload(document)
    try:
        trusted = verify_signature(key_id, payload, signature_bytes)
    except Exception as exc:
        raise ManifestError("Falha no verificador de assinatura.") from exc
    if trusted is not True:
        raise ManifestError("Assinatura do manifesto inválida ou chave não confiável.")

    parsed: list[ManifestFile] = []
    seen: set[str] = set()
    protected = {name.casefold() for name in PROTECTED_FILES}
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256", "classification", "action"}:
            raise ManifestError(f"Entrada {index} possui campos inválidos.")
        try:
            path = _normalize_relative(item["path"])
        except (InventoryError, TypeError) as exc:
            raise ManifestError(f"Caminho inseguro na entrada {index}.") from exc
        key = unicodedata.normalize("NFC", path).casefold()
        if key in seen:
            raise ManifestError(f"Caminho duplicado ou colisão de caixa: {path}")
        seen.add(key)
        protected_segments = {"_update", "backup", "backups", "historico", "history", "memoria", "memorias", "memory", "memories", "config", "configs", "configuracao", "configuracoes", "voice", "voz", "models", "modelos"}
        if path.rsplit("/", 1)[-1].casefold() in protected or any(part.casefold() in protected_segments for part in path.split("/")):
            raise ManifestError(f"Destino protegido no manifesto: {path}")
        if type(item["size"]) is not int or not 0 <= item["size"] <= MAX_FILE_SIZE:
            raise ManifestError(f"Tamanho inválido para {path}.")
        digest = item["sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ManifestError(f"SHA-256 inválido para {path}.")
        if item["classification"] != "managed":
            raise ManifestError(f"Classificação não gerenciada para {path}.")
        action = item["action"]
        if not isinstance(action, str) or action not in {"create", "replace"}:
            raise ManifestError(f"Ação não permitida para {path}.")
        parsed.append(ManifestFile(path=path, size=item["size"], sha256=digest, action=action))

    parsed.sort(key=lambda entry: entry.path.casefold())
    return ValidatedManifest(
        release_version=version,
        files=tuple(parsed),
        key_id=key_id,
        manifest_sha256=hashlib.sha256(payload).hexdigest(),
    )
