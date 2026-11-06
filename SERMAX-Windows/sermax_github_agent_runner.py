"""Executa uma tarefa pontual da equipe SERMAX no GitHub Actions."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sermax_dev_team import DevelopmentTeam
from sermax_groq_backend import GroqChatBackend
from sermax_workspace import TestRunner, WorkspaceAdapter


def main() -> int:
    objective = os.environ.get("SERMAX_DEV_TASK", "").strip()
    if not objective:
        print("SERMAX_DEV_TASK vazio.", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parent
    workspace = WorkspaceAdapter(project_root)
    test_runner = TestRunner(workspace, timeout_seconds=300)
    backend = GroqChatBackend()
    team = DevelopmentTeam(
        project_root / ".sermax_dev_state" / "team.sqlite3",
        model_call=backend,
        workspace_adapter=workspace,
        test_runner=test_runner,
    )
    task_id = team.enqueue(
        objective,
        evidence=(
            "Ambiente: GitHub Actions. Repositório SERMAX-Windows. "
            "A equipe trabalha somente neste workspace isolado. "
            "Não altere memórias pessoais, arquivos de instalação, segredos, "
            "workflows, configurações de permissões ou arquivos fora do escopo. "
            "O Programador deve propor arquivos relativos a esta pasta. "
            "O Testador deve avaliar os resultados reais fornecidos pelo executor."
        ),
        roles=("analista", "pesquisador", "programador", "testador"),
    )
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
