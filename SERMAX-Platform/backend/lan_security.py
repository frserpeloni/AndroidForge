"""Módulo de segurança LAN.

Este módulo fornece uma API simples para gerar códigos de pareamento, armazenar
hashes de credenciais, autenticar dispositivos e revogar credenciais.  O
armazenamento é feito em um banco SQLite localizado em
``data_dir/lan_security.db``.  A API é projetada para ser usada apenas
localmente, sem exposição de portas externas.

A implementação segue os requisitos da tarefa:

* Código de pareamento de uso único, com TTL (tempo de vida) e limite de
  tentativas.
* Hash de credencial usando PBKDF2-HMAC-SHA256 com salt aleatório.
* Autenticação que revoga a credencial após o primeiro uso bem-sucedido.
* Função de revogação explícita.
* Limpeza de registros expirados.
"""

from __future__ import annotations

import os
import sqlite3
import string
import secrets
import hashlib
import hmac
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

# Diretório onde o banco será criado (padrão: data_dir/lan_security.db)
DEFAULT_DB_PATH = Path("data_dir/lan_security.db")

# Parâmetros de hash
HASH_ITERATIONS = 200_000
HASH_ALGORITHM = "sha256"
SALT_LENGTH = 16

# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------

def _get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Retorna uma conexão SQLite, criando o banco e a tabela se necessário."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pairings (
            code TEXT PRIMARY KEY,
            device TEXT NOT NULL,
            credential_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            expires_at INTEGER NOT NULL,
            attempts_left INTEGER NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()
    return conn


def _hash_credential(credential: str, salt: bytes | None = None) -> Tuple[bytes, bytes]:
    """Retorna (hash, salt).  Se ``salt`` for ``None`` gera um salt aleatório."""
    if salt is None:
        salt = secrets.token_bytes(SALT_LENGTH)
    dk = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM, credential.encode("utf-8"), salt, HASH_ITERATIONS
    )
    return dk, salt


def _current_timestamp() -> int:
    return int(time.time())

# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def generate_pairing_code(
    device: str,
    ttl_seconds: int = 300,
    max_attempts: int = 5,
    credential: Optional[str] = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> str:
    """Gera um código de pareamento único.

    Parameters
    ----------
    device: Identificador do dispositivo que irá usar o código.
    ttl_seconds: Tempo de vida do código em segundos.
    max_attempts: Número máximo de tentativas de autenticação.
    credential: Credencial opcional.  Se ``None`` será gerada uma credencial
        aleatória e retornada junto com o código.
    db_path: Caminho do banco SQLite.

    Returns
    -------
    code: Código de pareamento (string).
    """
    if credential is None:
        # Gera credencial aleatória de 32 caracteres alfanuméricos
        credential = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
        )
    cred_hash, salt = _hash_credential(credential)
    expires_at = _current_timestamp() + ttl_seconds
    code = secrets.token_urlsafe(16)
    with _get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO pairings (code, device, credential_hash, salt, expires_at, attempts_left) VALUES (?, ?, ?, ?, ?, ?);",
            (code, device, cred_hash, salt, expires_at, max_attempts),
        )
        conn.commit()
    # O código é retornado; a credencial não é armazenada em texto puro.
    return code


def authenticate(
    device: str,
    code: str,
    credential: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> bool:
    """Tenta autenticar um dispositivo usando o código e a credencial.

    Se a autenticação for bem-sucedida, a credencial é revogada (removida do
    banco).  Se falhar, decrementa o contador de tentativas.
    """
    with _get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT credential_hash, salt, expires_at, attempts_left, revoked FROM pairings WHERE code = ? AND device = ?;",
            (code, device),
        )
        row = cur.fetchone()
        if row is None:
            return False
        cred_hash, salt, expires_at, attempts_left, revoked = row
        if revoked:
            return False
        if _current_timestamp() > expires_at:
            return False
        if attempts_left <= 0:
            return False
        # Verifica a credencial
        expected_hash, _ = _hash_credential(credential, salt)
        if hmac.compare_digest(expected_hash, cred_hash):
            # Revoga a credencial
            conn.execute("DELETE FROM pairings WHERE code = ?;", (code,))
            conn.commit()
            return True
        else:
            # Decrementa tentativas
            conn.execute(
                "UPDATE pairings SET attempts_left = attempts_left - 1 WHERE code = ?;",
                (code,),
            )
            conn.commit()
            return False


def revoke(device: str, code: str, db_path: Path | str = DEFAULT_DB_PATH) -> bool:
    """Revoga explicitamente um código de pareamento.

    Retorna ``True`` se o código foi revogado, ``False`` caso contrário.
    """
    with _get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT revoked FROM pairings WHERE code = ? AND device = ?;",
            (code, device),
        )
        row = cur.fetchone()
        if row is None:
            return False
        revoked = row[0]
        if revoked:
            return False
        conn.execute("DELETE FROM pairings WHERE code = ?;", (code,))
        conn.commit()
        return True


def cleanup_expired(db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """Remove registros expirados.

    Retorna o número de registros removidos.
    """
    now = _current_timestamp()
    with _get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM pairings WHERE expires_at <= ?;", (now,))
        conn.commit()
        return cur.rowcount

# ---------------------------------------------------------------------------
# Exemplo de uso (não executado em produção)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Exemplo rápido de geração e autenticação
    dev = "device-123"
    code = generate_pairing_code(dev, ttl_seconds=60, max_attempts=3, credential="secret123")
    print("Código gerado:", code)
    print("Autenticação bem-sucedida?", authenticate(dev, code, "secret123"))
    print("Tentativa subsequente (deveria falhar):", authenticate(dev, code, "secret123"))
