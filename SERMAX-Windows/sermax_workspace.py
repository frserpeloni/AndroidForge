"""Acesso restrito ao workspace de desenvolvimento do SERMAX.

Este adaptador não acessa C:\\SERMAX, memórias pessoais, .git ou caminhos externos.
Os testes são executados por comandos permitidos, sem shell arbitrário.
"""
from __future__ import annotations

import difflib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROTECTED_NAMES = {
    ".git",
    "memoria_sermax.json",
    "memoria_neural_pestinha.json",
    ".sermax_dev_backups",
}
MAX_FILE_BYTES = 1_000_000
MAX_OUTPUT_CHARS = 30_000
ALLOWED_TESTS = {
    "unittest": (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
    "compileall": (sys.executable, "-m", "compileall", "-q", "."),
}


class WorkspaceError(ValueError):
    """Operação fora do escopo autorizado."""


class WorkspaceAdapter:
    def __init__(self, root: str | Path):
        candidate = Path(root).expanduser().resolve(strict=True)
        if not candidate.is_dir():
            raise WorkspaceError("A raiz do workspace precisa ser uma pasta existente.")
        if candidate == Path(candidate.anchor):
            raise WorkspaceError("A raiz do workspace não pode ser a raiz do disco.")
        self.root = candidate
        self.backup_root = self.root / ".sermax_dev_backups"

    def _resolve(self, relative: str | Path, *, allow_missing: bool = False) -> Path:
        rel = Path(relative)
        if rel.is_absolute() or not rel.parts or any(p in {"", ".", ".."} for p in rel.parts):
            raise WorkspaceError("Caminho relativo inválido.")
        if any(part.lower() in PROTECTED_NAMES for part in rel.parts):
            raise WorkspaceError("Caminho protegido.")
        target = self.root.joinpath(rel)
        # Resolve symlinks existentes, inclusive em componentes intermediários.
        resolved = target.resolve(strict=not allow_missing)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("O caminho escapa do workspace.") from exc
        if resolved == self.root:
            raise WorkspaceError("A raiz não é um arquivo válido.")
        if target.exists() and target.is_symlink():
            raise WorkspaceError("Links simbólicos não são aceitos.")
        return resolved

    def read_text(self, relative: str | Path) -> str:
        path = self._resolve(relative)
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError("Arquivo ausente, inválido ou acima do limite.")
        return path.read_text(encoding="utf-8")

    def preview(self, relative: str | Path, new_text: str) -> str:
        if not isinstance(new_text, str) or len(new_text.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError("Conteúdo inválido ou acima do limite.")
        path = self._resolve(relative, allow_missing=True)
        old = path.read_text(encoding="utf-8") if path.is_file() else ""
        return "".join(difflib.unified_diff(
            old.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=str(relative), tofile=str(relative) + " (proposto)",
        ))

    def write_text(self, relative: str | Path, new_text: str) -> Path:
        if not isinstance(new_text, str) or len(new_text.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError("Conteúdo inválido ou acima do limite.")
        path = self._resolve(relative, allow_missing=True)
        if path.exists() and not path.is_file():
            raise WorkspaceError("O destino não é um arquivo.")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup = self.backup_root / Path(relative)
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(path.read_bytes())
        # Escrita atômica no mesmo volume.
        fd, temp_name = tempfile.mkstemp(prefix=".sermax-write-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(new_text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path


class TestRunner:
    def __init__(self, workspace: WorkspaceAdapter, *, timeout_seconds: int = 120):
        self.workspace = workspace
        self.timeout_seconds = max(1, min(int(timeout_seconds), 600))

    def run(self, suite: str) -> dict:
        if suite not in ALLOWED_TESTS:
            raise WorkspaceError("Conjunto de testes não autorizado.")
        command = ALLOWED_TESTS[suite]
        try:
            result = subprocess.run(
                command,
                cwd=self.workspace.root,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
            )
            output = result.stdout[-MAX_OUTPUT_CHARS:]
            return {
                "suite": suite,
                "status": "passed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "output": output,
                "truncated": len(result.stdout) > MAX_OUTPUT_CHARS,
            }
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return {
                "suite": suite, "status": "timeout", "returncode": None,
                "output": str(output)[-MAX_OUTPUT_CHARS:], "truncated": True,
            }
