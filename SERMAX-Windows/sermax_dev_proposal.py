"""Validação e aplicação controlada de propostas do papel Programador."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from typing import Any

from sermax_workspace import MAX_FILE_BYTES, WorkspaceAdapter, WorkspaceError

MAX_PROPOSAL_BYTES = 2_000_000
MAX_FILES = 10
MAX_PATH_CHARS = 240
PROTECTED_BASENAMES = {
    "sermax_github_agent_runner.py", "sermax_groq_backend.py",
    "sermax_dev_team.py", "sermax_dev_proposal.py", "sermax_workspace.py",
    "sermax.spec", "memoria_sermax.json", "memoria_neural_pestinha.json",
}


class ProposalError(ValueError):
    """Proposta inválida ou fora do escopo."""


@dataclass(frozen=True)
class ProposedFile:
    path: str
    content: str


@dataclass(frozen=True)
class ValidatedProposal:
    summary: str
    files: tuple[ProposedFile, ...]
    tests: tuple[str, ...]


def _validate_development_path(path: str) -> None:
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    lowered = [part.casefold() for part in parts]
    if (
        normalized.startswith("/")
        or any(not part or part in {".", ".."} for part in parts)
        or any(part.startswith(".") for part in parts)
        or any(part in {".github", ".git", ".sermax_dev_backups", "sermax_terminal"} for part in lowered)
        or lowered[-1] in PROTECTED_BASENAMES
        or not lowered[-1].endswith((".py", ".md"))
    ):
        raise ProposalError(
            "Caminho fora do escopo: somente arquivos .py e .md do produto; "
            "infraestrutura, workflows, credenciais e memórias são protegidos."
        )


def parse_proposal(raw: str) -> ValidatedProposal:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_PROPOSAL_BYTES:
        raise ProposalError("Resposta do Programador ausente ou acima do limite.")
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProposalError("O Programador precisa retornar JSON válido.") from exc
    if not isinstance(data, dict) or set(data) != {"summary", "files", "tests"}:
        raise ProposalError("A proposta exige os campos summary, files e tests.")
    summary, files, tests = data["summary"], data["files"], data["tests"]
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 2000:
        raise ProposalError("Resumo inválido.")
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ProposalError("A proposta deve conter de 1 a 10 arquivos.")
    if (
        not isinstance(tests, list)
        or not tests
        or any(test not in {"unittest", "compileall"} for test in tests)
        or "unittest" not in tests
    ):
        raise ProposalError("A proposta precisa incluir a suíte unittest autorizada.")
    parsed, seen = [], set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "content"}:
            raise ProposalError("Cada arquivo exige path e content.")
        path, content = item["path"], item["content"]
        if not isinstance(path, str) or not path.strip() or len(path) > MAX_PATH_CHARS:
            raise ProposalError("Caminho inválido.")
        _validate_development_path(path)
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ProposalError("Conteúdo de arquivo inválido ou acima do limite.")
        normalized = path.replace("\\", "/").casefold()
        if normalized in seen:
            raise ProposalError("A proposta contém caminhos duplicados.")
        seen.add(normalized)
        parsed.append(ProposedFile(path, content))
    return ValidatedProposal(summary.strip(), tuple(parsed), tuple(dict.fromkeys(tests)))


def preview_proposal(workspace: WorkspaceAdapter, proposal: ValidatedProposal) -> list[dict]:
    previews = []
    for item in proposal.files:
        try:
            diff = workspace.preview(item.path, item.content)
        except WorkspaceError as exc:
            raise ProposalError(f"Arquivo fora do escopo: {item.path}") from exc
        previews.append({"path": item.path, "diff": diff})
    return previews


def apply_proposal(workspace: WorkspaceAdapter, proposal: ValidatedProposal) -> list[str]:
    preview_proposal(workspace, proposal)
    written = []
    for item in proposal.files:
        workspace.write_text(item.path, item.content)
        written.append(item.path)
    return written


def apply_and_test_proposal(workspace: WorkspaceAdapter, proposal: ValidatedProposal, test_runner):
    """Aplica proposta e testes como transação: falha restaura todos os arquivos."""
    preview_proposal(workspace, proposal)
    snapshots, backup_snapshots = {}, {}
    backup_root = workspace.backup_root
    for item in proposal.files:
        target = workspace._resolve(item.path, allow_missing=True)
        existed = target.is_file()
        snapshots[item.path] = (existed, target.read_bytes() if existed else None)
        backup = backup_root / item.path
        backup_snapshots[item.path] = (
            backup.is_file(), backup.read_bytes() if backup.is_file() else None
        )
    try:
        written = apply_proposal(workspace, proposal)
        results = [test_runner.run(suite) for suite in proposal.tests]
        if any(result.get("status") != "passed" for result in results):
            raise RuntimeError("Testes da proposta falharam.")
        return written, results
    except Exception:
        for relative, (existed, content) in snapshots.items():
            target = workspace._resolve(relative, allow_missing=True)
            if existed:
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix=".sermax-rollback-", dir=str(target.parent))
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp_name, target)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            elif target.exists():
                target.unlink()
        for relative, (existed, content) in backup_snapshots.items():
            backup = backup_root / relative
            if existed:
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(content)
            elif backup.exists():
                backup.unlink()
        raise
