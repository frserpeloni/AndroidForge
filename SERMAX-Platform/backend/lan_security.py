"""Pareamento em duas fases e credenciais persistentes de dispositivos.

A aprovação local é registrada separadamente da reserva. A emissão da credencial
e o consumo da aprovação ocorrem na mesma transação SQLite. A camada HTTP deve
expor approve_pairing_locally exclusivamente à administração local do PC.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path("data_dir/lan_security.db")
HASH_ITERATIONS = 200_000
SALT_LENGTH = 16
MAX_DEVICE_LENGTH = 128
MAX_TTL_SECONDS = 86_400
MAX_ATTEMPTS = 20
DEFAULT_CREDENTIAL_TTL_SECONDS = 7_776_000
MAX_CREDENTIAL_TTL_SECONDS = 31_536_000
DEFAULT_RESERVATION_TTL_SECONDS = 180
MAX_RESERVATION_TTL_SECONDS = 900


def _validate_device(device: str) -> None:
    if not isinstance(device, str) or not device.strip() or len(device) > MAX_DEVICE_LENGTH:
        raise ValueError("device deve ser uma string não vazia de até 128 caracteres")


def _validate_positive_int(value: int, name: str, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} deve ser um inteiro entre 1 e {maximum}")


@contextmanager
def _connection(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_pairings (
                code TEXT PRIMARY KEY,
                device TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                attempts_left INTEGER NOT NULL CHECK (attempts_left >= 0)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_credentials (
                device TEXT PRIMARY KEY,
                credential_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1))
            )
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(device_credentials)")}
        if "expires_at" not in columns:
            conn.execute("ALTER TABLE device_credentials ADD COLUMN expires_at INTEGER NOT NULL DEFAULT 0")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pairing_reservations (
                reservation_id TEXT PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                device TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY(code) REFERENCES device_pairings(code) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS local_pairing_approvals (
                reservation_id TEXT PRIMARY KEY,
                device TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY(reservation_id) REFERENCES pairing_reservations(reservation_id) ON DELETE CASCADE
            )
        """)
        yield conn
    finally:
        conn.close()


def _hash_credential(credential: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    if salt is None:
        salt = secrets.token_bytes(SALT_LENGTH)
    digest = hashlib.pbkdf2_hmac("sha256", credential.encode("utf-8"), salt, HASH_ITERATIONS)
    return digest, salt


def generate_pairing_code(
    device: str,
    ttl_seconds: int = 300,
    max_attempts: int = 5,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> str:
    """Gera código temporário. Não aprova nem autoriza o dispositivo."""
    _validate_device(device)
    _validate_positive_int(ttl_seconds, "ttl_seconds", MAX_TTL_SECONDS)
    _validate_positive_int(max_attempts, "max_attempts", MAX_ATTEMPTS)
    code = secrets.token_urlsafe(24)
    expires_at = int(time.time()) + ttl_seconds
    with _connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO device_pairings(code, device, expires_at, attempts_left) VALUES (?, ?, ?, ?)",
                (code, device, expires_at, max_attempts),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return code


def reserve_pairing(
    device: str,
    code: str,
    *,
    reservation_ttl_seconds: int = DEFAULT_RESERVATION_TTL_SECONDS,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> str | None:
    """Reserva atomicamente um código válido para um único pedido de dispositivo.

    O identificador retornado não é uma credencial. A camada HTTP pode retorná-lo
    ao cliente para acompanhar o pedido, mas nunca deve aceitar aprovação remota.
    """
    _validate_device(device)
    _validate_positive_int(
        reservation_ttl_seconds, "reservation_ttl_seconds", MAX_RESERVATION_TTL_SECONDS
    )
    if not isinstance(code, str) or not code or len(code) > 256:
        raise ValueError("code inválido")

    now = int(time.time())
    with _connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT device, expires_at, attempts_left FROM device_pairings WHERE code = ?",
                (code,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            expected_device, code_expires, attempts_left = row
            if now >= code_expires or attempts_left <= 0:
                conn.execute("DELETE FROM device_pairings WHERE code = ?", (code,))
                conn.commit()
                return None
            if not hmac.compare_digest(expected_device.encode(), device.encode()):
                remaining = attempts_left - 1
                if remaining <= 0:
                    conn.execute("DELETE FROM device_pairings WHERE code = ?", (code,))
                else:
                    conn.execute(
                        "UPDATE device_pairings SET attempts_left = ? WHERE code = ?",
                        (remaining, code),
                    )
                conn.commit()
                return None

            active = conn.execute(
                "SELECT 1 FROM pairing_reservations WHERE code = ? AND expires_at > ?",
                (code, now),
            ).fetchone()
            if active:
                conn.rollback()
                return None
            expired_ids = [row[0] for row in conn.execute(
                "SELECT reservation_id FROM pairing_reservations WHERE code = ? AND expires_at <= ?",
                (code, now),
            )]
            for expired_id in expired_ids:
                conn.execute(
                    "DELETE FROM local_pairing_approvals WHERE reservation_id = ?",
                    (expired_id,),
                )
                conn.execute(
                    "DELETE FROM pairing_reservations WHERE reservation_id = ?",
                    (expired_id,),
                )
            reservation_id = secrets.token_urlsafe(32)
            conn.execute(
                """INSERT INTO pairing_reservations
                   (reservation_id, code, device, expires_at) VALUES (?, ?, ?, ?)""",
                (reservation_id, code, device, min(code_expires, now + reservation_ttl_seconds)),
            )
            conn.commit()
            return reservation_id
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise


def approve_pairing_locally(
    reservation_id: str,
    device: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> bool:
    """Registra aprovação administrativa local para uma reserva específica.

    Esta função é uma operação privilegiada. O servidor deve chamá-la somente
    após ação explícita na UI local do PC, nunca a partir de endpoint remoto.
    """
    _validate_device(device)
    if not isinstance(reservation_id, str) or not reservation_id or len(reservation_id) > 128:
        raise ValueError("reservation_id inválido")
    now = int(time.time())
    with _connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                """SELECT device, expires_at FROM pairing_reservations
                   WHERE reservation_id = ?""",
                (reservation_id,),
            ).fetchone()
            if row is None or row[0] != device or now >= row[1]:
                conn.rollback()
                return False
            conn.execute(
                """INSERT INTO local_pairing_approvals(reservation_id, device, expires_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(reservation_id) DO UPDATE SET
                     device=excluded.device, expires_at=excluded.expires_at""",
                (reservation_id, device, row[1]),
            )
            conn.commit()
            return True
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise


def finalize_pairing(
    reservation_id: str,
    device: str,
    *,
    credential_ttl_seconds: int = DEFAULT_CREDENTIAL_TTL_SECONDS,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> str | None:
    """Consome reserva e aprovação local atomicamente e emite uma credencial."""
    _validate_device(device)
    _validate_positive_int(
        credential_ttl_seconds, "credential_ttl_seconds", MAX_CREDENTIAL_TTL_SECONDS
    )
    if not isinstance(reservation_id, str) or not reservation_id or len(reservation_id) > 128:
        raise ValueError("reservation_id inválido")

    now = int(time.time())
    with _connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                """SELECT r.code, r.device, r.expires_at, p.expires_at, p.attempts_left,
                          a.device, a.expires_at
                   FROM pairing_reservations AS r
                   LEFT JOIN device_pairings AS p ON p.code = r.code
                   LEFT JOIN local_pairing_approvals AS a ON a.reservation_id = r.reservation_id
                   WHERE r.reservation_id = ?""",
                (reservation_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            code, reserved_device, reservation_expiry, code_expiry, attempts, approved_device, approval_expiry = row

            # Uma tentativa com outro identificador de dispositivo não deve
            # consumir a reserva legítima nem permitir negação de serviço.
            if reserved_device != device:
                conn.rollback()
                return None

            # Expiração é verificada mesmo quando ainda não existe aprovação.
            # LEFT JOIN permite limpar reservas vencidas sem exigir aprovação.
            if (
                code_expiry is None
                or attempts is None
                or now >= reservation_expiry
                or now >= code_expiry
                or attempts <= 0
            ):
                conn.execute(
                    "DELETE FROM local_pairing_approvals WHERE reservation_id = ?",
                    (reservation_id,),
                )
                conn.execute(
                    "DELETE FROM pairing_reservations WHERE reservation_id = ?",
                    (reservation_id,),
                )
                conn.commit()
                return None

            # Ausência ou incompatibilidade da aprovação não consome a reserva.
            # A aprovação local válida ainda pode ser registrada em seguida.
            if approved_device != device or approval_expiry is None:
                conn.rollback()
                return None
            if now >= approval_expiry:
                conn.execute(
                    "DELETE FROM local_pairing_approvals WHERE reservation_id = ?",
                    (reservation_id,),
                )
                conn.commit()
                return None

            credential = secrets.token_urlsafe(32)
            digest, salt = _hash_credential(credential)
            conn.execute(
                """INSERT INTO device_credentials
                   (device, credential_hash, salt, created_at, expires_at, revoked)
                   VALUES (?, ?, ?, ?, ?, 0)
                   ON CONFLICT(device) DO UPDATE SET
                     credential_hash=excluded.credential_hash,
                     salt=excluded.salt,
                     created_at=excluded.created_at,
                     expires_at=excluded.expires_at,
                     revoked=0""",
                (device, digest, salt, now, now + credential_ttl_seconds),
            )
            conn.execute("DELETE FROM local_pairing_approvals WHERE reservation_id = ?", (reservation_id,))
            conn.execute("DELETE FROM pairing_reservations WHERE reservation_id = ?", (reservation_id,))
            conn.execute("DELETE FROM device_pairings WHERE code = ?", (code,))
            conn.commit()
            return credential
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise


def authenticate(
    device: str,
    credential: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> bool:
    """Valida a credencial persistente sem consumi-la."""
    _validate_device(device)
    if not isinstance(credential, str) or not credential or len(credential) > 512:
        return False
    with _connection(db_path) as conn:
        row = conn.execute(
            "SELECT credential_hash, salt, revoked, expires_at FROM device_credentials WHERE device = ?",
            (device,),
        ).fetchone()
    if row is None:
        return False
    expected_hash, salt, revoked, expires_at = row
    if revoked or int(time.time()) >= expires_at:
        return False
    actual_hash, _ = _hash_credential(credential, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def revoke(device: str, db_path: Path | str = DEFAULT_DB_PATH) -> bool:
    """Revoga a credencial persistente do dispositivo, sem afetar outros."""
    _validate_device(device)
    with _connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE device_credentials SET revoked = 1 WHERE device = ? AND revoked = 0",
                (device,),
            )
            conn.commit()
            return cur.rowcount == 1
        except Exception:
            conn.rollback()
            raise


def cleanup_expired(db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """Remove códigos, reservas e aprovações expirados."""
    now = int(time.time())
    with _connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            expired_ids = [row[0] for row in conn.execute(
                "SELECT reservation_id FROM pairing_reservations WHERE expires_at <= ?",
                (now,),
            )]
            for expired_id in expired_ids:
                conn.execute(
                    "DELETE FROM local_pairing_approvals WHERE reservation_id = ?",
                    (expired_id,),
                )
                conn.execute(
                    "DELETE FROM pairing_reservations WHERE reservation_id = ?",
                    (expired_id,),
                )
            conn.execute(
                "DELETE FROM device_pairings WHERE expires_at <= ? OR attempts_left <= 0",
                (now,),
            )
            conn.commit()
            return len(expired_ids)
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise

def list_pending_pairings(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, object]]:
    """Lista pedidos ainda sem aprovação local, sem expor códigos ou credenciais."""
    now = int(time.time())
    with _connection(db_path) as conn:
        rows = conn.execute(
            """SELECT r.reservation_id, r.device, r.expires_at
               FROM pairing_reservations AS r
               JOIN device_pairings AS p ON p.code = r.code
               LEFT JOIN local_pairing_approvals AS a
                 ON a.reservation_id = r.reservation_id
               WHERE r.expires_at > ? AND p.expires_at > ?
                 AND p.attempts_left > 0 AND a.reservation_id IS NULL
               ORDER BY r.expires_at ASC""",
            (now, now),
        ).fetchall()
    return [
        {"reservation_id": row[0], "device": row[1], "expires_at": row[2]}
        for row in rows
    ]
