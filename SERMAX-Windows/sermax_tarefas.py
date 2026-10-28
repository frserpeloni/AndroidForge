"""Execução sequencial e restrita de tarefas locais do SERMAX.
Sem shell, rede externa, escrita de arquivos ou ações destrutivas.
"""
import re

MAX_TAREFAS = 5
MAX_PLANO = 800


def analisar_plano(texto):
    if not isinstance(texto, str):
        raise ValueError("Plano inválido.")
    texto = texto.strip()
    if not texto or len(texto) > MAX_PLANO:
        raise ValueError("Informe um plano de até 800 caracteres.")
    partes = [p.strip() for p in texto.split(";")]
    if len(partes) > MAX_TAREFAS:
        raise ValueError(f"O plano aceita no máximo {MAX_TAREFAS} tarefas.")
    if any(not p for p in partes):
        raise ValueError("Há uma tarefa vazia no plano.")
    return partes


def _verificar_resultado(acao, resultado):
    if not isinstance(resultado, str) or not resultado.strip():
        return False
    r = resultado.casefold()
    if any(s in r for s in ("não consegui", "nao consegui", "erro:", "falha ao", "não disponível", "nao disponivel")):
        if acao == "sistema" and "diagnóstico local do computador" in r and "disco c:" in r:
            return True
        return False
    if acao == "sistema":
        return "diagnóstico local do computador" in r and "windows:" in r and "disco c:" in r
    if acao == "memoria":
        return "memórias encontradas" in r or "não encontrei informações guardadas" in r or "nao encontrei informacoes guardadas" in r
    if acao == "calcular":
        return "resultado:" in r or "dividir por zero" in r
    return False


def executar_plano(texto, *, core, ferramenta=None):
    """Executa no máximo cinco consultas/cálculos explícitos; para na primeira falha."""
    try:
        tarefas = analisar_plano(texto)
    except ValueError as erro:
        return str(erro)
    saidas = [f"Plano local: {len(tarefas)} tarefa(s). Execução sequencial iniciada."]
    for indice, tarefa in enumerate(tarefas, 1):
        try:
            pedido = core.sermax_executor.analisar_pedido(tarefa)
        except ValueError as erro:
            saidas.append(f"{indice}. INTERROMPIDO: {erro}")
            saidas.append("As tarefas seguintes não foram executadas.")
            return "\n".join(saidas)
        acao = pedido["acao"]
        resultado = core.sermax_executor.executar(tarefa, core=core, ferramenta=ferramenta)
        if not _verificar_resultado(acao, resultado):
            saidas.append(f"{indice}. FALHA NA VERIFICAÇÃO ({acao}): {resultado}")
            saidas.append("Execução interrompida para evitar continuar com resultado incerto.")
            return "\n".join(saidas)
        saidas.append(f"{indice}. APROVADO ({acao}): {resultado}")
    saidas.append("Plano concluído: todas as tarefas passaram pela verificação local.")
    return "\n".join(saidas)
