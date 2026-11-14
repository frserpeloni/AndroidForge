"""Adaptador da rede LIF do Pestinha para SERMAX.

A rede recebe contexto sensorial e devolve métricas auditáveis. Saídas neurais
nunca executam ações, ferramentas ou alteram permissões do sistema.
"""
from __future__ import annotations
import math
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
TAXA_APRENDIZADO=0.02

class PestinhaAdapter:
    def __init__(self,state_path,*,brain_factory:Optional[Callable[[],object]]=None):
        self.state_path=os.path.abspath(state_path)
        self._brain_factory=brain_factory
        self._brain=None
        self.available=False
        self.last_metrics={}
        self.last_feedback=0.0
        try:
            factory=brain_factory or self._load_brain_factory()
            self._brain=factory()
            existed=os.path.isfile(self.state_path)
            restored=self._brain.load(self.state_path)
            if existed and restored is not True:
                raise ValueError("memória neural existente inválida ou incompatível")
            self.available=True
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

    def registrar_contexto(self,canais,dt_ms=80):
        """Registra estímulos sensoriais permitidos e atualiza elegibilidade sem recompensa."""
        if self._brain is None or not isinstance(canais,dict):
            return {"available":False,"error":"rede indisponível ou contexto inválido"}
        try:
            nomes=set(getattr(self._brain,"sensory_names",()))
            if not canais or any(name not in nomes for name in canais):
                raise ValueError("canal sensorial desconhecido")
            valores={}
            for name,value in canais.items():
                if isinstance(value,bool) or not isinstance(value,(int,float)):
                    raise ValueError("intensidade inválida")
                value=float(value)
                if not math.isfinite(value) or not 0.0<=value<=1.0:
                    raise ValueError("intensidade fora do intervalo 0..1")
                valores[name]=value
            duracao=max(1,min(400,int(dt_ms)))
            self._brain.stimulate(valores)
            self._brain.step(duracao)
            self._brain.learn(0.0,duracao/1000.0,TAXA_APRENDIZADO)
            self.last_metrics=self._coletar_metricas()
            return {"available":True,"metrics":self.last_metrics}
        except Exception as exc:
            self.last_metrics={"error":f"{type(exc).__name__}: {exc}"}
            return {"available":False,"error":self.last_metrics["error"]}

    def registrar_feedback(self,recompensa):
        """Aprende somente com feedback explícito e limitado a -1 ou +1."""
        if self._brain is None:
            return False
        if isinstance(recompensa,bool) or recompensa not in (-1,1):
            return False
        try:
            self._brain.learn(float(recompensa),0.1,TAXA_APRENDIZADO)
            self.last_feedback=float(recompensa)
            self.last_metrics=self._coletar_metricas()
            return True
        except Exception:
            return False

    def _coletar_metricas(self):
        brain=self._brain
        metricas={}
        for nome,metodo in (("pools", "pool_rates"),("efficacy","efficacy"),("motors","motor_activity")):
            fn=getattr(brain,metodo,None)
            if callable(fn):
                valor=fn()
                if isinstance(valor,dict):
                    metricas[nome]={str(k):round(float(v),5) for k,v in valor.items()
                                    if isinstance(v,(int,float)) and math.isfinite(float(v))}
        resumo=getattr(brain,"learned_summary",None)
        if callable(resumo):
            metricas["learned"]=[list(item) for item in resumo(top=5)]
        return metricas

    def diagnostico(self):
        return {"available":self.available,"metrics":self.last_metrics,
                "last_explicit_feedback":self.last_feedback}

    def salvar(self):
        if self._brain is None: return False
        try:
            folder=os.path.dirname(self.state_path)
            if folder: os.makedirs(folder,exist_ok=True)
            self._brain.save(self.state_path)
            return os.path.isfile(self.state_path)
        except Exception:
            return False
