import json
import urllib.request
import urllib.error
import os
import re
import ast
import operator
import math
import shutil
import sys
from datetime import datetime

import ferramenta_windows
import sermax_planejador
import sermax_executor
import sermax_tarefas

IDENTIDADE = """
Você é SERMAX, o assistente pessoal de Fabiano.
Informações de identidade:
- Seu nome é SERMAX.
- Seu apelido é MAX.
- O nome do usuário é Fabiano.
- Qwen é o modelo de linguagem utilizado pelo SERMAX.
Converse naturalmente em português do Brasil. Use contexto e memória sem inventar detalhes.
"""

MODELO = "sermax"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
if os.environ.get("SERMAX_ROOT"):
    BASE_DIR = os.path.abspath(os.environ["SERMAX_ROOT"])
elif getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_MEMORIA = os.path.join(BASE_DIR, "memoria_sermax.json")
MAX_MEMORIAS = 500
KEEP_ALIVE = "10m"
OPCOES_MODELO = {"num_ctx": 2048, "num_predict": 256}
ultimo_diagnostico_ollama = {}

STOPWORDS = {"a","o","as","os","um","uma","de","do","da","dos","das","e","é","em","no","na","nos","nas","que","qual","quais","eu","me","meu","minha","meus","minhas","você","seu","sua","seus","suas","para","por","com","como","foi","ser","sou","sobre","isso","esse","essa","este","esta","ao","aos","às","já"}
PALAVRAS_DE_PERGUNTA = {"qual","quais","quem","como","onde","quando","porque","porquê","quanto","quantos","quantas","posso","devo","será","tem","há"}
FRASES_DESCARTAVEIS = {"ok","okay","sim","não","nao","pronto","certo","beleza","entendi","continua","continue","obrigado","obrigada","valeu","bom dia","boa tarde","boa noite","oi","olá","ola"}
MARCADORES_PESSOAIS = {"meu","minha","meus","minhas","eu","tenho","sou","moro","nasci","gosto","prefiro","quero","uso","trabalho","chamo","preciso","costumo","estou"}

def normalizar(texto):
    return re.sub(r"\s+", " ", str(texto).strip().lower())

def eh_memoria_candidata(texto):
    t=normalizar(texto)
    if not t or t.startswith("/") or t in FRASES_DESCARTAVEIS or "?" in t: return False
    p=re.findall(r"[a-záàâãéêíóôõúç]+",t)
    return bool(p and p[0] not in PALAVRAS_DE_PERGUNTA and any(x in MARCADORES_PESSOAIS for x in p))

def _limpar_lista_memoria(memoria_antiga):
    memoria=[]; vistos=set()
    if not isinstance(memoria_antiga,list): return memoria
    for item in memoria_antiga:
        if not isinstance(item,dict) or item.get("role")!="user": continue
        c=str(item.get("content","")).strip(); k=normalizar(c)
        if eh_memoria_candidata(c) and k and k not in vistos:
            vistos.add(k); memoria.append({"role":"user","content":c})
    return memoria[-MAX_MEMORIAS:]

def carregar_memoria():
    if not os.path.exists(ARQUIVO_MEMORIA): return []
    try:
        with open(ARQUIVO_MEMORIA,"r",encoding="utf-8") as f: dados=json.load(f)
        if not isinstance(dados,list): raise ValueError("O arquivo de memória não contém uma lista JSON.")
        return _limpar_lista_memoria(dados)
    except (OSError,UnicodeError,json.JSONDecodeError,ValueError):
        try:
            if os.path.isfile(ARQUIVO_MEMORIA):
                stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                shutil.copy2(ARQUIVO_MEMORIA,ARQUIVO_MEMORIA+".corrompido_"+stamp+".bak")
        except OSError:
            raise RuntimeError("A memória está inválida e não foi possível fazer cópia de segurança. Arquivo original preservado.")
        return []

historico=carregar_memoria()
sessao=[]

def salvar_memoria():
    pasta=os.path.dirname(os.path.abspath(ARQUIVO_MEMORIA)); os.makedirs(pasta,exist_ok=True)
    temp=ARQUIVO_MEMORIA+f".tmp_{os.getpid()}_{datetime.now().strftime('%H%M%S%f')}"
    dados=_limpar_lista_memoria(historico[-MAX_MEMORIAS:])
    try:
        with open(temp,"x",encoding="utf-8",newline="\n") as f:
            json.dump(dados,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(temp,ARQUIVO_MEMORIA)
    except Exception:
        try:
            if os.path.exists(temp): os.remove(temp)
        except OSError: pass
        raise

def registrar_memoria(mensagem):
    if not eh_memoria_candidata(mensagem): return False
    mensagem=str(mensagem).strip(); chave=normalizar(mensagem)
    if any(normalizar(x.get("content",""))==chave for x in historico): return False
    historico.append({"role":"user","content":mensagem})
    if len(historico)>MAX_MEMORIAS: del historico[:-MAX_MEMORIAS]
    salvar_memoria(); return True

def palavras_importantes(texto):
    return {p for p in re.findall(r"[a-záàâãéêíóôõúç]+",normalizar(texto)) if len(p)>=3 and p not in STOPWORDS}

def buscar_memorias(pergunta,limite=4):
    termos=palavras_importantes(pergunta)
    if not termos: return []
    melhores={}; total=len(historico)
    for i,item in enumerate(historico):
        inter=termos.intersection(palavras_importantes(str(item.get("content",""))))
        if not inter: continue
        assinatura=tuple(sorted(inter)); cobertura=len(inter)/max(len(termos),1)
        score=len(inter)*100+ cobertura*10+i/max(total,1)
        atual=melhores.get(assinatura)
        if atual is None or (score,i)>(atual[0],atual[1]): melhores[assinatura]=(score,i,item)
    vals=sorted(melhores.values(),key=lambda x:(x[0],x[1]),reverse=True)
    out=[x[2] for x in vals[:limite]]; out.reverse(); return out

def montar_contexto(pergunta):
    contexto=[{"role":"system","content":IDENTIDADE}]
    mem=buscar_memorias(pergunta,4)
    if mem:
        txt="INFORMAÇÕES RECUPERADAS DA MEMÓRIA DO USUÁRIO. Considere a mais recente em caso de conflito; não acrescente detalhes não registrados:\n"
        txt += "".join("- "+x["content"]+"\n" for x in mem)
        contexto.append({"role":"system","content":txt})
    contexto.extend(sessao[-10:]); return contexto

_OPERADORES_BINARIOS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
_OPERADORES_UNARIOS={ast.UAdd:operator.pos,ast.USub:operator.neg}
def _avaliar_conta(no):
    if isinstance(no,ast.Expression): return _avaliar_conta(no.body)
    if isinstance(no,ast.Constant) and isinstance(no.value,(int,float)) and not isinstance(no.value,bool): valor=no.value
    elif isinstance(no,ast.BinOp) and type(no.op) in _OPERADORES_BINARIOS:
        esq,dir=_avaliar_conta(no.left),_avaliar_conta(no.right)
        if isinstance(no.op,ast.Pow) and (abs(dir)>10 or abs(esq)>1000000): raise ValueError("Potência fora do limite seguro.")
        valor=_OPERADORES_BINARIOS[type(no.op)](esq,dir)
    elif isinstance(no,ast.UnaryOp) and type(no.op) in _OPERADORES_UNARIOS: valor=_OPERADORES_UNARIOS[type(no.op)](_avaliar_conta(no.operand))
    else: raise ValueError("Expressão não permitida.")
    if not math.isfinite(float(valor)) or abs(valor)>1e15: raise ValueError("Resultado fora do limite seguro.")
    return valor

def _formatar_resultado(valor):
    if isinstance(valor,float) and valor.is_integer(): valor=int(valor)
    if isinstance(valor,int): return f"{valor:,}".replace(",",".")
    return f"{valor:,.8f}".rstrip("0").rstrip(".").replace(",","X").replace(".",",").replace("X",".")

def responder_calculo_local(mensagem):
    texto=str(mensagem).strip().lower().replace("×","*").replace("÷","/")
    texto=re.sub(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*%\s+de\s+([+-]?\d+(?:[.,]\d+)?)",r"(\1/100*\2)",texto)
    texto=re.sub(r"(?<=\d),(?=\d)",".",texto)
    texto=re.sub(r"(?<=[0-9)])\s*[xX]\s*(?=[0-9(])","*",texto)
    texto=re.sub(r"^(?:por favor[, ]*)?(?:calcule|calcular|quanto é|quanto e|resolva|resultado de|faz a conta|faça a conta|faca a conta)\s*","",texto)
    texto=re.sub(r"\s+","",texto)
    if not texto or len(texto)>100 or not re.fullmatch(r"[0-9.+*/()%\-]+",texto) or not re.search(r"[+*/%\-]",texto): return None
    try: return f"Resultado: {_formatar_resultado(_avaliar_conta(ast.parse(texto,mode='eval')))}"
    except ZeroDivisionError: return "Não consigo dividir por zero."
    except (SyntaxError,ValueError,TypeError,OverflowError): return None

def responder_comando_local(mensagem):
    comando=normalizar(mensagem).strip()
    if comando in {"/executar","/executar ajuda"}:
        return "Executor local restrito. Exemplos: /executar sistema; /executar memoria Siena; /executar calcular 125 x 87. Só executa consultas de leitura e cálculos."
    if comando.startswith("/executar "):
        return sermax_executor.executar(mensagem.strip()[len("/executar "):],core=sys.modules[__name__],ferramenta=ferramenta_windows)
    if comando in {"/executar-plano","/tarefas"}: return "Informe tarefas separadas por ponto e vírgula. Exemplo: /executar-plano sistema; calcular 125 x 87"
    if comando.startswith("/executar-plano ") or comando.startswith("/tarefas "):
        prefixo="/executar-plano " if comando.startswith("/executar-plano ") else "/tarefas "
        return sermax_tarefas.executar_plano(mensagem.strip()[len(prefixo):],core=sys.modules[__name__],ferramenta=ferramenta_windows)
    if comando in {"/plano","/planejar","planejar"}: return "Informe o objetivo após /plano. Exemplo: /plano organizar minhas tarefas da semana"
    if comando.startswith("/plano ") or comando.startswith("/planejar "):
        return sermax_planejador.planejar(mensagem.split(" ",1)[1].strip(),modelo=MODELO,url=OLLAMA_URL)
    if comando in {"/memoria","memoria","memória"}:
        if not historico: return "Ainda não há informações guardadas na memória persistente."
        return "Últimas informações guardadas na memória:\n"+"\n".join(f"{i}. {x['content']}" for i,x in enumerate(historico[-10:],1) if str(x.get("content","")).strip())
    if comando.startswith("/memoria ") or comando.startswith("/memória "):
        termo=comando.split(" ",1)[1].strip(); termos=palavras_importantes(termo); achados=[]
        for item in reversed(historico):
            conteudo=str(item.get("content","")).strip()
            if (termos and termos.intersection(palavras_importantes(conteudo))) or (not termos and termo in normalizar(conteudo)): achados.append(conteudo)
            if len(achados)>=10: break
        return "Não encontrei informações guardadas sobre: "+termo if not achados else "Memórias encontradas:\n"+"\n".join(f"{i}. {x}" for i,x in enumerate(achados,1))
    if comando in {"/sistema","sistema","diagnóstico do sistema","diagnostico do sistema"}:
        info=ferramenta_windows.informacoes_sistema(); disco=info.get("disco",{})
        d="indisponível" if "erro" in disco else f"{disco.get('livre_gb','?')} GB livres de {disco.get('total_gb','?')} GB"
        return ("Diagnóstico local do computador:\n"+f"Windows: {info.get('windows','não identificado')}\nArquitetura: {info.get('arquitetura','não identificada')}\nProcessador: {info.get('processador','não identificado')}\nRAM instalada: {info.get('memoria_ram','não disponível')}\nDisco C: {d}")
    if comando in {"/ajuda","ajuda"}:
        return "Comandos: /ajuda, /memoria, /memoria termo, /sistema, /plano objetivo, /executar ação e /executar-plano tarefas. O executor aceita apenas consultas de leitura e cálculos."
    return None

def perguntar(mensagem,receber_parte=None):
    global ultimo_diagnostico_ollama
    mensagem=str(mensagem).strip()
    if not mensagem: return ""
    resposta=responder_comando_local(mensagem)
    if resposta is None: resposta=responder_calculo_local(mensagem)
    if resposta is not None:
        sessao.extend([{"role":"user","content":mensagem},{"role":"assistant","content":resposta}])
        if receber_parte: receber_parte(resposta)
        return resposta
    sessao.append({"role":"user","content":mensagem}); registrar_memoria(mensagem)
    ferramenta=ferramenta_windows.responder_consulta(mensagem)
    if ferramenta is not None:
        sessao.append({"role":"assistant","content":ferramenta})
        if receber_parte: receber_parte(ferramenta)
        return ferramenta
    ultimo_diagnostico_ollama={}
    dados={"model":MODELO,"messages":montar_contexto(mensagem),"stream":True,"keep_alive":KEEP_ALIVE,"options":OPCOES_MODELO}
    pedido=urllib.request.Request(OLLAMA_URL,data=json.dumps(dados,ensure_ascii=False).encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
    resposta=""
    try:
        with urllib.request.urlopen(pedido,timeout=300) as retorno:
            for linha in retorno:
                if not linha: continue
                try: obj=json.loads(linha.decode("utf-8"))
                except json.JSONDecodeError: continue
                trecho=obj.get("message",{}).get("content","")
                if trecho:
                    resposta+=trecho
                    if receber_parte: receber_parte(resposta)
                if obj.get("done"):
                    campos=("load_duration","prompt_eval_duration","eval_duration","total_duration","prompt_eval_count","eval_count")
                    ultimo_diagnostico_ollama={k:obj[k] for k in campos if k in obj}; break
    except urllib.error.URLError as e:
        raise RuntimeError("Não foi possível conectar ao Ollama. Verifique se o Ollama está aberto.") from e
    sessao.append({"role":"assistant","content":resposta})
    return resposta.strip()
