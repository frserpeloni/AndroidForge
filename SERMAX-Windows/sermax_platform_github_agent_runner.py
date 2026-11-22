"""Equipe SERMAX para desenvolvimento controlado da SERMAX Platform, com escopo LAN aprovado."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sermax_dev_team import DevelopmentTeam
from sermax_groq_backend import GroqChatBackend
from sermax_workspace import TestRunner, WorkspaceAdapter, WorkspaceError


class PlatformWorkspaceAdapter(WorkspaceAdapter):
    """Permite alterações no backend Python, exceto no servidor central protegido, launcher e testes."""

    ALLOWED_ROOT_FILES = {
        "sermax_platform_launcher.py",
        "INTEGRACAO-ESTADO.md",
        "README.md",
    }

    def _resolve(self, relative: str | Path, *, allow_missing: bool = False) -> Path:
        raw = str(relative).replace("\\", "/")
        parts = raw.split("/")
        allowed = (
            (len(parts) == 2 and parts[0] == "backend" and parts[1].endswith(".py")
             and parts[1] != "server.py")
            or (len(parts) == 2 and parts[0] == "tests" and parts[1].endswith(".py"))
            or (len(parts) == 1 and parts[0] in self.ALLOWED_ROOT_FILES)
        )
        if not allowed:
            raise WorkspaceError(
                "Fora do escopo: backend/server.py é somente leitura; são permitidos os demais "
                "backend/*.py, tests/*.py, sermax_platform_launcher.py, "
                "INTEGRACAO-ESTADO.md e README.md."
            )
        return super()._resolve(relative, allow_missing=allow_missing)


CONTEXT_FILES = (
    "backend/instance_lock.py",
    "backend/server.py",
    "backend/windows_autostart.py",
    "backend/windows_stop.py",
    "sermax_platform_launcher.py",
    "tests/test_instance_lock.py",
    "tests/test_platform_launcher.py",
    "tests/test_platform_windows_stop.py",
    "backend/test_api.py",
    "backend/test_core_session_contract.py",
    "backend/test_core_stream_integration.py",
)


def collect_code_context(project_root: Path) -> str:
    sections = []
    remaining = 3_500
    for relative in CONTEXT_FILES:
        path = project_root / relative
        if not path.is_file() or path.stat().st_size > 1_000_000 or remaining <= 0:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Arquivos de contrato crítico precisam chegar completos ao agente.
        # O limite anterior de 900 caracteres cortava a implementação de
        # instance_lock.py e induzia diagnósticos baseados em código parcial.
        file_limit = 1_800 if relative == "backend/instance_lock.py" else 900
        excerpt = content[: min(file_limit, remaining)]
        section = f"\n--- {relative} ---\n{excerpt}" 
        if len(excerpt) < len(content):
            section += "\n[ARQUIVO TRUNCADO PELO LIMITE DE CONTEXTO]"
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
    # O sandbox evita bytecode .pyc para permitir limpeza segura após testes isolados.
    # TestRunner restaura a propriedade do sandbox antes da limpeza temporária.
    test_runner = TestRunner(workspace, timeout_seconds=300, isolate_as_nobody=True)
    # Três tentativas permitem respeitar o Retry-After da Groq em HTTP 429.
    backend = GroqChatBackend(max_retries=3)
    evidence = (
        "GitHub Actions em checkout isolado. Escopo: backend Python, launcher Python "
        "e testes Python. Escrita permitida: backend/*.py EXCETO backend/server.py, "
        "tests/*.py, sermax_platform_launcher.py, INTEGRACAO-ESTADO.md e README.md. "
        "backend/server.py é o servidor central protegido, somente leitura. "
        "NUNCA inclua backend/server.py em files. Se a correção exigir esse arquivo, "
        "registre o bloqueio e escolha outro defeito independente ou encerre sem proposta. "
        "No máximo dois arquivos por proposta. Exija unittest. Toda alteração de "
        "comportamento deve incluir teste novo ou atualizado em tests/test_*.py. "
        "Nunca declare que adicionou teste se nenhum arquivo de teste estiver em files. "
        "Se o contexto de um arquivo estiver marcado como truncado, não infira código "
        "ausente: peça o arquivo completo ou escolha outro defeito com evidência completa. "
        "O TestRunner roda unittest e compileall em sandbox descartável; falha provoca rollback. "
        "Não altere frontend, instalador, workflows, SERMAX-Windows, Terminal, memória, "
        "backups, SERMAX Control ou Drive Connect. Não acesse C:\\SERMAX. "
        "Não faça merge nem altere main. CI Linux não comprova homologação Windows. "
        "Acesso LAN foi autorizado pelo operador conforme o desenho documentado. " 
        "Esta tarefa inicial está limitada ao módulo backend/lan_security.py e " 
        "tests/test_lan_security.py: implemente pareamento por código de uso único, " 
        "expiração, limites de tentativas, armazenamento de hash de credenciais, " 
        "autenticação por dispositivo e revogação, com testes positivos e negativos. " 
        "Não altere backend/server.py, launcher, bind, middleware, CORS, Host/Origin, " 
        "TLS ou firewall nesta etapa. Não abra portas nem exponha a API. "
        "Formato obrigatório da proposta do Programador: JSON puro com exatamente estas chaves: "
        '{"summary":"...","files":[{"path":"backend/arquivo.py","content":"..."}],'
        '"tests":["unittest"]}. A lista tests deve conter literalmente unittest.' 
        "Inclua os testes unittest correspondentes entre os arquivos propostos. "
        "Não retorne compileall como substituto de unittest. "
        "Baseie-se no código real abaixo e prefira uma correção pequena.\n"
        + collect_code_context(project_root)
    )
    team = DevelopmentTeam(
        Path(tempfile.gettempdir()) / "sermax-platform-development-team.sqlite3",
        model_call=backend,
        max_attempts=2,
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
