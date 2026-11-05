"""Equipe única de desenvolvimento do SERMAX.

Este módulo é um supervisor externo ao executável SERMAX. Mantém uma fila SQLite
persistente e aciona papéis sob demanda, sempre com o mesmo backend de modelo.
Não concede acesso ao filesystem, Git ou shell: essas ferramentas exigem adaptadores
de workspace isolado, ainda não conectados.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROLES = {"analista", "pesquisador", "programador", "testador"}
STATUSES = {
    "queued", "running", "completed", "blocked", "failed"
}
MAX_PROMPT_CHARS = 12_000
MAX_RESULT_CHARS = 20_000

ROLE_INSTRUCTIONS = {
    "analista": (
        "Analise a tarefa e as evidências fornecidas. Separe fatos, hipóteses, "
        "riscos e critérios de aceitação. Não afirme que executou ações."
    ),
    "pesquisador": (
        "Pesquise somente nas fontes e evidências disponibilizadas no contexto. "
        "Indique lacunas e referências. Não invente consultas externas."
    ),
    "programador": (
        "Proponha uma alteração técnica pequena e verificável. Descreva arquivos, "
        "mudanças, riscos e testes. Não afirme que gravou arquivos."
    ),
    "testador": (
        "Defina os testes necessários e avalie somente resultados de execução "
        "fornecidos no contexto. Sem logs, marque como NÃO EXECUTADO."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DevelopmentTeam:
    """Fila persistente e execução sequencial de papéis sob demanda.

    model_call(role, prompt) deve chamar um único modelo compartilhado.
    Nenhum agente recebe uma instância de modelo própria.
    """

    def __init__(
        self,
        database: str | Path,
        model_call: Callable[[str, str], str] | None = None,
        *,
        max_attempts: int = 1,
    ):
        self.database = str(database)
        self.model_call = model_call
        self.max_attempts = max(1, min(int(max_attempts), 3))
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS development_tasks (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    roles TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS development_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES development_tasks(id)
                )
            """)
            db.execute("""
                UPDATE development_tasks
                SET status='queued', updated_at=?
                WHERE status='running'
            """, (_utc_now(),))

    def enqueue(
        self,
        objective: str,
        evidence: str = "",
        roles: Iterable[str] | None = None,
    ) -> str:
        objective = str(objective).strip()
        evidence = str(evidence).strip()
        selected = list(dict.fromkeys(roles or ("analista", "programador", "testador")))
        if not objective or len(objective) > MAX_PROMPT_CHARS:
            raise ValueError("Objetivo vazio ou acima do limite.")
        if len(evidence) > MAX_PROMPT_CHARS:
            raise ValueError("Evidências acima do limite.")
        if not selected or any(role not in ROLES for role in selected):
            raise ValueError("Papel inválido ou lista de papéis vazia.")
        task_id = uuid.uuid4().hex
        now = _utc_now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO development_tasks
                (id, objective, evidence, roles, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'queued', ?, ?)""",
                (task_id, objective, evidence, json.dumps(selected), now, now),
            )
            self._event(db, task_id, "supervisor", "queued", "Tarefa registrada.")
        return task_id

    @staticmethod
    def _event(db, task_id, role, status, detail):
        db.execute(
            """INSERT INTO development_events
            (task_id, role, status, detail, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (task_id, role, status, str(detail)[:MAX_RESULT_CHARS], _utc_now()),
        )

    def get_task(self, task_id: str) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM development_tasks WHERE id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError(task_id)
            item = dict(row)
            item["roles"] = json.loads(item["roles"])
            return item

    def events(self, task_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT role, status, detail, created_at
                FROM development_events WHERE task_id=? ORDER BY id""",
                (task_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def run_next(self) -> str | None:
        """Executa uma tarefa da fila. Papéis são ativados sequencialmente."""
        if self.model_call is None:
            raise RuntimeError("Backend de modelo compartilhado não configurado.")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT * FROM development_tasks
                WHERE status='queued' ORDER BY created_at, id LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            task_id = row["id"]
            db.execute(
                """UPDATE development_tasks SET status='running',
                attempts=attempts+1, updated_at=? WHERE id=?""",
                (_utc_now(), task_id),
            )
            self._event(db, task_id, "supervisor", "running", "Execução sequencial iniciada.")
        task = self.get_task(task_id)
        transcript = []
        try:
            for role in task["roles"]:
                prior = "\n\n".join(transcript)[-MAX_PROMPT_CHARS:]
                prompt = (
                    f"OBJETIVO:\n{task['objective']}\n\n"
                    f"EVIDÊNCIAS DISPONÍVEIS:\n{task['evidence'] or 'Nenhuma evidência anexada.'}\n\n"
                    f"RESULTADOS DOS PAPÉIS ANTERIORES:\n{prior or 'Nenhum.'}\n\n"
                    f"INSTRUÇÃO DO PAPEL ({role}):\n{ROLE_INSTRUCTIONS[role]}\n\n"
                    "Responda em português. Diferencie proposta de execução comprovada."
                )
                answer = self.model_call(role, prompt)
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError(f"O papel {role} retornou resposta vazia.")
                answer = answer[:MAX_RESULT_CHARS]
                transcript.append(f"[{role}]\n{answer}")
                with self._connect() as db:
                    self._event(db, task_id, role, "completed", answer)
            result = "\n\n".join(transcript)
            with self._connect() as db:
                db.execute(
                    """UPDATE development_tasks SET status='completed',
                    result=?, updated_at=? WHERE id=?""",
                    (result, _utc_now(), task_id),
                )
                self._event(
                    db, task_id, "supervisor", "completed",
                    "Papéis concluídos. Nenhuma edição de código foi executada por este módulo.",
                )
            return task_id
        except Exception as exc:
            with self._connect() as db:
                db.execute(
                    """UPDATE development_tasks SET status='failed',
                    error=?, updated_at=? WHERE id=?""",
                    (f"{type(exc).__name__}: {exc}"[:2000], _utc_now(), task_id),
                )
                self._event(db, task_id, "supervisor", "failed", str(exc))
            raise

    def start_background(self, poll_seconds: float = 2.0):
        """Inicia um único worker em segundo plano; não cria modelos por papel."""
        if self.model_call is None:
            raise RuntimeError("Backend de modelo compartilhado não configurado.")
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()

        def worker():
            while not self._stop.is_set():
                try:
                    processed = self.run_next()
                except Exception:
                    processed = None
                if processed is None:
                    self._stop.wait(max(0.2, min(float(poll_seconds), 30.0)))

        self._thread = threading.Thread(
            target=worker, name="SERMAX-DevelopmentTeam", daemon=True
        )
        self._thread.start()
        return True

    def stop_background(self, timeout: float = 5.0):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(max(0.1, min(float(timeout), 30.0)))
        return not bool(self._thread and self._thread.is_alive())
