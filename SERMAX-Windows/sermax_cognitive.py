"""Ponte cognitiva do SERMAX com o subsistema Pestinha.

O módulo mantém a rede neural e as memórias do Pestinha isoladas da memória
pessoal do SERMAX. Não executa comandos do sistema operacional.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Iterable

from sermax_pestinha.pestinha import config
from sermax_pestinha.pestinha.core.conditioning import Conditioning
from sermax_pestinha.pestinha.core.emotion import EmotionState
from sermax_pestinha.pestinha.core.episodic import EpisodicMemory
from sermax_pestinha.pestinha.core.homeostasis import Drives
from sermax_pestinha.pestinha.core.motor import MotorTone
from sermax_pestinha.pestinha.core.nervous_system import LIFBrain, MotorDecoder

EVENT_CHANNELS = {
    "user_request": "PEDIDO",
    "task_started": "WORK",
    "task_finished": "NOVELTY",
    "user_attention": "SOCIAL",
    "new_information": "NOVELTY",
}
INTERNAL_CHANNELS = frozenset({"BOREDOM", "FATIGUE", "LONELY"})
DEFAULT_SENSOR_PERMISSIONS = {
    "PEDIDO": True,
    "WORK": True,
    "NOVELTY": True,
    "SOCIAL": False,
    "TYPING": False,
    "MOTION": False,
    "SILENCE": False,
    "SOUND": False,
    "WEB": False,
    "POKE": False,
    "DRAG": False,
    "DISMISS": False,
    "CARESS": False,
    "ANTICIPATE": True,
    "TOY_NEAR": False,
    "TOY_TAKEN": False,
    "THROW": False,
    "IMPACT": False,
    "PEDIDO": True,
    "PRESO": False,
    "LEMBRA_FUGA": False,
    "RECUSA": False,
    "PLACA": False,
    "ANTECIPA_PLACA": False,
    "VISITA": False,
    "RECEIO": False,
    "RANCOR": False,
}


class SermaxCognitiveEngine:
    """Integra rede LIF, homeostase, emoção, condicionamento e memória episódica."""

    def __init__(self, state_dir: str | Path, seed: int = 7,
                 sensor_permissions: dict[str, bool] | None = None):
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.profile = config.PROFILES["normal"]
        self.brain = LIFBrain(seed=seed)
        self.drives = Drives()
        self.emotion = EmotionState()
        self.motor_tone = MotorTone()
        self.motor_decoder = MotorDecoder()
        self.conditioning = Conditioning(self.state_dir / "conditioning.json",
                                         rate=self.profile["cond_rate"])
        self.episodic = EpisodicMemory(self.state_dir / "episodes.jsonl",
                                       self.state_dir / "preferences.json")
        self.sensor_permissions = dict(DEFAULT_SENSOR_PERMISSIONS)
        if sensor_permissions:
            self.set_sensor_permissions(sensor_permissions)
        self._pending: dict[str, float] = {}
        self._last_motor: dict[str, float] = {}
        self._last_decision = None
        self._last_tick = time.monotonic()
        self.brain.load(self.state_dir / "nervous.json")
        self.drives.load(self.state_dir / "drives.json", self.profile)
        self.conditioning.load()
        self.episodic.load()

    def set_sensor_permissions(self, permissions: dict[str, bool]) -> dict[str, bool]:
        """Atualiza permissões por canal; canais internos continuam sob controle do motor interno."""
        if not isinstance(permissions, dict):
            raise TypeError("permissions deve ser um dicionário.")
        for channel, enabled in permissions.items():
            if channel not in self.brain.sensory_names:
                raise ValueError(f"Canal sensorial desconhecido: {channel}")
            if channel in INTERNAL_CHANNELS:
                raise ValueError(f"{channel} é um canal interno, não um sensor externo.")
            if type(enabled) is not bool:
                raise TypeError(f"A permissão de {channel} deve ser booleana.")
        self.sensor_permissions.update(permissions)
        return dict(self.sensor_permissions)

    def set_sensor_permission(self, channel: str, enabled: bool) -> bool:
        self.set_sensor_permissions({channel: enabled})
        return self.sensor_permissions[channel]

    def submit_event(self, event: str, intensity: float = 1.0) -> bool:
        """Envia evento explícito e permitido. Não lê teclado, janelas, sites ou processos."""
        if not isinstance(event, str):
            return False
        channel = EVENT_CHANNELS.get(event.strip().lower())
        if channel is None or not self.sensor_permissions.get(channel, False):
            return False
        value = max(0.0, min(1.0, float(intensity)))
        with self._lock:
            self._pending[channel] = max(self._pending.get(channel, 0.0), value)
        return True

    def stimulate(self, channel: str, intensity: float) -> bool:
        """Entrada sensorial direta, sujeita à permissão do canal."""
        if channel not in self.brain.sensory_names:
            return False
        if channel in INTERNAL_CHANNELS or not self.sensor_permissions.get(channel, False):
            return False
        value = max(0.0, min(1.0, float(intensity)))
        with self._lock:
            self._pending[channel] = max(self._pending.get(channel, 0.0), value)
        return True

    def set_cue(self, cue: str, active: bool) -> bool:
        if cue not in {"PRESS", "APPROACH", "PLACA"}:
            return False
        with self._lock:
            self.conditioning.set_cue(cue, bool(active), time.monotonic())
        return True

    def feedback(self, reward: float, duration_s: float = 1.0) -> None:
        """Reforço explícito entre -1 e +1, aplicado às elegibilidades recentes."""
        reward = max(-1.0, min(1.0, float(reward)))
        duration_s = max(0.0, min(10.0, float(duration_s)))
        with self._lock:
            self.brain.learn(reward, duration_s, self.profile["learn_rate"])

    def tick(self, dt_ms: float = 100.0) -> dict:
        """Avança o ciclo neural, atualiza necessidades, emoção e decodificador motor."""
        dt_ms = max(1.0, min(400.0, float(dt_ms)))
        dt_s = dt_ms / 1000.0
        with self._lock:
            self.conditioning.tick(time.monotonic())
            stimuli = dict(self._pending)
            self._pending.clear()
            self.drives.update(
                dt_s, self.profile, asleep=False, moving=self.motor_tone.drive(),
                arousal=self.emotion.arousal, user_away=False,
                engaged=stimuli.get("WORK", 0.0) > 0.0,
            )
            stimuli.update(self.drives.channels())
            stimuli["ANTICIPATE"] = max(
                stimuli.get("ANTICIPATE", 0.0),
                self.conditioning.strength(),
            )
            self.brain.stimulate(stimuli)
            self.brain.step(dt_ms)
            motors = self.brain.motor_activity()
            self.brain.learn(0.0, dt_s, self.profile["learn_rate"])
            now = time.monotonic()
            emotion = self.emotion.update(motors, dt_s, self.profile, now=now)
            self.motor_tone.update(motors, dt_s)
            decision, changed = self.motor_decoder.update(motors, now=now)
            self._last_motor = motors
            self._last_decision = decision
            self._last_tick = now
            return self.snapshot()

    def choose_action(self, context: str, allowed: Iterable[str], epsilon: float = 0.05):
        """Seleciona uma opção permitida com base na memória episódica do Pestinha."""
        options = [str(x) for x in allowed]
        with self._lock:
            return self.episodic.choose(str(context), options,
                                        max(0.0, min(1.0, float(epsilon))))

    def record_decision(self, context: str, action: str, result: str,
                        valence: float) -> None:
        """Registra resultado de uma decisão para aprendizado episódico contextual."""
        valence = max(-1.0, min(1.0, float(valence)))
        with self._lock:
            episode = self.episodic.start(str(context), str(action))
            self.episodic._resolve(episode, str(result)[:240], valence)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "network": self.brain.describe(),
                "neurons": int(self.brain.N),
                "synapses": int(self.brain.n_synapses),
                "emotion": self.emotion.current,
                "valence": round(float(self.emotion.valence), 4),
                "arousal": round(float(self.emotion.arousal), 4),
                "drives": {
                    "energy": round(self.drives.energy, 4),
                    "stimulation": round(self.drives.stimulation, 4),
                    "contact": round(self.drives.contact, 4),
                },
                "decision": self._last_decision,
                "motors": dict(self._last_motor),
                "learned": self.brain.learned_summary(top=8),
                "sensor_permissions": dict(self.sensor_permissions),
            }

    def prompt_context(self) -> str:
        """Resumo curto dos estados internos para o raciocínio do Ollama."""
        state = self.snapshot()
        drives = state["drives"]
        learned = state["learned"]
        learned_text = ", ".join(
            f"{sensor}->{target} ({weight:+.3f})"
            for sensor, target, weight in learned
        ) or "sem associações reforçadas"
        return (
            "ESTADO COGNITIVO INTERNO DO SERMAX, calculado pelo subsistema neural: "
            f"emoção operacional={state['emotion']}; valência={state['valence']}; "
            f"ativação={state['arousal']}; energia={drives['energy']}; "
            f"estimulação={drives['stimulation']}; contato={drives['contact']}; "
            f"tendência motora={state['decision'] or 'nenhuma'}. "
            f"Associações aprendidas={learned_text}. "
            "Trate esses valores como sinais computacionais, não como sentimentos humanos. "
            "Eles ajudam a avaliar contexto, mas não autorizam ações externas."
        )

    def save(self) -> None:
        with self._lock:
            self.brain.save(self.state_dir / "nervous.json")
            self.drives.save(self.state_dir / "drives.json")
            self.conditioning.save()
            self.episodic.save()

    def close(self) -> None:
        self.save()
