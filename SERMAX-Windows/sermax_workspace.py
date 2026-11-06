"""Acesso restrito ao workspace isolado de desenvolvimento do SERMAX.

Não acessa a instalação C:\\SERMAX, memórias pessoais, .git ou caminhos externos.
O TestRunner executa somente comandos previamente autorizados e limita tempo e saída.
"""
from __future__ import annotations

import difflib
import ntpath
import os
import subprocess
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROTECTED_NAMES = {
    ".git",
    "memoria_sermax.json",
    "memoria_neural_pestinha.json",
    ".sermax_dev_backups",
}
MAX_FILE_BYTES = 1_000_000
MAX_OUTPUT_CHARS = 30_000
MAX_OUTPUT_BYTES = MAX_OUTPUT_CHARS * 4
ALLOWED_TESTS = {
    "unittest": (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
    "compileall": (sys.executable, "-m", "compileall", "-q", "."),
}


class WorkspaceError(ValueError):
    """Operação fora do escopo autorizado."""


def _is_inside_windows_install(path: str) -> bool:
    candidate = ntpath.normcase(ntpath.abspath(path))
    protected = ntpath.normcase(ntpath.abspath(r"C:\SERMAX"))
    try:
        return ntpath.commonpath((candidate, protected)) == protected
    except ValueError:
        return False


class WorkspaceAdapter:
    def __init__(self, root: str | Path):
        candidate = Path(root).expanduser().resolve(strict=True)
        if not candidate.is_dir():
            raise WorkspaceError("A raiz do workspace precisa ser uma pasta existente.")
        if candidate == Path(candidate.anchor):
            raise WorkspaceError("A raiz do workspace não pode ser a raiz do disco.")
        if _is_inside_windows_install(str(candidate)):
            raise WorkspaceError("A instalação C:\\SERMAX está fora do escopo.")
        if (candidate / ".git").exists():
            raise WorkspaceError("Use um workspace isolado, fora da raiz do repositório Git.")
        self.root = candidate
        self.backup_root = self.root / ".sermax_dev_backups"

    def _resolve(self, relative: str | Path, *, allow_missing: bool = False) -> Path:
        raw = str(relative)
        # Também rejeita caminhos absolutos e traversal com sintaxe Windows em hosts POSIX.
        win = ntpath.normpath(raw)
        rel = Path(relative)
        if (rel.is_absolute() or ntpath.isabs(raw) or not rel.parts
                or any(p in {"", ".", ".."} for p in rel.parts)
                or any(p in PROTECTED_NAMES for p in (part.lower() for part in rel.parts))
                or any(p.lower() in PROTECTED_NAMES or p in {".", ".."} for p in win.replace("\\", "/").split("/"))):
            raise WorkspaceError("Caminho relativo inválido ou protegido.")
        target = self.root.joinpath(rel)
        resolved = target.resolve(strict=not allow_missing)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("O caminho escapa do workspace.") from exc
        if resolved == self.root:
            raise WorkspaceError("A raiz não é um arquivo válido.")
        # Rejeita links simbólicos em qualquer componente existente.
        current = self.root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise WorkspaceError("Links simbólicos não são aceitos.")
        return resolved

    def read_text(self, relative: str | Path) -> str:
        path = self._resolve(relative)
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError("Arquivo ausente, inválido ou acima do limite.")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkspaceError("O arquivo não contém texto UTF-8 válido.") from exc

    def preview(self, relative: str | Path, new_text: str) -> str:
        if not isinstance(new_text, str) or len(new_text.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError("Conteúdo inválido ou acima do limite.")
        path = self._resolve(relative, allow_missing=True)
        old = self.read_text(relative) if path.is_file() else ""
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
        # Revalida após criar diretórios para reduzir risco de redirecionamento por symlink.
        path = self._resolve(relative, allow_missing=True)
        if path.exists():
            if path.stat().st_size > MAX_FILE_BYTES:
                raise WorkspaceError("Arquivo original acima do limite de backup.")
            backup_dir = self.backup_root
            if backup_dir.is_symlink():
                raise WorkspaceError("Pasta de backup não pode ser link simbólico.")
            backup = backup_dir / Path(relative)
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup_dir.is_symlink() or any(p.is_symlink() for p in backup.parents if p != self.root):
                raise WorkspaceError("Caminho de backup contém link simbólico.")
            backup.write_bytes(path.read_bytes())
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
    def __init__(
        self,
        workspace: WorkspaceAdapter,
        *,
        timeout_seconds: int = 120,
        isolate_as_nobody: bool = False,
    ):
        self.workspace = workspace
        self.timeout_seconds = max(1, min(int(timeout_seconds), 600))
        self.isolate_as_nobody = bool(isolate_as_nobody)

    def _prepare_isolated_workspace(self, parent: str) -> Path:
        """Copia o workspace para sandbox temporário sem acesso de escrita ao checkout."""
        os.chmod(parent, 0o755)
        sandbox = Path(parent) / "workspace"
        shutil.copytree(
            self.workspace.root,
            sandbox,
            ignore=shutil.ignore_patterns(".sermax_dev_backups", "__pycache__", ".git"),
        )
        # O processo de testes roda como nobody, sem acesso ao ambiente/arquivos do runner.
        subprocess.run(
            ["sudo", "-n", "chown", "-R", "nobody:nogroup", str(sandbox)],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        return sandbox

    def run(self, suite: str) -> dict:
        if suite not in ALLOWED_TESTS:
            raise WorkspaceError("Conjunto de testes não autorizado.")
        command = ALLOWED_TESTS[suite]
        env = {
            key: value for key, value in os.environ.items()
            if key in {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
                       "HOME", "USERPROFILE", "PYTHONPATH", "SERMAX_JARVIS_PYTHON",
                       "SERMAX_ROOT"}
        }
        env["PYTHONIOENCODING"] = "utf-8"
        started = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="sermax-test-") as temporary:
            cwd = self.workspace.root
            if self.isolate_as_nobody:
                try:
                    cwd = self._prepare_isolated_workspace(temporary)
                except (OSError, subprocess.SubprocessError) as exc:
                    return {
                        "suite": suite, "status": "isolation_failed", "returncode": None,
                        "output": f"Falha ao preparar sandbox isolado: {type(exc).__name__}: {exc}"[:MAX_OUTPUT_CHARS],
                        "truncated": False,
                    }
                command = ["sudo", "-n", "-u", "nobody", "--", *command]
                env["HOME"] = "/tmp"
                env.pop("PYTHONPATH", None)
                env.pop("SERMAX_ROOT", None)
                env.pop("SERMAX_JARVIS_PYTHON", None)

            with tempfile.TemporaryFile() as output_file:
                try:
                    process = subprocess.Popen(
                        command, cwd=cwd, shell=False,
                        stdin=subprocess.DEVNULL, stdout=output_file,
                        stderr=subprocess.STDOUT, env=env,
                    )
                    status = "failed"
                    while process.poll() is None:
                        size = os.fstat(output_file.fileno()).st_size
                        if size > MAX_OUTPUT_BYTES:
                            process.kill()
                            process.wait()
                            status = "output_limit"
                            break
                        if time.monotonic() - started > self.timeout_seconds:
                            process.kill()
                            process.wait()
                            status = "timeout"
                            break
                        time.sleep(0.05)
                    output_size = os.fstat(output_file.fileno()).st_size
                    if status == "failed" and output_size > MAX_OUTPUT_BYTES:
                        status = "output_limit"
                    returncode = process.returncode
                    if status == "failed" and returncode == 0:
                        status = "passed"
                    output_file.seek(max(0, output_size - MAX_OUTPUT_BYTES))
                    raw = output_file.read(MAX_OUTPUT_BYTES)
                    output = raw.decode("utf-8", errors="replace")[-MAX_OUTPUT_CHARS:]
                    return {
                        "suite": suite, "status": status, "returncode": returncode,
                        "output": output, "truncated": output_size > MAX_OUTPUT_BYTES,
                    }
                except OSError as exc:
                    return {
                        "suite": suite, "status": "failed", "returncode": None,
                        "output": f"{type(exc).__name__}: {exc}"[:MAX_OUTPUT_CHARS],
                        "truncated": False,
                    }
