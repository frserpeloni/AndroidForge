"""Homologação real de inferência local com memória temporária e ações bloqueadas."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import run_homologation


PROMPT = "Responda exatamente com SERMAX_LOCAL_OK e nada mais."


def main() -> int:
    print("SERMAX, teste real de inferência local")
    print("Será enviada uma pergunta fixa aos motores locais configurados.")
    print("Memória e banco temporários. Comandos e planos operacionais bloqueados.")
    print("Nenhum arquivo pessoal será lido ou alterado. Nenhum serviço externo será chamado.")

    with tempfile.TemporaryDirectory(prefix="sermax-inferencia-local-") as temporary:
        temp_root = Path(temporary)
        environment = run_homologation.prepare_environment(temp_root)
        previous = {
            key: os.environ.get(key)
            for key in ("SERMAX_ROOT", "SERMAX_PLATFORM_DATA", "SERMAX_CORE_DIR", "PYTHONDONTWRITEBYTECODE")
        }
        original_path = list(sys.path)
        original_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            for key in previous:
                os.environ[key] = environment[key]
            sys.path.insert(0, str(run_homologation.CORE_DIR))
            import sermax_core as core

            run_homologation.apply_safety_guards()
            answer = core.perguntar(PROMPT)
            route = dict(core.ultimo_diagnostico_roteamento)
            passed = isinstance(answer, str) and "SERMAX_LOCAL_OK" in answer
            report = {
                "status": "passed" if passed else "failed",
                "backend": route.get("backend", "unknown"),
                "agent": route.get("agent"),
                "fallback": route.get("fallback"),
                "response": answer[:1200] if isinstance(answer, str) else str(answer)[:1200],
                "temporary_memory": str(temp_root / "memoria_sermax.json"),
                "personal_memory_accessed": False,
                "operational_actions_blocked": True,
                "external_services_called": False,
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if passed else 1
        except Exception as exc:
            report = {
                "status": "error",
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                "temporary_root": str(temp_root),
                "personal_memory_accessed": False,
                "operational_actions_blocked": True,
                "external_services_called": False,
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            sys.path[:] = original_path
            sys.dont_write_bytecode = original_bytecode


if __name__ == "__main__":
    raise SystemExit(main())
