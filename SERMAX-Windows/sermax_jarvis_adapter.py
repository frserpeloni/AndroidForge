"""Ponte opcional e restrita para o SDK OpenJarvis.

SERMAX mantém a identidade, a memória e o controle de ferramentas. Esta ponte
usa somente o agente 'simple', sem ferramentas e sem contexto/memória do Jarvis.
"""
from __future__ import annotations

from typing import Callable, Optional


class JarvisAdapter:
    def __init__(
        self,
        *,
        model: str = "sermax",
        sdk_factory: Optional[Callable[..., object]] = None,
    ) -> None:
        self.model = model
        self._sdk_factory = sdk_factory

    def _factory(self):
        if self._sdk_factory is not None:
            return self._sdk_factory
        try:
            from openjarvis import Jarvis
        except ImportError as exc:
            raise RuntimeError(
                "OpenJarvis não instalado. A ponte SERMAX permanece desativada."
            ) from exc
        return Jarvis

    def responder(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise ValueError("Pergunta inválida.")
        prompt = prompt.strip()
        if not prompt or len(prompt) > 4000:
            raise ValueError("A pergunta deve conter de 1 a 4000 caracteres.")

        sdk = self._factory()(engine_key="ollama", model=self.model)
        try:
            # Agente simples: sem ferramentas, shell, arquivos ou memória externa.
            resposta = sdk.ask(
                prompt,
                agent="simple",
                tools=[],
                context=False,
                temperature=0.2,
                max_tokens=512,
            )
            if not isinstance(resposta, str) or not resposta.strip():
                raise RuntimeError("OpenJarvis retornou uma resposta vazia.")
            return resposta.strip()
        finally:
            close = getattr(sdk, "close", None)
            if callable(close):
                close()
