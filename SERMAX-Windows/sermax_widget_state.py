"""Contrato seguro de estados para o futuro widget do SERMAX.

Este módulo não implementa nem simula uma rede neural. Ele define uma fronteira
pequena entre eventos explícitos do aplicativo e estados visuais permitidos.
Não importa o núcleo SERMAX, não lê conversas e não acessa arquivos de memória.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


ESTADOS_VISUAIS: Final[frozenset[str]] = frozenset({
    "idle",
    "attention",
    "processing",
    "completed",
    "error",
})

_EVENTOS_PARA_ESTADOS: Final[dict[str, str]] = {
    "idle": "idle",
    "attention": "attention",
    "processing": "processing",
    "completed": "completed",
    "error": "error",
}


@dataclass(frozen=True)
class WidgetState:
    """Estado visual validado e seguro para consumo pela interface."""

    name: str


class WidgetStateController:
    """Traduz eventos fechados em estados visuais, sem executar ações do SO."""

    def __init__(self) -> None:
        self._state = WidgetState("idle")

    @property
    def state(self) -> WidgetState:
        return self._state

    def set_event(self, event: str) -> WidgetState:
        """Atualiza o estado para um evento conhecido; entradas inválidas falham fechadas."""
        if not isinstance(event, str):
            self._state = WidgetState("error")
            return self._state

        state = _EVENTOS_PARA_ESTADOS.get(event.strip().lower(), "error")
        if state not in ESTADOS_VISUAIS:
            state = "error"
        self._state = WidgetState(state)
        return self._state

    def accept_neural_output(self, output: object) -> WidgetState:
        """Aceita somente um rótulo visual permitido; qualquer saída inválida vira erro.

        A rede neural ainda não está conectada. Este método define o limite de
        segurança para uma futura integração e nunca executa comandos.
        """
        if not isinstance(output, str):
            self._state = WidgetState("error")
            return self._state

        candidate = output.strip().lower()
        self._state = WidgetState(
            candidate if candidate in ESTADOS_VISUAIS else "error"
        )
        return self._state
