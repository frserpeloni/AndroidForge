import os
import sys

# Localiza o C:\SERMAX, que está uma pasta acima do Terminal
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sermax_core
import sermax_historico_comandos as _sermax_hist
import subprocess
import time
import sermax_integracao_comandos  # SERMAX_V310_INTEGRACAO
from sermax_voz import transcrever_arquivo, localizar_whisper_e_modelo, diagnostico_voz

COLS = 120
ROWS = 42

FACE_COLS = 70
PANEL_COLS = 44
TOP_ROWS = 29
CHAT_ROWS = 9

GREEN = "\033[92m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

ROSTO = r"""
                  .                .... . ..:.:.:...+.:.:           :.          .:
  :       .       :              :.::.: :.:...        ::+.+         +:          :+
  :       :       :            +.:::. : .           :.:.+:+:+.      :   ..      :+       :
  :       :       :         .:.: . ..             .   ..::++*++.    :   ..      :+       :
  +       +      :*:      .+:+.+ +:                 :.+:+.:.+:*+*:  :   ..      :*       +
  :       +.      :     ::.. : .        .               ..*++:::::+.    ..      .+       +.
  +      .*:      +   :.+....:        :           ::+:+.:.:.::*+++*+:   ..      :+      .*.
 .*:      +       : ..+:. .:                            ..+.: ::++*+*+  ..      :*      .*.
 .+.      +       ..+.+...                        ..:.:.:...:.:...::+:+         .+       +.
 .*.      +       ::*.+.+.                    . : : .:::+:+::.+:+:++*+*+.      . +      .*.
 .*.      :     .:*:+..                                 . ::+++:+:+:+:++*:     . :       :
 .+.      :    .:.+.+   .               . :.::+::.::::*:+.. ..:.:.+:::+:++:      :       +
  +       +    :*:+.  .             ..+.:.+..           .:*::.:.::+:+:++**+.     +       +
  +       :  .*::.: .            ..::.:.                    ++*:. :.+:+:++++     +       +
  +       :  :+::            ..+.::.                          ..*::.:.+:::+::    +       +
  +         +:*..   .     .:.+..                      .         ..*++.:.++*+*+   +       +
  .        :+.:   .     ..::                    .   .   .         .:+.. ..::++   :       +.
          +:*.:     . +.:.                      .   .               +:+:..::++.  +      .*.
  +.    .:+.: .   ..+..               :         .   .                 ::+:.:++:. :      .*.
 .+.   .:.:     ..+..                           .   . . . : :           ::...::: :       +.
 .+.   :+.+ . :.+                               . :.::+::         .       ++:::+.        +
  .   +.: . :.+         ..  ..              : ..:.:               .        .+:.:+:       :
  .  .+.:.+.:           .:  .**#**+.        :.: :       .:++*:    :          ::::*       +
    ::+.+..             .:    :##%%%%*:     :.+     :*#%%%%*:   . .           :++*.      :
    +.:.:               ..      .::++++:    ..+    .+++++::     . .             .::+     :
   .*:+.              :  .                  :.* .           :   : :              *.+    .*:
   .*.:                 .. :        .       ..*:+ . . : : : :   :                .:*:    :
   .+..                  . :                :.+::.: : . . : .   :                 .+:    +
    +.:                  +.+ . .    .       ::*++.+:+:+.+.*.. +                   :*:    +
     .*.                  :: :      .       ::*++.+:+.:.+.: . +                  ..+     :
      +..                  : :              ::*++.+::.:.+ . : .                  ..+     :
       :*.        .         :* :          . ++*++:::+.:.: :.*.                  :*.      +
    .   ..+ .               .+:+    .           . +.:.: . +.                  .:::       :
. ..+..   +::                .:*.:            :.+:+::.: :.+                   ++:        :
+:+.:      .+.+                .:*:.          . ....+ ::*.              .   :+: :+.:
: .          .*.+                +:::         :.:.:.:.+.              .   ..+:   ..::*:+.:
: .            .+.:                ++ .         . :.+..                 ..++   . : :.:.+:+::
::* .            .*.:               :+*       :.+.+::   .     .         *+    ...::+.:.:.:.+
    + :             *..              .+:+     ::+::     .     .       +:       ..:..   . : +
      +       :      .*.        .      .+::.. .:+.    .     .       +..      . .:+     : . :
             .*        .+:       :.       ..:.:      ..         . +:.       ...:.    .   +.:
             .:   .      .::      :                 :           +::         ....       . +.:
             .*            :..     :.              ..   .     *::     :     ::       :.: :
              .     .        :      ..            .       . . .       :                . .
  .           + :   :          +     :.          ..       + :       . :.  ..           . .
"""


def reduzir_rosto(texto, linhas_alvo=25, colunas_alvo=66):
    linhas = texto.splitlines()

    while linhas and not linhas[0].strip():
        linhas.pop(0)

    while linhas and not linhas[-1].strip():
        linhas.pop()

    if not linhas:
        return []

    altura = len(linhas)
    largura = max(len(linha) for linha in linhas)

    resultado = []

    for y in range(linhas_alvo):
        oy = min(altura - 1, int(y * altura / linhas_alvo))
        linha = linhas[oy].ljust(largura)

        resultado.append(
            "".join(
                linha[
                    min(
                        largura - 1,
                        int(x * largura / colunas_alvo)
                    )
                ]
                for x in range(colunas_alvo)
            ).rstrip()
        )

    return resultado


ROSTO_REDUZIDO = reduzir_rosto(ROSTO)


def cortar(texto, largura):
    texto = str(texto)

    if len(texto) <= largura:
        return texto

    return texto[:max(0, largura - 1)] + "…"


def quebrar(texto, largura):
    resultado = []

    for bloco in str(texto).replace("\r", "").split("\n"):

        if not bloco:
            resultado.append("")
            continue

        palavras = bloco.split()
        atual = ""

        for palavra in palavras:

            if len(palavra) > largura:

                if atual:
                    resultado.append(atual)
                    atual = ""

                for i in range(0, len(palavra), largura):
                    resultado.append(
                        palavra[i:i + largura]
                    )

            elif not atual:
                atual = palavra

            elif len(atual) + 1 + len(palavra) <= largura:
                atual += " " + palavra

            else:
                resultado.append(atual)
                atual = palavra

        if atual:
            resultado.append(atual)

    return resultado


def preparar_terminal():

    if os.name == "nt":

        os.system(
            f"mode con: cols={COLS} lines={ROWS} >nul 2>&1"
        )

        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            h = k32.GetStdHandle(-11)

            mode = ctypes.c_uint32()

            if k32.GetConsoleMode(
                h,
                ctypes.byref(mode)
            ):
                k32.SetConsoleMode(
                    h,
                    mode.value | 0x0004
                )

        except Exception:
            pass

    os.system("title SERMAX - Terminal de IA")


def painel():

    w = PANEL_COLS

    itens = [
        " SERMAX",
        " --------------------------------------",
        " INTELIGENCIA ARTIFICIAL",
        "",
        " [ ONLINE ]",
        "",
        " MODELO",
        " QWEN 2.5 1.5B",
        "",
        " SISTEMA",
        " OLLAMA",
        "",
        " USUARIO",
        " FABIANO",
        "",
        " COMANDOS",
        " /limpar",
        " /modelo",
        " /ajuda",
        " /voz <arquivo.wav>",
        " /sair",
    ]

    linhas = [
        "+" + "-" * (w - 2) + "+"
    ]

    for item in itens:
        linhas.append(
            "|" +
            cortar(item, w - 2).ljust(w - 2) +
            "|"
        )

    while len(linhas) < TOP_ROWS - 1:

        linhas.append(
            "|" +
            " " * (w - 2) +
            "|"
        )

    return linhas[:TOP_ROWS - 1]


def render(conversa):

    tela = []

    tela.append(
        " SERMAX - Terminal de IA".ljust(COLS)
    )

    tela.append("-" * COLS)

    rosto = ROSTO_REDUZIDO[:TOP_ROWS - 2]

    p = painel()

    for i in range(TOP_ROWS - 2):

        esquerda = cortar(
            rosto[i] if i < len(rosto) else "",
            FACE_COLS
        ).ljust(FACE_COLS)

        direita = (
            p[i]
            if i < len(p)
            else "|" +
            " " * (PANEL_COLS - 2) +
            "|"
        )

        tela.append(
            (
                " " +
                esquerda +
                " " +
                direita
            ).ljust(COLS)
        )

    tela.append(
        "+" +
        "-" * (COLS - 2) +
        "+"
    )

    tela.append(
        "|" +
        " CONVERSA".ljust(COLS - 2) +
        "|"
    )

    tela.append(
        "|" +
        "-" * (COLS - 2) +
        "|"
    )

    largura = COLS - 5
    capacidade = CHAT_ROWS - 1

    chat_reverso = []

    for item in reversed(conversa):

        prefixo = (
            "Você: "
            if item["role"] == "user"
            else "SERMAX: "
        )

        partes = quebrar(
            item["content"],
            largura - len(prefixo)
        ) or [""]

        linhas_item = [
            prefixo + partes[0]
        ]

        linhas_item.extend(
            " " * len(prefixo) + x
            for x in partes[1:]
        )

        for linha in reversed(linhas_item):

            chat_reverso.append(linha)

            if len(chat_reverso) >= capacidade:
                break

        if len(chat_reverso) >= capacidade:
            break

    chat = list(reversed(chat_reverso))

    chat = (
        [""] * (capacidade - len(chat))
        + chat
    )

    for item in chat:

        tela.append(
            "|" +
            " " +
            cortar(
                item,
                COLS - 4
            ).ljust(COLS - 4) +
            " |"
        )

    tela.append(
        "+" +
        "-" * (COLS - 2) +
        "+"
    )

    assert len(tela) == ROWS - 1

    assert all(
        len(line) == COLS
        for line in tela
    )

    return "\n".join(tela)


def desenhar(conversa):

    tela = render(conversa)

    sys.stdout.write(
        CLEAR +
        HIDE_CURSOR +
        GREEN +
        tela +
        RESET +
        "\n" +
        SHOW_CURSOR
    )

    sys.stdout.flush()


def consultar(pergunta, conversa):

    conversa_temp = conversa + [
        {
            "role": "user",
            "content": pergunta
        },
        {
            "role": "assistant",
            "content": ""
        }
    ]

    def atualizar(resposta_atual):

        conversa_temp[-1]["content"] = resposta_atual

        desenhar(conversa_temp)

    try:

        resposta = sermax_core.perguntar(
            pergunta,
            receber_parte=atualizar
        )

        conversa.extend([
            {
                "role": "user",
                "content": pergunta
            },
            {
                "role": "assistant",
                "content": resposta
            }
        ])

        return resposta

    except Exception as erro:

        resposta = "Erro no SERMAX: " + str(erro)

        conversa.extend([
            {
                "role": "user",
                "content": pergunta
            },
            {
                "role": "assistant",
                "content": resposta
            }
        ])

        return resposta

def main():
    preparar_terminal()
    conversa = []

    try:
        desenhar(conversa)

        while True:
            pergunta = input(
                GREEN + " Você: " + RESET
            ).strip()

            if not pergunta:
                desenhar(conversa)
                continue

            cmd = pergunta.lower()
            # Comandos de controle são tratados antes do registro; nunca entram no histórico.
            if cmd == "/historico":
                conversa.extend([{"role": "user", "content": pergunta},
                                 {"role": "assistant", "content": _sermax_hist.listar()}])
                desenhar(conversa)
                continue

            if cmd == "/repetir" or cmd.startswith("/repetir "):
                partes = pergunta.split(maxsplit=1)
                repetida = _sermax_hist.obter(partes[1] if len(partes) > 1 else 1)
                if not repetida or repetida.strip().lower().split(maxsplit=1)[0] in {"/sair", "/reiniciar", "/historico", "/repetir"}:
                    mensagem = "Não há solicitação repetível nessa posição."
                    conversa.extend([{"role": "user", "content": pergunta}, {"role": "assistant", "content": mensagem}])
                    desenhar(conversa)
                    continue
                conversa.extend([{"role": "user", "content": pergunta}, {"role": "assistant", "content": "Repetindo solicitação: " + repetida}])
                if repetida.lower().startswith("/plano "):
                    try:
                        import sermax_planejador as _sp
                        conversa.append({"role": "assistant", "content": str(_sp.planejar(repetida[6:].strip()))})
                    except Exception as erro:
                        conversa.append({"role": "assistant", "content": "Falha ao repetir planejamento: " + str(erro)})
                elif repetida.startswith("/"):
                    conversa.append({"role": "assistant", "content": "O histórico recuperou um comando especial. Por segurança, digite-o diretamente para executá-lo."})
                else:
                    consultar(repetida, conversa)
                desenhar(conversa)
                continue

            if cmd == "/reiniciar":
                try:
                    script = os.path.abspath(__file__)
                    if getattr(sys, "frozen", False):
                        raiz = os.path.dirname(os.path.abspath(sys.executable))
                    else:
                        raiz = os.path.dirname(os.path.dirname(script))
                    if os.name != "nt":
                        raise RuntimeError("O reinício de janela precisa ser validado no Windows.")
                    if getattr(sys, "frozen", False):
                        comando = [sys.executable]
                    else:
                        comando = [sys.executable, script]
                    child = subprocess.Popen(
                        comando, cwd=raiz,
                        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                        close_fds=True
                    )
                    time.sleep(0.8)
                    if child.poll() is not None:
                        raise RuntimeError("A nova instância encerrou imediatamente (código %s)." % child.returncode)
                except Exception as erro:
                    conversa.extend([{"role": "user", "content": pergunta},
                                     {"role": "assistant", "content": "Não foi possível reiniciar; esta janela continuará aberta. Erro: " + str(erro)}])
                    desenhar(conversa)
                    continue
                print("Nova instância iniciada. Encerrando esta sessão...")
                break

            # Ponto único de registro para entradas que não são comandos de controle.
            if cmd not in {"/sair", "sair", "exit", "quit"}:
                _sermax_hist.registrar(pergunta)

            if cmd == "/vozdiag":
                estado = diagnostico_voz()
                mensagem = (
                    "Diagnostico de voz local\n"
                    f"Whisper: {estado['whisper'] or 'NAO ENCONTRADO'}\n"
                    f"Modelo: {estado['modelo'] or 'NAO ENCONTRADO'}\n"
                    f"Pronto: {'SIM' if estado['pronto'] else 'NAO'}"
                )
                conversa.extend([
                    {"role": "user", "content": pergunta},
                    {"role": "assistant", "content": mensagem}
                ])
                desenhar(conversa)
                continue

            if cmd == "/voz" or cmd.startswith("/voz "):
                argumento = pergunta[4:].strip()
                if not argumento:
                    exe, modelo = localizar_whisper_e_modelo()
                    if exe and modelo:
                        mensagem = (
                            "Reconhecimento local disponível para arquivo WAV.\n"
                            "Uso: /voz \"caminho completo do arquivo.wav\"\n"
                            "Microfone ao vivo ainda não está ativado."
                        )
                    else:
                        mensagem = (
                            "Whisper ou modelo não localizado. Verifique a instalação existente; "
                            "nenhum download será iniciado automaticamente."
                        )
                    conversa.extend([
                        {"role": "user", "content": pergunta},
                        {"role": "assistant", "content": mensagem}
                    ])
                    desenhar(conversa)
                    continue

                caminho_audio = argumento.strip().strip('\"')
                if not os.path.isfile(caminho_audio):
                    mensagem = "Arquivo de áudio não encontrado: " + caminho_audio
                    conversa.extend([
                        {"role": "user", "content": pergunta},
                        {"role": "assistant", "content": mensagem}
                    ])
                    desenhar(conversa)
                    continue

                try:
                    texto_voz = transcrever_arquivo(caminho_audio)
                    if not texto_voz or not texto_voz.strip():
                        raise RuntimeError("O Whisper não retornou uma transcrição. Verifique o WAV e o log de voz.")
                    # Encaminha o texto reconhecido ao núcleo, como uma entrada normal.
                    consultar(texto_voz.strip(), conversa)
                except Exception as erro:
                    conversa.extend([
                        {"role": "user", "content": pergunta},
                        {"role": "assistant", "content": "Falha no reconhecimento de voz: " + str(erro)}
                    ])
                desenhar(conversa)
                continue

            # SERMAX_V310_INTEGRACAO: comandos modulares seguros
            if sermax_integracao_comandos.processar(pergunta, conversa, sermax_core):
                desenhar(conversa)
                continue

            if cmd == "/sair":
                break

            if cmd == "/limpar":
                conversa.clear()
                desenhar(conversa)
                continue

            if cmd == "/modelo":
                conversa.extend([
                    {
                        "role": "user",
                        "content": pergunta
                    },
                    {
                        "role": "assistant",
                        "content": "Modelo atual: qwen2.5:1.5b"
                    }
                ])

                desenhar(conversa)
                continue

            if cmd == "/ajuda":
                conversa.extend([
                    {
                        "role": "user",
                        "content": pergunta
                    },
                    {
                        "role": "assistant",
                        "content": (
                            "Comandos: /limpar, /modelo, /ajuda, /memoria, /voz <arquivo.wav> e /sair. "
                            "Recursos locais: calculadora e consultas do Windows. "
                            "Perguntas gerais usam o cérebro local SERMAX."
                        )
                    }
                ])

                desenhar(conversa)
                continue

            consultar(
                pergunta,
                conversa
            )

            desenhar(conversa)

    except KeyboardInterrupt:
        pass

    finally:
        sys.stdout.write(
            SHOW_CURSOR +
            RESET +
            "\n"
        )
        sys.stdout.flush()


if __name__ == "__main__":
    main()