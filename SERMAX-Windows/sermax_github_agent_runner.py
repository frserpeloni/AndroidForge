"""Executa uma tarefa pontual da equipe SERMAX no GitHub Actions."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sermax_dev_team import DevelopmentTeam
from sermax_groq_backend import GroqChatBackend
from sermax_workspace import TestRunner, WorkspaceAdapter

WINDOWS_CONTEXT_FILES = (
    "sermax_core.py",
    "sermax_jarvis_adapter.py",
    "sermax_pestinha_adapter.py",
    "sermax_dev_team.py",
    "sermax_workspace.py",
    "sermax_dev_proposal.py",
)
PLATFORM_CONTEXT_FILES = (
    "backend/server.py",
    "backend/test_api.py",
)


def collect_code_context(project_root: Path) -> str:
    """Anexa trechos reais e limitados dos arquivos relevantes ao contexto dos papéis."""
    sections = []
    is_platform_workspace = (project_root / "backend" / "server.py").is_file()
    remaining = 4_200 if is_platform_workspace else 3_000
    context_files = PLATFORM_CONTEXT_FILES if is_platform_workspace else WINDOWS_CONTEXT_FILES
    for relative in context_files:
        path = project_root / relative
        if not path.is_file() or path.stat().st_size > 1_000_000 or remaining <= 0:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if relative == "backend/server.py":
            lines = content.splitlines()
            middleware_at = next(
                (index for index, line in enumerate(lines)
                 if "async def local_origin_guard" in line),
                None,
            )
            excerpts = ["\\n".join(lines[:24])]
            if middleware_at is not None:
                excerpts.append(
                    "\\n".join(lines[max(0, middleware_at - 2):middleware_at + 20])
                )
            excerpt = "\\n...\\n".join(excerpts)
        elif relative == "backend/test_api.py":
            lines = content.splitlines()
            excerpts = ["\\n".join(lines[:62])]
            if len(lines) > 245:
                excerpts.append("\\n".join(lines[248:260]))
            excerpt = "\\n...\\n".join(excerpts)
        else:
            excerpt = content[: min(650, remaining)]
        section = f"\\n--- ARQUIVO: {relative} ---\\n{excerpt}"
        sections.append(section)
        remaining -= len(section)
    return "\n".join(sections)


def main() -> int:
    objective = os.environ.get("SERMAX_DEV_TASK", "").strip()
    if not objective:
        print("SERMAX_DEV_TASK vazio.", file=sys.stderr)
        return 2

    default_root = Path(__file__).resolve().parent
    workspace_setting = os.environ.get("SERMAX_DEV_WORKSPACE", "").strip()
    workspace_root = Path(workspace_setting) if workspace_setting else default_root
    if not workspace_root.is_absolute():
        workspace_root = (default_root / workspace_root).resolve()
    else:
        workspace_root = workspace_root.resolve()
    if not workspace_root.is_dir():
        print(f"Workspace SERMAX inexistente: {workspace_root}", file=sys.stderr)
        return 2

    workspace = WorkspaceAdapter(workspace_root)
    test_runner = TestRunner(workspace, timeout_seconds=300, isolate_as_nobody=True)
    backend = GroqChatBackend()
    code_context = collect_code_context(workspace_root)
    evidence = (
        "Ambiente: GitHub Actions. "
        f"Workspace isolado: {workspace_root.name}. "
        "Não altere memórias, infraestrutura dos agentes, workflows, credenciais, "
        "configurações de permissões ou arquivos fora do escopo. "
        "Propostas aceitas: somente .py e .md do produto. Toda proposta exige unittest. "
        "O Programador terá a proposta validada antes de ser aplicada. "
        "O executor roda os testes e faz rollback se algum falhar. "
        "O Testador deve emitir JSON PASS/FAIL com evidência real.\n"
        "CONTEXTO DE CÓDIGO REAL:\n" + code_context
    )
    team = DevelopmentTeam(
        Path(tempfile.gettempdir()) / "sermax-development-team.sqlite3",
        model_call=backend,
        max_attempts=3,
        workspace_adapter=workspace,
        test_runner=test_runner,
    )
    task_id = team.enqueue(objective, evidence=evidence)
    print(f"Tarefa SERMAX registrada: {task_id}")
    team.run_next()
    result = team.get_task(task_id)
    print(f"Status: {result['status']}")
    if result["status"] != "completed":
        print(result.get("error", "Tarefa não concluída."), file=sys.stderr)
        return 1
    print(result["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
