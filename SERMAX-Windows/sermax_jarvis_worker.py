"""Worker isolado do OpenJarvis, fixado à política de segurança do SERMAX."""
from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path


AGENTE_SERMAX = "orchestrator"
FERRAMENTAS_PERMITIDAS = ("calculator", "think")


def _configurar_openjarvis():
    """Cria configuração explícita. Não herda preferências do perfil do usuário."""
    from openjarvis.core.config import JarvisConfig

    config = JarvisConfig()
    config.skills.enabled = False
    config.tools.mcp.enabled = False
    config.tools.enabled = ""
    config.agent.tools = ""
    config.agent.context_from_memory = False
    config.agent.max_turns = 4
    config.agent.default_system_prompt = (
        "Você é um componente interno do SERMAX. "
        "Responda ao pedido recebido em português, com precisão. "
        "Não afirme ser um assistente independente."
    )
    config.agent.system_prompt = config.agent.default_system_prompt
    config.telemetry.enabled = False
    config.traces.enabled = False
    config.analytics.enabled = False
    config.channel.enabled = False
    config.tools.storage.enabled = False

    # Impede a leitura acidental de arquivos SOUL/MEMORY/USER do perfil Jarvis.
    isolated = Path(os.environ.get("SERMAX_ROOT", Path(__file__).resolve().parent))
    isolated = isolated / ".sermax-openjarvis-isolated"
    config.memory_files.soul_path = str(isolated / "SOUL.md")
    config.memory_files.memory_path = str(isolated / "MEMORY.md")
    config.memory_files.user_path = str(isolated / "USER.md")
    config.memory_files.persona_name = ""
    return config


def main():
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("Solicitação inválida.")
        prompt = request.get("prompt")
        model = request.get("model", "sermax")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            raise ValueError("Pergunta inválida.")
        if not isinstance(model, str) or not model.strip() or len(model) > 120:
            raise ValueError("Modelo inválido.")

        with contextlib.redirect_stdout(sys.stderr):
            from openjarvis import Jarvis

            sdk = Jarvis(
                config=_configurar_openjarvis(),
                engine_key="ollama",
                model=model,
            )
            try:
                response = sdk.ask(
                    prompt.strip(),
                    agent=AGENTE_SERMAX,
                    tools=list(FERRAMENTAS_PERMITIDAS),
                    context=False,
                    temperature=0.2,
                    max_tokens=512,
                )
            finally:
                close = getattr(sdk, "close", None)
                if callable(close):
                    close()

        if not isinstance(response, str) or not response.strip():
            raise RuntimeError("OpenJarvis retornou resposta vazia.")
        json.dump({"response": response.strip()}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
