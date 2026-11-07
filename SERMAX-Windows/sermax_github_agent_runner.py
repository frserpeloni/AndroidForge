"""Executa uma tarefa pontual da equipe SERMAX no GitHub Actions."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sermax_dev_team import DevelopmentTeam
from sermax_groq_backend import GroqChatBackend
from sermax_workspace import TestRunner, WorkspaceAdapter

CONTEXT_FILES = (
    "sermax_core.py",
    "sermax_jarvis_adapter.py",
    "sermax_pestinha_adapter.py",
    "sermax_dev_team.py",
    "sermax_workspace.py",
    "sermax_dev_proposal.py",
)


def collect_code_context(project_root: Path) -> str:
    """Anexa trechos reais e limitados dos arquivos relevantes ao contexto dos papéis."""
    sections = []
    remaining = 3_000
    for relative in CONTEXT_FILES:
        path = project_root / relative
        if not path.is_file() or path.stat().st_size > 1_000_000 or remaining <= 0:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        excerpt = content[: min(650, remaining)]
        section = f"\n--- ARQUIVO: {relative} ---\n{excerpt}"
        sections.append(section)
        remaining -= len(section)
    return "\n".join(sections)


def main() -> int:
    objective = os.environ.get("SERMAX_DEV_TASK", "").strip()
    if not objective:
        print("SERMAX_DEV_TASK vazio.", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parent
    workspace = WorkspaceAdapter(project_root)
    test_runner = TestRunner(workspace, timeout_seconds=300, isolate_as_nobody=True)
    backend = GroqChatBackend()
    code_context = collect_code_context(project_root)
    evidence = (
        "Ambiente: GitHub Actions. Workspace isolado: SERMAX-Windows. "
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
