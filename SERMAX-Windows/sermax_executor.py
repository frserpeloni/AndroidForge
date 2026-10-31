"""Executor local restrito do SERMAX. Sem shell, rede externa ou escrita de arquivos."""
ACOES_PERMITIDAS = {"sistema", "memoria", "calcular"}
MAX_ENTRADA = 240


def analisar_pedido(texto):
    if not isinstance(texto, str):
        raise ValueError("Pedido inválido.")
    texto = texto.strip()
    if not texto or len(texto) > MAX_ENTRADA or any(ord(c) < 32 for c in texto):
        raise ValueError("Informe uma ação válida de até 240 caracteres.")
    if any(c in texto for c in ";&|`<>$\\"):
        raise ValueError("Caracteres de comando não são permitidos.")
    partes = texto.split(maxsplit=1)
    acao = partes[0].lower()
    argumento = partes[1].strip() if len(partes) > 1 else ""
    if acao not in ACOES_PERMITIDAS:
        raise ValueError("Ação não permitida. Use: sistema, memoria <termo> ou calcular <conta>.")
    if acao == "memoria" and not argumento:
        raise ValueError("Informe o termo da memória. Exemplo: memoria Siena")
    if acao == "calcular" and not argumento:
        raise ValueError("Informe uma conta. Exemplo: calcular 125 x 87")
    if acao == "sistema" and argumento:
        raise ValueError("A ação sistema não aceita argumentos.")
    return {"acao": acao, "argumento": argumento}


def executar(pedido, *, core, ferramenta):
    try:
        item = analisar_pedido(pedido)
    except ValueError as erro:
        return str(erro)
    acao, argumento = item["acao"], item["argumento"]
    if acao == "sistema":
        return core.responder_comando_local("/sistema")
    if acao == "memoria":
        return core.responder_comando_local("/memoria " + argumento)
    if acao == "calcular":
        resultado = core.responder_calculo_local(argumento)
        return resultado if resultado is not None else "Conta não reconhecida. Nenhuma ação foi executada."
    return "Ação não permitida."
