"""Equipe SERMAX para desenvolvimento controlado da SERMAX Platform."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sermax_dev_team import DevelopmentTeam
from sermax_groq_backend import GroqChatBackend
from sermax_workspace import TestRunner, WorkspaceAdapter, WorkspaceError


class PlatformWorkspaceAdapter(WorkspaceAdapter):
    """Permite alterações somente no backend Python, launcher e testes Python."""

    ALLOWED_ROOT_FILES = {
        "sermax_platform_launcher.py",
        "INTEGRACAO-ESTADO.md",
        "README.md",
    }

    def _resolve(self, relative: str | Path, *, allow_missing: bool = False) -> Path:
        raw = str(relative).replace("\\", "/")
        parts = raw.split("/")
        allowed = (
            (len(parts) == 2 and parts[0] == "backend" and parts[1].endswith(".py"))
            or (len(parts) == 2 and parts[0] == "tests" and parts[1].endswith(".py"))
            or (len(parts) == 1 and parts[0] in self.ALLOWED_ROOT_FILES)
        )
        if not allowed:
            raise WorkspaceError(
                "Fora do escopo inicial: somente backend/*.py, tests/*.py, "
                "sermax_platform_launcher.py, INTEGRACAO-ESTADO.md e README.md."
            )
        return super()._resolve(relative, allow_missing=allow_missing)


CONTEXT_FILES = (
    "backend/server.py",
    "backend/instance_lock.py",
    "backend/windows_autostart.py",
    "backend/windows_stop.py",
    "sermax_platform_launcher.py",
    "tests/test_platform_launcher.py",
    "tests/test_platform_windows_stop.py",
    "backend/test_api.py",
    "backend/test_core_session_contract.py",
    "backend/test_core_stream_integration.py",
    "INTEGRACAO-ESTADO.md",
    "ARQUITETURA-SERVIDOR-CENTRAL-E-CLIENTES-2026-11-20.md",
)


def collect_code_context(project_root: Path) -> str:
    sections = []
    remaining = 6_000
    for relative in CONTEXT_FILES:
        path = project_root / relative
        if not path.is_file() or path.stat().st_size > 1_000_000 or remaining <= 0:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        excerpt = content[: min(900, remaining)]
        section = f"\n--- ARQUIVO: {relative} ---\n{excerpt}"
        sections.append(section)
        remaining -= len(section)
    return "\n".join(sections)


def main() -> int:
    objective = os.environ.get("SERMAX_DEV_TASK", "").strip()
    if not objective:
        print("SERMAX_DEV_TASK vazio.", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parents[1] / "SERMAX-Platform"
    if not project_root.is_dir():
        print("SERMAX-Platform ausente no checkout.", file=sys.stderr)
        return 2

    workspace = PlatformWorkspaceAdapter(project_root)
    test_runner = TestRunner(workspace, timeout_seconds=300, isolate_as_nobody=True)
    backend = GroqChatBackend(max_retries=1)
    evidence = (
        "AMBIENTE: GitHub Actions, checkout isolado em SERMAX-Platform. "
        "ESCOPO AUTORIZADO NESTA FASE: backend Python, launcher Python e testes Python. "
        "Arquivos permitidos: backend/*.py, tests/*.py, sermax_platform_launcher.py, "
        "INTEGRACAO-ESTADO.md e README.md. O validador bloqueia os demais caminhos. "
        "A proposta terá no máximo três arquivos e exige unittest. "
        "O TestRunner executa unittest em SERMAX-Platform/tests e compileall, "
        "em sandbox descartável. Falha em teste provoca rollback. "
        "Não altere frontend (HTML, JS, CSS), package.json, installer, workflows, "
        "SERMAX-Windows, terminal original, memória, credenciais, backups, "
        "SERMAX Control ou Drive Connect. Não acesse C:\\SERMAX nem qualquer instalação local. "
        "Não faça merge nem altere main. Identifique fatos, lacunas e riscos com base "
        "no código fornecido. Não afirme homologação Windows que o CI Linux não prova. "
        "CONTEXTO DE CÓDIGO REAL:\n" + collect_code_context(project_root)
    )
    team = DevelopmentTeam(
        Path(tempfile.gettempdir()) / "sermax-platform-development-team.sqlite3",
        model_call=backend,
        max_attempts=3,
        workspace_adapter=workspace,
        test_runner=test_runner,
    )
    task_id = team.enqueue(objective, evidence=evidence)
    print(f"Tarefa SERMAX Platform registrada: {task_id}")
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
