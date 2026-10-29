"""Comandos modulares seguros do SERMAX v3.1.2."""
def _log(hist,cmd,answer):
    hist.extend([{"role":"user","content":cmd},{"role":"assistant","content":str(answer)}])
def processar(cmd,hist,core):
    if not isinstance(cmd,str): return False
    low=cmd.strip().lower()
    if low=="/integracao":
        import os
        root=os.path.dirname(os.path.abspath(core.__file__))
        lines=["SERMAX v3.1.4 — diagnóstico da instalação principal",
          "Núcleo: "+("OK" if hasattr(core,"perguntar") else "AUSENTE"),
          "Planejador: "+("OK" if hasattr(core,"sermax_planejador") else "AUSENTE"),
          "Executor: "+("OK" if hasattr(core,"sermax_executor") else "AUSENTE"),
          "Tarefas: "+("OK" if hasattr(core,"sermax_tarefas") else "AUSENTE"),
          "Memória: "+("ENCONTRADA" if os.path.isfile(getattr(core,"ARQUIVO_MEMORIA","")) else "AUSENTE"),
          "Whisper: "+("ENCONTRADO" if os.path.isfile(os.path.join(root,"voz","whisper","Release","whisper-cli.exe")) else "AUSENTE"),
          "Modelo de voz: "+("ENCONTRADO" if os.path.isfile(os.path.join(root,"voz","modelos","ggml-tiny.bin")) else "AUSENTE"),
          "Instalação ativa: C:\\SERMAX."]
        _log(hist,cmd,"\n".join(lines)); return True
    if low=="/plano" or low.startswith("/plano "):
        obj=cmd[len("/plano"):].strip()
        try:
            answer=core.sermax_planejador.planejar(obj,modelo=getattr(core,"MODELO","sermax"),url=getattr(core,"OLLAMA_URL","http://127.0.0.1:11434/api/chat")) if obj else "Uso: /plano <objetivo>"
        except Exception as e: answer=f"Erro do planejador ({type(e).__name__}: {e}). Nenhuma ação executada."
        _log(hist,cmd,answer); return True
    if low=="/tarefas" or low.startswith("/tarefas "):
        plan=cmd[len("/tarefas"):].strip()
        if not plan: answer="Uso: /tarefas sistema; calcular 125 x 87; memoria Siena"
        else:
            try: answer=core.sermax_tarefas.executar_plano(plan,core=core,ferramenta=getattr(core,"ferramenta_windows",None))
            except Exception as e: answer=f"Erro nas tarefas seguras ({type(e).__name__}: {e})."
        _log(hist,cmd,answer); return True
    return False
