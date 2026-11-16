"""Executa uma tarefa pontual da equipe SERMAX no GitHub Actions."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sermax_dev_team import DevelopmentTeam
from sermax_groq_backend import GroqChatBackend
from sermax_workspace import TestRunner, WorkspaceAdapter

# Contexto direcionado à etapa autorizada do atualizador transacional.
# Os agentes recebem código real e testes relacionados à área privada _update.
CONTEXT_FILES = (
    ("sermax_windows_private_area.py", "def create_private_directory_component"),
    ("sermax_windows_private_area_acl_policy.py", "def validate_private_area_acl"),
    ("sermax_windows_acl_inspection.py", "def inspect_directory_acl"),
    ("sermax_windows_root.py", "def open_managed_directory_for_private_area"),
    ("sermax_windows_handle_inventory.py", "def inventory_directory_handle"),
    ("sermax_update_inventory_contract.py", "def classify_inventory"),
    ("tests/test_sermax_windows_private_area.py",
     "def test_rejects_component_outside_fixed_allowlist"),
    ("tests/test_sermax_windows_private_area_acl_policy.py",
     "def test_accepts_exact_protected_policy_and_empty_directory"),
    ("tests/test_sermax_windows_private_area_acl_policy_windows.py",
     "def test_reads_back_exact_protected_acl_from_same_retained_handle"),
    ("tests/test_sermax_windows_handle_inventory.py",
     "def test_hashes_file_from_stable_directory"),
)


def collect_code_context(project_root: Path) -> str:
    """Anexa trechos reais e limitados dos módulos e testes de _update."""
    sections = []
    remaining = 5_600
    for relative, marker in CONTEXT_FILES:
        path = project_root / relative
        if not path.is_file() or path.stat().st_size > 1_000_000 or remaining <= 0:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        start = next(
            (index for index, line in enumerate(lines) if marker in line),
            None,
        )
        if start is None:
            excerpt = "\n".join(lines)[:500]
        else:
            excerpt = "\n".join(lines[start:])[:520]
        section = f"\n--- ARQUIVO: {relative}, trecho {marker} ---\n{excerpt}"
        if len(section) > remaining:
            section = section[:remaining]
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
        "ESCOPO AUTORIZADO: próxima etapa de validação segura da área privada _update. "
        "Audite a abertura relativa por handle, identidade de volume/FileId, reparse "
        "points, ACL, enumeração, concorrência e falhas. "
        "Não acesse nem escreva em C:\\SERMAX. Não crie diretórios nem altere ACL "
        "fora de sandbox descartável. Não implemente staging, backup, journal, "
        "instalação ou rollback nesta etapa. "
        "Não altere workflows, infraestrutura dos agentes, credenciais, memórias, "
        "configurações, integrações Jarvis/Pestinha, terminal ou arquivos protegidos. "
        "Propostas aceitas: somente .py e .md do produto e testes relacionados. "
        "Toda proposta exige unittest. O executor roda os testes em sandbox isolada "
        "e faz rollback se algum falhar. O Testador deve emitir JSON PASS/FAIL com "
        "evidência real. Não alegue validação de acesso efetivo somente pela leitura "
        "da DACL. Se uma garantia depender de Windows x64 e não for testada no CI, "
        "registre a pendência e mantenha o fluxo bloqueado.\n"
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
