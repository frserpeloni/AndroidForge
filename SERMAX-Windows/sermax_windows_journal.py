"""Journal transacional append-only, encadeado por SHA-256 e operado por handles.

Cada evento ocupa um arquivo exclusivo criado com FILE_CREATE. Não há
sobrescrita de registros. Lacunas, duplicatas, arquivos desconhecidos ou
qualquer quebra da cadeia interrompem a leitura para recuperação segura.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
from dataclasses import dataclass

from sermax_windows_handle_io import close_handle, query_handle_metadata

FILE_LIST_DIRECTORY = 0x0001
FILE_ADD_FILE = 0x0002
FILE_READ_DATA = 0x0001
READ_CONTROL = 0x00020000
MAX_JOURNAL_EVENT_BYTES = 1024 * 1024
MAX_JOURNAL_EVENTS = 4096
MAX_JOURNAL_TOTAL_BYTES = 64 * 1024 * 1024
MAX_JOURNAL_TRANSACTIONS = 1024
_TRANSACTION_NAME = re.compile(r"^txn-[0-9a-f]{24}$")
_EVENT_NAME = re.compile(r"^event-([0-9]{6})\.json$")
_ZERO_HASH = "0" * 64
_ALLOWED_EVENTS = {
    "PREPARED",
    "BACKUP_COMPLETE",
    "STAGING_COMPLETE",
    "INSTALL_STARTED",
    "FILE_INSTALL_INTENT",
    "FILE_REPLACED",
    "COMMITTED",
    "ROLLBACK_STARTED",
    "FILE_RESTORED",
    "FILE_REMOVED",
    "ROLLED_BACK",
    "RECOVERY_REQUIRED",
}

_TRANSITIONS = {
    None: {"PREPARED"},
    "PREPARED": {"BACKUP_COMPLETE", "STAGING_COMPLETE", "RECOVERY_REQUIRED"},
    "BACKUP_COMPLETE": {"STAGING_COMPLETE", "RECOVERY_REQUIRED"},
    "STAGING_COMPLETE": {"INSTALL_STARTED", "RECOVERY_REQUIRED"},
    "INSTALL_STARTED": {"FILE_INSTALL_INTENT", "FILE_REPLACED", "COMMITTED", "ROLLBACK_STARTED", "RECOVERY_REQUIRED"},
    "FILE_INSTALL_INTENT": {"FILE_REPLACED", "ROLLBACK_STARTED", "RECOVERY_REQUIRED"},
    "FILE_REPLACED": {"FILE_INSTALL_INTENT", "FILE_REPLACED", "COMMITTED", "ROLLBACK_STARTED", "RECOVERY_REQUIRED"},
    "COMMITTED": set(),
    "ROLLBACK_STARTED": {"FILE_RESTORED", "FILE_REMOVED", "ROLLED_BACK", "RECOVERY_REQUIRED"},
    "FILE_RESTORED": {"FILE_RESTORED", "FILE_REMOVED", "ROLLED_BACK", "RECOVERY_REQUIRED"},
    "FILE_REMOVED": {"FILE_RESTORED", "FILE_REMOVED", "ROLLED_BACK", "RECOVERY_REQUIRED"},
    "ROLLED_BACK": set(),
    "RECOVERY_REQUIRED": {"RECOVERY_REQUIRED", "ROLLBACK_STARTED"},
}


def _validate_event_payload(event: str, payload: dict) -> None:
    required = {
        "PREPARED": ("release_version", "manifest_sha256"),
        "BACKUP_COMPLETE": ("backup_component", "catalog_sha256"),
        "STAGING_COMPLETE": ("staging_component", "archive_sha256"),
        "INSTALL_STARTED": (),
        "FILE_INSTALL_INTENT": ("path", "sha256", "file_id_128"),
        "FILE_REPLACED": ("path", "sha256", "file_id_128"),
        "COMMITTED": ("release_version",),
        "ROLLBACK_STARTED": ("reason",),
        "FILE_RESTORED": ("path", "sha256"),
        "FILE_REMOVED": ("path", "sha256", "file_id_128"),
        "ROLLED_BACK": ("reason",),
        "RECOVERY_REQUIRED": ("reason",),
    }[event]
    if any(key not in payload for key in required):
        raise JournalError(f"Payload incompleto para evento {event}.")
    for key in ("manifest_sha256", "archive_sha256", "catalog_sha256", "sha256"):
        if key in payload and payload[key] is not None:
            value = payload[key]
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(ch not in "0123456789abcdef" for ch in value)
            ):
                raise JournalError(f"Hash inválido no payload: {key}.")
    for key in ("file_id_128",):
        if key in payload and (
            not isinstance(payload[key], str)
            or not re.fullmatch(r"[0-9a-fA-F]{32}", payload[key])
        ):
            raise JournalError(f"FileId inválido no payload: {key}.")
    for key in ("release_version", "reason"):
        if key in payload and (
            not isinstance(payload[key], str) or not payload[key].strip()
        ):
            raise JournalError(f"Campo textual inválido no payload: {key}.")
    if "path" in payload:
        from sermax_update_inventory import (
            PROTECTED_FILES, PROTECTED_DIRECTORY_SEGMENTS, _normalize_relative,
        )
        try:
            normalized = _normalize_relative(payload["path"])
        except Exception as exc:
            raise JournalError("Caminho inválido no evento.") from exc
        if normalized != payload["path"]:
            raise JournalError("Caminho do evento não está normalizado.")
        if (
            normalized.rsplit("/", 1)[-1].casefold()
            in {name.casefold() for name in PROTECTED_FILES}
            or any(
                part.casefold() in PROTECTED_DIRECTORY_SEGMENTS
                for part in normalized.split("/")
            )
        ):
            raise JournalError("Evento aponta para caminho protegido.")
    if event == "BACKUP_COMPLETE":
        component = payload["backup_component"]
        catalog_hash = payload["catalog_sha256"]
        if (component is None) != (catalog_hash is None):
            raise JournalError("Backup vazio exige componente e hash nulos.")
        if component is not None and (
            not isinstance(component, str)
            or not re.fullmatch(r"backup-[0-9a-f]{24}", component)
        ):
            raise JournalError("Componente de backup inválido.")
    if event == "STAGING_COMPLETE":
        component = payload["staging_component"]
        if (
            not isinstance(component, str)
            or not re.fullmatch(r"stage-[0-9a-f]{24}", component)
        ):
            raise JournalError("Componente de staging inválido.")


def _validate_transition(previous_event: str | None, event: str) -> None:
    if event not in _TRANSITIONS.get(previous_event, set()):
        raise JournalError(
            f"Transição de journal inválida: {previous_event!r} -> {event!r}."
        )


class JournalError(RuntimeError):
    """Journal inválido, inconsistente ou não durável."""


def _canonical_json(value) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise JournalError(f"Evento não é JSON canônico válido: {exc}") from exc


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise JournalError(f"Chave JSON duplicada no journal: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise JournalError(f"Constante JSON não permitida: {value}")


def _real_entries(handle):
    from sermax_windows_directory_handle import enumerate_stable_directory_handle
    return tuple(
        entry for entry in enumerate_stable_directory_handle(handle)
        if entry.name not in {".", ".."}
    )


def _validate_journal_parent(parent_handle) -> dict[str, object]:
    from sermax_windows_private_area import validate_private_directory_handle

    validation = validate_private_directory_handle(
        parent_handle, require_empty=False
    )
    if validation.get("valid") is not True:
        raise JournalError("Área journal não passou na validação ACL/Authz.")
    for entry in _real_entries(parent_handle):
        if (
            not entry.is_directory
            or entry.is_reparse_point
            or not _TRANSACTION_NAME.fullmatch(entry.name)
        ):
            raise JournalError(
                "Área journal contém objeto desconhecido ou reparse point."
            )
    return validation


def _read_event_bytes(handle, expected_volume: int) -> bytes:
    from sermax_windows_backup import NativeHandleReader

    metadata = query_handle_metadata(handle)
    if (
        metadata["is_directory"]
        or metadata["is_reparse_point"]
        or metadata["delete_pending"]
        or metadata["volume_serial_number"] != expected_volume
        or metadata["number_of_links"] != 1
        or metadata["end_of_file"] < 1
        or metadata["end_of_file"] > MAX_JOURNAL_EVENT_BYTES
    ):
        raise JournalError("Metadados do evento de journal inválidos.")

    reader = NativeHandleReader(handle)
    reader.seek_start()
    chunks = []
    total = 0
    while True:
        chunk = reader.read(min(1024 * 1024, MAX_JOURNAL_EVENT_BYTES))
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_JOURNAL_EVENT_BYTES:
            raise JournalError("Evento excedeu o limite de tamanho.")
        chunks.append(chunk)
    if total != metadata["end_of_file"]:
        raise JournalError("Tamanho efetivo do evento diverge dos metadados.")
    return b"".join(chunks)


def read_journal_events_by_handle(
    transaction_handle, transaction_id: str
) -> tuple[dict[str, object], ...]:
    """Lê e valida integralmente a cadeia de eventos de uma transação."""
    from sermax_windows_directory_handle import open_verified_child_component
    from sermax_windows_private_area import validate_private_directory_handle

    if not isinstance(transaction_id, str) or not _TRANSACTION_NAME.fullmatch(transaction_id):
        raise JournalError("Identificador de transação inválido.")
    validation = validate_private_directory_handle(
        transaction_handle, require_empty=False
    )
    if validation.get("valid") is not True:
        raise JournalError("Diretório da transação não passou na validação ACL/Authz.")

    directory_metadata = query_handle_metadata(transaction_handle)
    if (
        not directory_metadata["is_directory"]
        or directory_metadata["is_reparse_point"]
        or directory_metadata["delete_pending"]
    ):
        raise JournalError("Handle da transação não é diretório regular.")

    entries = _real_entries(transaction_handle)
    if len(entries) > MAX_JOURNAL_EVENTS:
        raise JournalError("Quantidade de eventos excede o limite do journal.")
    if any(
        isinstance(entry.end_of_file, bool)
        or not isinstance(entry.end_of_file, int)
        or entry.end_of_file < 1
        or entry.end_of_file > MAX_JOURNAL_EVENT_BYTES
        for entry in entries
    ):
        raise JournalError("Metadados de tamanho de evento fora dos limites.")
    total_declared = sum(entry.end_of_file for entry in entries)
    if total_declared > MAX_JOURNAL_TOTAL_BYTES:
        raise JournalError("Tamanho total do journal excede o limite de segurança.")
    indexed = []
    for entry in entries:
        match = _EVENT_NAME.fullmatch(entry.name)
        if (
            match is None
            or entry.is_directory
            or entry.is_reparse_point
        ):
            raise JournalError(
                f"Objeto inesperado na transação: {entry.name}"
            )
        indexed.append((int(match.group(1)), entry))

    indexed.sort(key=lambda item: item[0])
    events = []
    previous_hash = _ZERO_HASH
    expected_sequence = 1
    for sequence, entry in indexed:
        if sequence != expected_sequence:
            raise JournalError("Journal contém lacuna ou sequência duplicada.")
        event_handle = None
        try:
            event_handle = open_verified_child_component(
                transaction_handle,
                entry,
                desired_access=FILE_READ_DATA | READ_CONTROL,
            )
            raw = _read_event_bytes(
                event_handle, directory_metadata["volume_serial_number"]
            )
        finally:
            if event_handle is not None:
                close_handle(event_handle)

        file_hash = hashlib.sha256(raw).hexdigest()
        try:
            record = json.loads(
                raw.decode("utf-8", errors="strict"),
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_constant,
            )
        except JournalError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JournalError("Evento JSON corrompido.") from exc

        expected_keys = {
            "schema_version", "transaction_id", "sequence", "event",
            "previous_hash", "payload", "record_sha256",
        }
        if not isinstance(record, dict) or set(record) != expected_keys:
            raise JournalError("Schema do evento de journal inválido.")
        if raw != _canonical_json(record):
            raise JournalError("Evento não está na serialização canônica esperada.")
        if type(record["schema_version"]) is not int or record["schema_version"] != 1:
            raise JournalError("Versão do schema de journal não suportada.")
        if record["transaction_id"] != transaction_id:
            raise JournalError("Evento pertence a outra transação.")
        if (
            type(record["sequence"]) is not int
            or record["sequence"] != sequence
        ):
            raise JournalError("Sequência interna diverge do nome do arquivo.")
        if (
            not isinstance(record["event"], str)
            or record["event"] not in _ALLOWED_EVENTS
        ):
            raise JournalError("Tipo de evento não permitido.")
        if not isinstance(record["payload"], dict):
            raise JournalError("Payload do evento precisa ser objeto JSON.")
        if (
            not isinstance(record["previous_hash"], str)
            or len(record["previous_hash"]) != 64
            or any(ch not in "0123456789abcdef" for ch in record["previous_hash"])
            or record["previous_hash"] != previous_hash
        ):
            raise JournalError("Cadeia hash do journal foi interrompida.")
        record_hash = record["record_sha256"]
        if (
            not isinstance(record_hash, str)
            or len(record_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in record_hash)
        ):
            raise JournalError("Hash interno do evento inválido.")
        body = {key: value for key, value in record.items() if key != "record_sha256"}
        calculated_record_hash = hashlib.sha256(_canonical_json(body)).hexdigest()
        if calculated_record_hash != record_hash:
            raise JournalError("Hash interno do evento diverge.")
        _validate_event_payload(record["event"], record["payload"])
        previous_event = events[-1]["event"] if events else None
        _validate_transition(previous_event, record["event"])
        events.append({
            **record,
            "file_sha256": file_hash,
        })
        previous_hash = record_hash
        expected_sequence += 1

    return tuple(events)


@dataclass
class JournalSession:
    transaction_id: str
    handle: object | None

    def read_events(self) -> tuple[dict[str, object], ...]:
        if self.handle is None:
            raise JournalError("Sessão do journal já foi encerrada.")
        return read_journal_events_by_handle(self.handle, self.transaction_id)

    def append_event(
        self, event: str, payload: dict[str, object]
    ) -> dict[str, object]:
        if self.handle is None:
            raise JournalError("Sessão do journal já foi encerrada.")
        if not isinstance(event, str) or event not in _ALLOWED_EVENTS:
            raise JournalError("Tipo de evento não permitido.")
        if not isinstance(payload, dict):
            raise JournalError("Payload do evento precisa ser objeto JSON.")
        _validate_event_payload(event, payload)
        payload_bytes = _canonical_json(payload)
        if len(payload_bytes) > MAX_JOURNAL_EVENT_BYTES // 2:
            raise JournalError("Payload do evento excede o limite.")

        current = self.read_events()
        sequence = len(current) + 1
        if sequence > MAX_JOURNAL_EVENTS:
            raise JournalError("Limite de eventos por transação excedido.")
        previous_event = current[-1]["event"] if current else None
        _validate_transition(previous_event, event)
        previous_hash = current[-1]["record_sha256"] if current else _ZERO_HASH
        body = {
            "schema_version": 1,
            "transaction_id": self.transaction_id,
            "sequence": sequence,
            "event": event,
            "previous_hash": previous_hash,
            "payload": payload,
        }
        record_hash = hashlib.sha256(_canonical_json(body)).hexdigest()
        record = {**body, "record_sha256": record_hash}
        raw = _canonical_json(record)
        if len(raw) > MAX_JOURNAL_EVENT_BYTES:
            raise JournalError("Evento excede o limite de tamanho.")
        filename = f"event-{sequence:06d}.json"

        from sermax_windows_file_writer import write_verified_file_component

        file_result = write_verified_file_component(
            self.handle,
            filename,
            io.BytesIO(raw),
            expected_size=len(raw),
            expected_sha256=hashlib.sha256(raw).hexdigest(),
        )
        verified = self.read_events()
        if (
            len(verified) != sequence
            or verified[-1]["record_sha256"] != record_hash
            or verified[-1]["file_sha256"] != file_result["sha256"]
        ):
            raise JournalError("Readback da nova entrada não confirmou a cadeia.")
        return {**record, "file_sha256": file_result["sha256"]}

    def close(self) -> None:
        if self.handle is not None:
            close_handle(self.handle)
            self.handle = None

    def __enter__(self):
        if self.handle is None:
            raise JournalError("Sessão do journal já foi encerrada.")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def create_journal_transaction_by_handle(
    journal_parent_handle,
) -> JournalSession:
    """Cria uma transação append-only exclusiva dentro da área journal."""
    from sermax_windows_private_area import create_journal_directory_component

    _validate_journal_parent(journal_parent_handle)
    transaction_id = "txn-" + secrets.token_hex(12)
    handle = create_journal_directory_component(
        journal_parent_handle, transaction_id
    )
    return JournalSession(transaction_id=transaction_id, handle=handle)


def open_journal_transaction_by_handle(
    journal_parent_handle, transaction_id: str
) -> JournalSession:
    """Reabre uma transação existente, vinculando nome e FileId pelo handle."""
    from sermax_windows_directory_handle import open_verified_child_component

    if not isinstance(transaction_id, str) or not _TRANSACTION_NAME.fullmatch(transaction_id):
        raise JournalError("Identificador de transação inválido.")
    _validate_journal_parent(journal_parent_handle)
    matches = [
        entry for entry in _real_entries(journal_parent_handle)
        if entry.name == transaction_id
    ]
    if len(matches) != 1 or not matches[0].is_directory or matches[0].is_reparse_point:
        raise JournalError("Transação ausente, ambígua ou insegura.")
    handle = open_verified_child_component(
        journal_parent_handle,
        matches[0],
        desired_access=FILE_LIST_DIRECTORY | FILE_ADD_FILE | READ_CONTROL,
    )
    try:
        from sermax_windows_private_area import validate_private_directory_handle
        validation = validate_private_directory_handle(
            handle, require_empty=False
        )
        if validation.get("valid") is not True:
            raise JournalError("ACL/Authz da transação não foi confirmada.")
        read_journal_events_by_handle(handle, transaction_id)
        return JournalSession(transaction_id=transaction_id, handle=handle)
    except Exception:
        close_handle(handle)
        raise



def scan_journal_transactions_by_handle(
    journal_parent_handle,
) -> tuple[dict[str, object], ...]:
    """Enumera transações e identifica quais exigem recuperação.

    A função é somente leitura. Qualquer transação corrompida ou com namespace
    inválido interrompe a varredura. Transações sem PREPARED ou sem evento
    terminal são marcadas como exigindo recuperação, sem alterar arquivos.
    """
    from sermax_windows_directory_handle import open_verified_child_component

    _validate_journal_parent(journal_parent_handle)
    entries = _real_entries(journal_parent_handle)
    if len(entries) > MAX_JOURNAL_TRANSACTIONS:
        raise JournalError("Quantidade de transações excede o limite de segurança.")

    summaries = []
    for entry in sorted(entries, key=lambda item: item.name):
        transaction_handle = None
        try:
            transaction_handle = open_verified_child_component(
                journal_parent_handle,
                entry,
                desired_access=FILE_LIST_DIRECTORY | READ_CONTROL,
            )
            events = read_journal_events_by_handle(
                transaction_handle, entry.name
            )
            last_event = events[-1]["event"] if events else None
            terminal = last_event in {"COMMITTED", "ROLLED_BACK"}
            install_started = any(
                item["event"] == "INSTALL_STARTED" for item in events
            )
            summaries.append({
                "transaction_id": entry.name,
                "event_count": len(events),
                "first_event": events[0]["event"] if events else None,
                "last_event": last_event,
                "last_record_sha256": (
                    events[-1]["record_sha256"] if events else None
                ),
                "install_started": install_started,
                "state": (
                    "EMPTY" if not events
                    else "TERMINAL" if terminal
                    else "RECOVERY_REQUIRED"
                    if last_event == "RECOVERY_REQUIRED"
                    else "IN_PROGRESS"
                ),
                "requires_recovery": not terminal,
                "rollback_supported": install_started and not terminal,
            })
        except JournalError:
            raise
        except Exception as exc:
            raise JournalError(
                f"Falha ao inspecionar transação {entry.name}: {exc}"
            ) from exc
        finally:
            if transaction_handle is not None:
                close_handle(transaction_handle)

    return tuple(summaries)
