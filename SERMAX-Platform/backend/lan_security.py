"""Pareamento local e credenciais persistentes de dispositivos.

A emissão de credenciais exige um verificador confiável, injetado pelo servidor.
Esse verificador deve consultar uma aprovação originada exclusivamente na UI
administrativa local. Nunca passe dados de aprovação recebidos do cliente.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

DEFAULT_DB_PATH = Path("data_dir/lan_security.db")
HASH_ITERATIONS = 200_000
SALT_LENGTH = 16
MAX_DEVICE_LENGTH = 128
MAX_TTL_SECONDS = 86_400
MAX_ATTEMPTS = 20
DEFAULT_CREDENTIAL_TTL_SECONDS = 7776000
MAX_CREDENTIAL_TTL_SECONDS = 31536000

ApprovalVerifier = Callable[[str, str], bool]


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


def complete_pairing(
    device: str,
    code: str,
    *,
    approval_verifier: ApprovalVerifier,
    credential_ttl_seconds: int = DEFAULT_CREDENTIAL_TTL_SECONDS,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> str | None:
    """Emite credencial após confirmação por verificador confiável do servidor.

    approval_verifier deve ser uma função interna do servidor, ligada ao estado
    de aprovação produzido pela UI administrativa local. Nunca aceite callback,
    booleano ou resultado de aprovação enviado em uma requisição remota.

    O chamador entrega o segredo ao dispositivo por canal protegido. O servidor
    armazena somente o hash da credencial.
    """
    _validate_device(device)
    if not callable(approval_verifier):
        raise PermissionError("verificador de aprovação local do servidor é obrigatório")
    _validate_positive_int(credential_ttl_seconds, "credential_ttl_seconds", MAX_CREDENTIAL_TTL_SECONDS)
    if not isinstance(code, str) or not code or len(code) > 256:
        raise ValueError("code inválido")

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

            expected_device, expires_at, attempts_left = row
            if int(time.time()) >= expires_at or attempts_left <= 0:
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

            # O callback é injetado pelo servidor, nunca obtido do payload remoto.
            if approval_verifier(device, code) is not True:
                conn.rollback()
                raise PermissionError("pareamento ainda não aprovado na administração local")

            credential = secrets.token_urlsafe(32)
            digest, salt = _hash_credential(credential)
            now = int(time.time())
            conn.execute(
                """INSERT INTO device_credentials(device, credential_hash, salt, created_at, expires_at, revoked)
                   VALUES (?, ?, ?, ?, ?, 0)
                   ON CONFLICT(device) DO UPDATE SET
                     credential_hash=excluded.credential_hash,
                     salt=excluded.salt,
                     created_at=excluded.created_at,
                     expires_at=excluded.expires_at,
                     revoked=0""",
                (device, digest, salt, now, now + credential_ttl_seconds),
            )
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
    """Remove códigos de pareamento expirados ou esgotados."""
    with _connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "DELETE FROM device_pairings WHERE expires_at <= ? OR attempts_left <= 0",
                (int(time.time()),),
            )
            conn.commit()
            return cur.rowcount
        except Exception:
            conn.rollback()
            raise
