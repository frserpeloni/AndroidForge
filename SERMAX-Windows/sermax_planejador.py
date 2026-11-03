"""Planejador local SERMAX v3.1.7: organização segura de listas."""
import json, re, urllib.request, urllib.error

MODELO_PADRAO = "sermax"
URL_PADRAO = "http://127.0.0.1:11434/api/chat"
FERRAMENTAS_PERMITIDAS = {"responder", "consultar_memoria", "calcular", "consultar_sistema"}

_INSTRUCOES = """Você é o planejador local do SERMAX. Proponha um plano curto, sem executar ações.
Não invente tarefas pessoais, compromissos, horários ou prazos. Não altere a lista fornecida.
Use no máximo quatro etapas. Não proponha comandos de terminal, scripts, alterações de arquivos,
instalações ou ações destrutivas. Retorne somente JSON:
{"objetivo":"...","etapas":[{"titulo":"...","ferramenta":"responder","verificacao":"..."}]}.
Ferramenta deve ser responder, consultar_memoria, calcular ou consultar_sistema."""

def _safe(s, n=240):
    if not isinstance(s, str): return ""
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", s)).strip()[:n]

def _parse_lista(texto):
    # Accept "organizar: A, B, C", newline-separated items, or semicolons.
    partes = re.split(r"[;\n]+", texto)
    itens=[]
    for parte in partes:
        parte=parte.strip(" \t-•")
        if not parte: continue
        # Commas separate tasks only when there is no sentence-like phrase.
        if "," in parte:
            itens.extend(x.strip(" \t-•") for x in parte.split(",") if x.strip(" \t-•"))
        else:
            itens.append(parte)
    saida=[]
    vistos=set()
    for item in itens:
        item=_safe(item,180)
        chave=item.casefold()
        if item and chave not in vistos:
            vistos.add(chave); saida.append(item)
    return saida[:20]

def _plano_organizacao(objetivo):
    low=objetivo.lower().strip()
    verbos=("organizar","organize","planejar","planeje","ordenar")
    if not any(v in low for v in verbos) or not any(k in low for k in ("tarefa","tarefas","dia","rotina","lista","organizar:","organize:")):
        return None
    # Strip common task-intro prefixes but keep user content intact.
    m=re.search(r"\b(?:organizar|organize|planejar|planeje|ordenar)(?:\s+(?:as|minhas|minha|meu|meus))?(?:\s+(?:tarefas|lista|rotina|dia))?\s*:?\s*(.*)$", objetivo, re.I)
    remainder=m.group(1).strip(" :.-") if m else ""
    # "organizar minhas tarefas para hoje" has no actual task list.
    if not remainder or remainder.lower() in {"para hoje","hoje","do dia","para o dia de hoje"}:
        return ("Para organizar suas tarefas, preciso da lista real.\n"
                "Envie uma tarefa por linha ou separe-as por ponto e vírgula. "
                "Se souber, inclua prazo e urgência.\n"
                "Não vou inventar compromissos nem executar ações.")
    # Remove leading connective phrases before parsing.
    remainder=re.sub(r"^(?:para hoje|hoje|do dia de hoje)\s*[:,.-]?\s*", "", remainder, flags=re.I)
    itens=_parse_lista(remainder)
    # Avoid treating generic words as task items.
    itens=[x for x in itens if x.lower() not in {"para hoje","hoje","tarefas para hoje","minhas tarefas para hoje"}]
    if not itens:
        return ("Ainda não identifiquei tarefas na mensagem.\n"
                "Envie uma tarefa por linha ou separe-as por ponto e vírgula.\n"
                "Nenhuma ação foi executada.")
    linhas=["LISTA ORGANIZADA — proposta, não executada:"]
    for i,item in enumerate(itens,1):
        lowitem=item.lower()
        if any(k in lowitem for k in ("vencido","atrasado","vence hoje","urgente","prazo hoje","até hoje")):
            marca="URGENTE (com base no texto informado)"
        elif any(k in lowitem for k in ("quando puder","sem prazo","não urgente","na semana")):
            marca="PODE AGUARDAR (com base no texto informado)"
        else:
            marca="PRAZO/urgência a confirmar"
        linhas.append(f"{i}. {item} — {marca}")
    linhas.extend(["","Não inventei prazos. A ordem acima mantém a sequência que você informou.",
                   "Se informar vencimentos ou urgências, posso reordenar a lista.",
                   "Nenhuma ferramenta foi executada."])
    return "\n".join(linhas)

def validar_resposta_plano(content, objetivo):
    """Valida a saída não confiável do modelo e retorna etapas permitidas."""
    if not isinstance(content, str) or len(content) > 16000:
        raise ValueError("resposta do modelo ausente ou acima de 16 KB")
    texto = content.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.I)
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim <= inicio:
        raise ValueError("JSON ausente")
    dados = json.loads(texto[inicio:fim + 1])
    if not isinstance(dados, dict) or not isinstance(dados.get("etapas"), list):
        raise ValueError("estrutura inválida")
    if not 1 <= len(dados["etapas"]) <= 4:
        raise ValueError("o plano deve conter de uma a quatro etapas")
    etapas = []
    for etapa in dados["etapas"]:
        if not isinstance(etapa, dict):
            raise ValueError("etapa inválida")
        ferramenta = etapa.get("ferramenta")
        if ferramenta not in FERRAMENTAS_PERMITIDAS:
            raise ValueError("ferramenta não permitida")
        titulo = _safe(etapa.get("titulo"), 160)
        verificacao = _safe(etapa.get("verificacao"), 200)
        if not titulo or not verificacao:
            raise ValueError("etapa sem título ou verificação")
        etapas.append((titulo, ferramenta, verificacao))
    return etapas


def planejar(objetivo, modelo=MODELO_PADRAO, url=URL_PADRAO, timeout=300):
    objetivo=_safe(objetivo,1200)
    if not objetivo: return "Informe o objetivo após /plano."
    direto=_plano_organizacao(objetivo)
    if direto is not None: return direto
    payload={"model":modelo,"stream":False,"format":"json","keep_alive":"10m",
      "options":{"num_ctx":1024,"num_predict":120,"temperature":0},
      "messages":[{"role":"system","content":_INSTRUCOES},
      {"role":"user","content":"Proponha um plano para este objetivo, sem executar: "+objetivo}]}
    req=urllib.request.Request(url,data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
      headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            result=json.loads(r.read().decode("utf-8"))
        content=result.get("message",{}).get("content","")
        etapas=validar_resposta_plano(content, objetivo)
        linhas=["Plano proposto (ainda não executado):","Objetivo: "+objetivo]
        for i,(t,f,v) in enumerate(etapas,1): linhas.extend([f"{i}. {t} [ferramenta: {f}]",f"   Verificação: {v}"])
        linhas.append("Nenhuma ferramenta ou comando foi executado.")
        return "\n".join(linhas)
    except urllib.error.HTTPError as e:
        return f"Erro HTTP {e.code} na API do Ollama. Nenhuma ação executada."
    except (urllib.error.URLError,TimeoutError) as e:
        return f"Falha de conexão/tempo limite com Ollama: {getattr(e,'reason',str(e))}. Nenhuma ação executada."
    except Exception as e:
        return f"Planejador: {type(e).__name__}: {e}. Nenhuma ação executada."
