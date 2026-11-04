"""Adaptador isolado da rede LIF do Pestinha para estados visuais SERMAX."""
from __future__ import annotations
import os
from typing import Callable, Optional
from sermax_widget_state import ESTADOS_VISUAIS

EVENTOS=frozenset({"idle","attention","processing","completed","error"})
ESTIMULOS={
 "idle":{"SILENCE":0.25},
 "attention":{"NOVELTY":0.70,"MOTION":0.25},
 "processing":{"WORK":0.80,"TYPING":0.20},
 "completed":{"NOVELTY":0.45,"SILENCE":0.10},
 "error":{"NOVELTY":0.65,"SILENCE":0.05},
}
MOTORES_VISUAIS={"WATCH":"attention","CHEER":"completed","SETTLE":"idle","DROWSE":"idle","SAD":"error","ANGRY":"error"}

class PestinhaAdapter:
    def __init__(self,state_path,*,brain_factory:Optional[Callable[[],object]]=None):
        self.state_path=os.path.abspath(state_path)
        self._brain_factory=brain_factory
        self._brain=None
        self.available=False
        try:
            factory=brain_factory or self._load_brain_factory()
            self._brain=factory()
            existed=os.path.isfile(self.state_path)
            restored=self._brain.load(self.state_path)
            if existed and restored is not True:
                raise ValueError("memória neural existente inválida ou incompatível")
            self.available=True
        except (ImportError,ModuleNotFoundError):
            self._brain=None
        except Exception:
            self._brain=None

    @staticmethod
    def _load_brain_factory():
        from pestinha.core.nervous_system import LIFBrain
        return LIFBrain

    def processar_evento(self,evento):
        if not isinstance(evento,str) or evento.strip().lower() not in EVENTOS: return "error"
        evento=evento.strip().lower()
        if evento=="error" or self._brain is None: return evento
        try:
            self._brain.stimulate(ESTIMULOS[evento])
            self._brain.step(80)
            activity=self._brain.motor_activity()
            if not isinstance(activity,dict): return evento
            choices=[(float(value),MOTORES_VISUAIS[name]) for name,value in activity.items()
                     if name in MOTORES_VISUAIS and isinstance(value,(int,float))]
            if not choices: return evento
            intensity,state=max(choices,key=lambda item:item[0])
            if intensity<=0: return evento
            return state if state in ESTADOS_VISUAIS else evento
        except Exception:
            self.available=False
            self._brain=None
            return evento

    def salvar(self):
        if self._brain is None: return False
        try:
            folder=os.path.dirname(self.state_path)
            if folder: os.makedirs(folder,exist_ok=True)
            self._brain.save(self.state_path)
            return os.path.isfile(self.state_path)
        except Exception:
            return False
