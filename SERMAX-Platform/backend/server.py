"""API local da Plataforma SERMAX.

Executa em loopback. Carrega o núcleo existente sob bloqueio global para
preservar a sessão compartilhada e não permitir chamadas concorrentes.
"""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = Path(os.environ.get("SERMAX_CORE_DIR", ROOT / "SERMAX-Windows")).resolve()
DATA_DIR = Path(os.environ.get("SERMAX_PLATFORM_DATA", Path.home() / ".sermax-platform")).expanduser().resolve()
DB_PATH = DATA_DIR / "platform.sqlite3"
MAX_MESSAGE_CHARS = 8000
CORE_LOCK = threading.Lock()
CORE_MODULE: Any = None
CORE_ERROR: str | None = None

app = FastAPI(title="SERMAX Platform API", version="0.2.0", docs_url=None, redoc_url=None)
WEB_DIR = ROOT / "SERMAX-Platform"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8765", "http://localhost:8765"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: str | None = Field(default=None, max_length=64)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    """Abre uma conexão por operação e garante commit/rollback e fechamento."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    with database() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'complete'
                    CHECK(status IN ('pending','complete','error'))
            )
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        if "status" not in columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'"
            )


def load_core():
    global CORE_MODULE, CORE_ERROR
    if CORE_MODULE is not None:
        return CORE_MODULE
    if CORE_ERROR:
        raise RuntimeError(CORE_ERROR)
    core_file = CORE_DIR / "sermax_core.py"
    if not core_file.is_file():
        CORE_ERROR = f"Núcleo não encontrado em {core_file}"
        raise RuntimeError(CORE_ERROR)
    if str(CORE_DIR) not in sys.path:
        sys.path.insert(0, str(CORE_DIR))
    try:
        CORE_MODULE = importlib.import_module("sermax_core")
    except Exception as exc:
        CORE_ERROR = f"Falha ao carregar núcleo: {type(exc).__name__}: {str(exc)[:300]}"
        raise RuntimeError(CORE_ERROR) from exc
    return CORE_MODULE


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.middleware("http")
async def local_origin_guard(request: Request, call_next):
    host = request.headers.get("host", "")
    if host not in {"127.0.0.1:8765", "localhost:8765"}:
        return JSONResponse(status_code=403, content={"detail": "A API aceita somente acesso local."})
    origin = request.headers.get("origin")
    if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
        return JSONResponse(status_code=403, content={"detail": "Origem não autorizada."})
    return await call_next(request)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/styles.css", include_in_schema=False)
def stylesheet():
    return FileResponse(WEB_DIR / "styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "service": "sermax-platform-api",
        "version": app.version,
        "core": "loaded" if CORE_MODULE is not None else ("error" if CORE_ERROR else "not_loaded"),
        "timestamp": utc_now(),
    }


@app.get("/api/models")
def models():
    return {
        "selection": "automatic",
        "manual_options": ["Automático", "Ollama local", "OpenJarvis"],
        "connection": "not_verified",
        "note": "A disponibilidade dos motores será verificada pelo núcleo na primeira chamada.",
    }


@app.get("/api/conversations")
def list_conversations():
    with database() as conn:
        rows = conn.execute(
            "SELECT id,title,created_at,updated_at FROM conversations ORDER BY updated_at DESC LIMIT 100"
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    with database() as conn:
        conversation = conn.execute(
            "SELECT id,title,created_at,updated_at FROM conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")
        messages = conn.execute(
            "SELECT role,content,created_at,status FROM messages WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    return {"conversation": dict(conversation), "messages": [dict(row) for row in messages]}


@app.post("/api/chat")
def chat(payload: ChatInput):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Mensagem vazia.")
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    now = utc_now()
    with database() as conn:
        exists = conn.execute("SELECT id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                (conversation_id, message[:72], now, now),
            )
        cursor = conn.execute(
            "INSERT INTO messages(conversation_id,role,content,created_at,status) VALUES(?,?,?,?,?)",
            (conversation_id, "user", message, now, "pending"),
        )
        user_message_id = cursor.lastrowid

    try:
        with CORE_LOCK:
            core = load_core()
            answer = core.perguntar(message)
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("O núcleo não retornou uma resposta válida.")
    except Exception as exc:
        with database() as conn:
            conn.execute(
                "UPDATE messages SET status='error' WHERE id=?",
                (user_message_id,),
            )
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (utc_now(), conversation_id),
            )
        raise HTTPException(
            status_code=503,
            detail=f"Núcleo indisponível ou falha na execução: {type(exc).__name__}: {str(exc)[:300]}",
        ) from exc

    finished = utc_now()
    with database() as conn:
        conn.execute(
            "UPDATE messages SET status='complete' WHERE id=?",
            (user_message_id,),
        )
        conn.execute(
            "INSERT INTO messages(conversation_id,role,content,created_at,status) VALUES(?,?,?,?,?)",
            (conversation_id, "assistant", answer, finished, "complete"),
        )
        conn.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?",
            (finished, conversation_id),
        )
    return {"conversation_id": conversation_id, "answer": answer, "created_at": finished}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=False)
