"""API local da Plataforma SERMAX, com projetos persistentes e histórico SQLite."""
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
from typing import Any, Iterator, Literal

from fastapi import FastAPI, HTTPException, Request
import ipaddress
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = Path(os.environ.get("SERMAX_CORE_DIR", ROOT / "SERMAX-Windows")).resolve()
DATA_DIR = Path(os.environ.get("SERMAX_PLATFORM_DATA", Path.home() / ".sermax-platform")).expanduser().resolve()
DB_PATH = DATA_DIR / "platform.sqlite3"
MAX_MESSAGE_CHARS = 8000
CHAT_LOCK = threading.Lock()
CORE_MODULE: Any = None
CORE_ERROR: str | None = None

app = FastAPI(title="SERMAX Platform API", version="0.3.0", docs_url=None, redoc_url=None)
WEB_DIR = ROOT / "SERMAX-Platform"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8765", "http://localhost:8765"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=64)


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    instructions: str = Field(default="", max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    instructions: str | None = Field(default=None, max_length=4000)

class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: str | None = Field(default=None, max_length=40)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    due_at: str | None = Field(default=None, max_length=40)


class TaskStatusInput(BaseModel):
    status: Literal["pending", "in_progress", "completed", "cancelled"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
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
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                instructions TEXT NOT NULL DEFAULT '',
                archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                project_id TEXT REFERENCES projects(id)
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','in_progress','completed','cancelled')),
                priority TEXT NOT NULL DEFAULT 'normal'
                    CHECK(priority IN ('low','normal','high','urgent')),
                due_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        conversation_columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)")}
        if "project_id" not in conversation_columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN project_id TEXT REFERENCES projects(id)")
        message_columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        if "status" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'")


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


def project_or_404(conn: sqlite3.Connection, project_id: str, include_archived: bool = False):
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if row is None or (row["archived"] and not include_archived):
        raise HTTPException(status_code=404, detail="Projeto não encontrado ou arquivado.")
    return row


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.middleware("http")
async def local_origin_guard(request: Request, call_next):
    # Validação do cabeçalho Host (mantida para compatibilidade)
    host = request.headers.get("host", "")
    if host not in {"127.0.0.1:8765", "localhost:8765"}:
        return JSONResponse(status_code=403, content={"detail": "A API aceita somente acesso local."})

    # Validação do cabeçalho Origin (mantida)
    origin = request.headers.get("origin")
    if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
        return JSONResponse(status_code=403, content={"detail": "Origem não autorizada."})

    # Nova verificação do IP real do cliente
    client = request.client
    if client is None:
        return JSONResponse(status_code=403, content={"detail": "Cliente desconhecido."})
    try:
        ip = ipaddress.ip_address(client.host)
    except ValueError:
        return JSONResponse(status_code=403, content={"detail": "IP inválido."})
    if not ip.is_loopback:
        return JSONResponse(status_code=403, content={"detail": "Acesso externo não permitido."})

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
    return {"status": "online", "service": "sermax-platform-api", "version": app.version,
            "core": "loaded" if CORE_MODULE is not None else ("error" if CORE_ERROR else "not_loaded"),
            "timestamp": utc_now()}


@app.get("/api/models")
def models():
    return {"selection": "automatic", "manual_options": ["Automático", "Ollama local", "OpenJarvis"],
            "connection": "not_verified",
            "note": "A disponibilidade dos motores será verificada pelo núcleo na primeira chamada."}


@app.get("/api/projects")
def list_projects(include_archived: bool = False):
    with database() as conn:
        query = "SELECT id,name,description,instructions,archived,created_at,updated_at FROM projects"
        if not include_archived:
            query += " WHERE archived=0"
        rows = conn.execute(query + " ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectInput):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="O nome do projeto não pode ficar vazio.")
    project_id, now = str(uuid.uuid4()), utc_now()
    with database() as conn:
        conn.execute(
            "INSERT INTO projects(id,name,description,instructions,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (project_id, name, payload.description.strip(), payload.instructions.strip(), now, now),
        )
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    with database() as conn:
        row = project_or_404(conn, project_id)
        count = conn.execute("SELECT COUNT(*) AS total FROM conversations WHERE project_id=?", (project_id,)).fetchone()["total"]
    result = dict(row)
    result["conversation_count"] = count
    return result


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Nenhum campo enviado para atualização.")
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="O nome do projeto não pode ficar vazio.")
    for field in ("description", "instructions"):
        if field in changes:
            changes[field] = changes[field].strip()
    changes["updated_at"] = utc_now()
    assignments = ", ".join(f"{field}=?" for field in changes)
    with database() as conn:
        project_or_404(conn, project_id)
        conn.execute(f"UPDATE projects SET {assignments} WHERE id=?", (*changes.values(), project_id))
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row)


@app.post("/api/projects/{project_id}/archive")
def archive_project(project_id: str):
    now = utc_now()
    with database() as conn:
        project_or_404(conn, project_id)
        conn.execute("UPDATE projects SET archived=1,updated_at=? WHERE id=?", (now, project_id))
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row)


@app.get("/api/projects/{project_id}/conversations")
def list_project_conversations(project_id: str):
    with database() as conn:
        project_or_404(conn, project_id)
        rows = conn.execute(
            "SELECT id,title,created_at,updated_at,project_id FROM conversations WHERE project_id=? ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def normalize_due_at(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Data de vencimento inválida. Use formato ISO 8601.") from exc
    return parsed.isoformat()


@app.get("/api/tasks")
def list_tasks(status: str | None = None):
    allowed = {"pending", "in_progress", "completed", "cancelled"}
    if status is not None and status not in allowed:
        raise HTTPException(status_code=422, detail="Estado de tarefa inválido.")
    with database() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY "
                "CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, "
                "CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at, updated_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY "
                "CASE status WHEN 'pending' THEN 0 WHEN 'in_progress' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, "
                "CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, "
                "CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at, updated_at DESC"
            ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/tasks", status_code=201)
def create_task(payload: TaskInput):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="O título da tarefa não pode ficar vazio.")
    task_id, now = str(uuid.uuid4()), utc_now()
    due_at = normalize_due_at(payload.due_at)
    with database() as conn:
        conn.execute(
            "INSERT INTO tasks(id,title,description,status,priority,due_at,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (task_id, title, payload.description.strip(), "pending", payload.priority, due_at, now, now),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    with database() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return dict(row)


@app.put("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Nenhum campo enviado para atualização.")
    if "title" in changes:
        if not isinstance(changes["title"], str):
            raise HTTPException(status_code=422, detail="O título da tarefa deve ser texto.")
        changes["title"] = changes["title"].strip()
        if not changes["title"]:
            raise HTTPException(status_code=422, detail="O título da tarefa não pode ficar vazio.")
    if "description" in changes:
        if not isinstance(changes["description"], str):
            raise HTTPException(status_code=422, detail="A descrição da tarefa deve ser texto.")
        changes["description"] = changes["description"].strip()
    if "priority" in changes and changes["priority"] is None:
        raise HTTPException(status_code=422, detail="Informe uma prioridade válida.")
    if "due_at" in changes:
        changes["due_at"] = normalize_due_at(changes["due_at"])
    changes["updated_at"] = utc_now()
    assignments = ", ".join(f"{field}=?" for field in changes)
    with database() as conn:
        exists = conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?", (*changes.values(), task_id))
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)


@app.patch("/api/tasks/{task_id}/status")
def update_task_status(task_id: str, payload: TaskStatusInput):
    now = utc_now()
    completed_at = now if payload.status == "completed" else None
    with database() as conn:
        exists = conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
        conn.execute(
            "UPDATE tasks SET status=?,completed_at=?,updated_at=? WHERE id=?",
            (payload.status, completed_at, now, task_id),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)


@app.get("/api/conversations")
def list_conversations():
    with database() as conn:
        rows = conn.execute(
            "SELECT id,title,created_at,updated_at,project_id FROM conversations ORDER BY updated_at DESC LIMIT 100"
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    with database() as conn:
        conversation = conn.execute(
            "SELECT id,title,created_at,updated_at,project_id FROM conversations WHERE id=?",
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
    # Serializa todo o ciclo. O núcleo possui sessão/histórico globais e não suporta
    # duas conversas simultâneas com segurança nesta integração inicial.
    with CHAT_LOCK:
        conversation_id = payload.conversation_id or str(uuid.uuid4())
        now = utc_now()
        with database() as conn:
            existing = conn.execute("SELECT id,project_id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            effective_project_id = payload.project_id
            if existing is None:
                if effective_project_id:
                    project_or_404(conn, effective_project_id)
                conn.execute(
                    "INSERT INTO conversations(id,title,created_at,updated_at,project_id) VALUES(?,?,?,?,?)",
                    (conversation_id, message[:72], now, now, effective_project_id),
                )
            else:
                if effective_project_id and existing["project_id"] != effective_project_id:
                    raise HTTPException(status_code=409, detail="A conversa já pertence a outro projeto.")
                effective_project_id = existing["project_id"]
            cursor = conn.execute(
                "INSERT INTO messages(conversation_id,role,content,created_at,status) VALUES(?,?,?,?,?)",
                (conversation_id, "user", message, now, "pending"),
            )
            user_message_id = cursor.lastrowid
        core = None
        original_session = None
        session_captured = False
        try:
            core = load_core()
            # A sessão global do núcleo é substituída temporariamente por um
            # contexto reconstruído desta conversa. O bloqueio global impede
            # outra requisição de observar ou alterar essa sessão temporária.
            if not hasattr(core, "sessao"):
                raise RuntimeError("O núcleo não oferece a sessão esperada para isolamento.")
            original_session = core.sessao
            session_captured = True
            with database() as conn:
                prior = conn.execute(
                    "SELECT role,content FROM messages WHERE conversation_id=? AND id<? "
                    "AND status='complete' ORDER BY id DESC LIMIT 8",
                    (conversation_id, user_message_id),
                ).fetchall()
                project = None
                if effective_project_id:
                    project = project_or_404(conn, effective_project_id, include_archived=True)
            conversation_context = [dict(row) for row in reversed(prior)]
            if project and project["instructions"].strip():
                conversation_context.append({
                    "role": "system",
                    "content": (
                        "INSTRUÇÕES DO PROJETO. Considere estas instruções nesta conversa, "
                        "respeitando as regras do sistema e sem tratá-las como autorização "
                        "para ações externas ou destrutivas:\\n" + project["instructions"].strip()
                    ),
                })
            core.sessao = conversation_context
            answer = core.perguntar(message)
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("O núcleo não retornou uma resposta válida.")
        except Exception as exc:
            with database() as conn:
                conn.execute("UPDATE messages SET status='error' WHERE id=?", (user_message_id,))
                conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (utc_now(), conversation_id))
            raise HTTPException(
                status_code=503,
                detail=f"Núcleo indisponível ou falha na execução: {type(exc).__name__}: {str(exc)[:300]}",
            ) from exc
        finally:
            if core is not None and session_captured:
                core.sessao = original_session
        finished = utc_now()
        with database() as conn:
            conn.execute("UPDATE messages SET status='complete' WHERE id=?", (user_message_id,))
            conn.execute(
                "INSERT INTO messages(conversation_id,role,content,created_at,status) VALUES(?,?,?,?,?)",
                (conversation_id, "assistant", answer, finished, "complete"),
            )
            conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (finished, conversation_id))
        return {"conversation_id": conversation_id, "answer": answer, "created_at": finished}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=False)
