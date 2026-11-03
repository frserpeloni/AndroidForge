"""Adaptador isolado da rede LIF do Pestinha para estados visuais SERMAX.

Recebe somente eventos internos explícitos do aplicativo. Não lê janelas,
teclado, mouse, conversas, memória pessoal ou dados do sistema operacional.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

from sermax_widget_state import ESTADOS_VISUAIS


EVENTOS = frozenset({"idle", "attention", "processing", "completed", "error"})
# Somente canais sensoriais do modelo que representam eventos de software
# sem fingir carinho, impacto físico ou interação humana.
ESTIMULOS = {
    "idle": {"SILENCE": 0.25},
    "attention": {"NOVELTY": 0.70, "MOTION": 0.25},
    "processing": {"WORK": 0.80, "TYPING": 0.20},
    "completed": {"NOVELTY": 0.45, "SILENCE": 0.10},
    "error": {"NOVELTY": 0.65, "SILENCE": 0.05},
}
# Motores de expressão, nunca motores de decisão ou ação.
MOTORES_VISUAIS = {
    "WATCH": "attention",
    "CHEER": "completed",
    "SETTLE": "idle",
    "DROWSE": "idle",
    "SAD": "error",
    "ANGRY": "error",
}


class PestinhaAdapter:
    def __init__(
        self,
        state_path: str,
        *,
        brain_factory: Optional[Callable[[], object]] = None,
    ) -> None:
        self.state_path = os.path.abspath(state_path)
        self._brain_factory = brain_factory
        self._brain = None
        self.available = False
        try:
            factory = brain_factory or self._load_brain_factory()
            self._brain = factory()
            self._brain.load(self.state_path)
            self.available = True
        except (ImportError, ModuleNotFoundError):
            self._brain = None
        except Exception:
            # Falha neural nunca impede o funcionamento do SERMAX.
            self._brain = None

    @staticmethod
    def _load_brain_factory():
        from pestinha.core.nervous_system import LIFBrain
        return LIFBrain

    def processar_evento(self, evento: str) -> str:
        if not isinstance(evento, str) or evento.strip().lower() not in EVENTOS:
            return "error"
        evento = evento.strip().lower()
        if evento == "error" or self._brain is None:
            return evento

        try:
            self._brain.stimulate(ESTIMULOS[evento])
            self._brain.step(80)
            atividade = self._brain.motor_activity()
            if not isinstance(atividade, dict):
                return evento
            candidatos = [
                (float(valor), MOTORES_VISUAIS[nome])
                for nome, valor in atividade.items()
                if nome in MOTORES_VISUAIS and isinstance(valor, (int, float))
            ]
            if not candidatos:
                return evento
            intensidade, estado = max(candidatos, key=lambda item: item[0])
            if intensidade <= 0:
                return evento
            return estado if estado in ESTADOS_VISUAIS else evento
        except Exception:
            self.available = False
            self._brain = None
            return evento

    def salvar(self) -> bool:
        if self._brain is None:
            return False
        try:
            pasta = os.path.dirname(self.state_path)
            if pasta:
                os.makedirs(pasta, exist_ok=True)
            self._brain.save(self.state_path)
            return True
        except Exception:
            return False
