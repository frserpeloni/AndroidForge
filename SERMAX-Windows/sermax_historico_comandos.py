# -*- coding: utf-8 -*-
"""Histórico local do SERMAX; arquivo ao lado do núcleo da instalação."""
import datetime
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "historico_comandos.json"
MAX = 100
CONTROLES = ("/historico", "/repetir", "/reiniciar", "/sair", "/ajuda")


def _controle(comando):
    c = str(comando or "").strip().lower()
    return any(c == prefixo or c.startswith(prefixo + " ") for prefixo in CONTROLES)


def carregar():
    try:
        with PATH.open("r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("comandos"), list):
            d["comandos"] = [x for x in d["comandos"] if isinstance(x, dict)]
            return d
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    return {"comandos": []}


def registrar(comando):
    comando = str(comando or "").strip()
    if not comando or _controle(comando):
        return False
    d = carregar()
    itens = d["comandos"]
    if itens and str(itens[0].get("comando", "")) == comando:
        return False
    itens.insert(0, {"comando": comando, "data": datetime.datetime.now().isoformat(timespec="seconds")})
    d["comandos"] = itens[:MAX]
    tmp = PATH.with_suffix(PATH.suffix + ".tmp")
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PATH)
        return True
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def listar(limite=10):
    itens = carregar()["comandos"]
    if not itens:
        return "Ainda não há comandos salvos."
    linhas = ["Histórico persistente (mais recentes primeiro):"]
    for i, x in enumerate(itens[:max(1, min(int(limite), 30))], 1):
        linhas.append(f"{i}. {x.get('comando', '')} [{x.get('data', '')}]")
    linhas.append("Use /repetir ou /repetir N.")
    return "\n".join(linhas)


def obter(indice=1):
    try:
        itens = carregar()["comandos"]
        n = int(indice)
        if 1 <= n <= len(itens):
            comando = str(itens[n - 1].get("comando", "")).strip()
            return comando or None
    except (TypeError, ValueError, KeyError):
        pass
    return None
