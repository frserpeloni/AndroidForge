"""Ponte SERMAX para OpenJarvis em processo Python isolado."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
from typing import Callable, Optional

class JarvisAdapter:
    def __init__(self, *, model="sermax", agent="orchestrator", sdk_factory: Optional[Callable[..., object]]=None,
                 python_executable=None, worker_path=None, timeout=180):
        if agent not in {"simple", "orchestrator"}: raise ValueError("Agente OpenJarvis não permitido.")
        self.model=model
        self.agent=agent
        self._sdk_factory=sdk_factory
        self.python_executable=python_executable or os.environ.get("SERMAX_JARVIS_PYTHON")
        self.worker_path=worker_path
        self.timeout=timeout

    def _direct_responder(self, prompt):
        sdk=self._sdk_factory(engine_key="ollama", model=self.model)
        try:
            tools=["calculator", "think"] if self.agent == "orchestrator" else []
            answer=sdk.ask(prompt, agent=self.agent, tools=tools, context=False, temperature=0.2, max_tokens=512)
            if not isinstance(answer,str) or not answer.strip():
                raise RuntimeError("OpenJarvis retornou uma resposta vazia.")
            return answer.strip()
        finally:
            close=getattr(sdk,"close",None)
            if callable(close): close()

    def responder(self,prompt):
        if not isinstance(prompt,str): raise ValueError("Pergunta inválida.")
        prompt=prompt.strip()
        if not prompt or len(prompt)>4000: raise ValueError("A pergunta deve conter de 1 a 4000 caracteres.")
        if self._sdk_factory is not None: return self._direct_responder(prompt)
        root_value=os.environ.get("SERMAX_ROOT")
        if root_value: root=Path(root_value)
        elif getattr(sys,"frozen",False): root=Path(sys.executable).resolve().parent
        else: root=Path(__file__).resolve().parent
        python=self.python_executable or str(root/".venv-jarvis"/"Scripts"/"python.exe")
        if self.worker_path: worker=Path(self.worker_path)
        elif getattr(sys,"frozen",False) and hasattr(sys,"_MEIPASS"): worker=Path(sys._MEIPASS)/"sermax_jarvis_worker.py"
        else: worker=root/"sermax_jarvis_worker.py"
        if not Path(python).is_file(): raise RuntimeError("Ambiente OpenJarvis indisponível. Configure SERMAX_JARVIS_PYTHON ou instale .venv-jarvis.")
        if not worker.is_file(): raise RuntimeError("Worker OpenJarvis não encontrado.")
        payload=json.dumps({"prompt":prompt,"model":self.model,"agent":self.agent},ensure_ascii=False)
        try:
            proc=subprocess.run([python,str(worker)],input=payload,text=True,encoding="utf-8",
                                capture_output=True,timeout=self.timeout,check=False,cwd=str(root))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("OpenJarvis excedeu o tempo limite.") from exc
        if proc.returncode!=0:
            detail=(proc.stderr or proc.stdout or "falha sem detalhes").strip()[-2000:]
            raise RuntimeError(f"Processo OpenJarvis falhou: {detail}")
        try: result=json.loads(proc.stdout)
        except json.JSONDecodeError as exc: raise RuntimeError("Worker OpenJarvis retornou uma resposta inválida.") from exc
        answer=result.get("response") if isinstance(result,dict) else None
        if not isinstance(answer,str) or not answer.strip(): raise RuntimeError("OpenJarvis retornou uma resposta vazia.")
        return answer.strip()
