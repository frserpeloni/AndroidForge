"""Smoke test of the frozen SERMAX executable on a Windows runner."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: smoke_frozen_executable.py PATH_TO_SERMAX_EXE")
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    result = subprocess.run(
        [str(executable)],
        input="/sair\n",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        cwd=str(executable.parent),
    )
    output = result.stdout + "\n" + result.stderr
    if result.returncode != 0:
        print(output[-12000:], file=sys.stderr)
        raise SystemExit(f"SERMAX.exe exited with code {result.returncode}")
    if "Você:" not in output:
        print(output[-12000:], file=sys.stderr)
        raise SystemExit("SERMAX.exe did not reach the original terminal input prompt")
    print("Frozen executable smoke test passed: original terminal prompt reached and /sair handled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
