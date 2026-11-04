"""Worker executado no ambiente Python compatível com OpenJarvis."""
from __future__ import annotations
import contextlib, json, sys

def main():
    try:
        request=json.load(sys.stdin)
        if not isinstance(request,dict): raise ValueError("Solicitação inválida.")
        prompt=request.get("prompt")
        model=request.get("model","sermax")
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>4000: raise ValueError("Pergunta inválida.")
        if not isinstance(model,str) or not model.strip() or len(model)>120: raise ValueError("Modelo inválido.")
        with contextlib.redirect_stdout(sys.stderr):
            from openjarvis import Jarvis
            sdk=Jarvis(engine_key="ollama",model=model)
            try:
                response=sdk.ask(prompt.strip(),agent="simple",tools=[],context=False,temperature=0.2,max_tokens=512)
            finally:
                close=getattr(sdk,"close",None)
                if callable(close): close()
        if not isinstance(response,str) or not response.strip(): raise RuntimeError("OpenJarvis retornou resposta vazia.")
        json.dump({"response":response.strip()},sys.stdout,ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}",file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
