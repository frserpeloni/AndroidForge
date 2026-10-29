"""Terminal SERMAX de contingência para integração Windows.
Preserva execução em console e encaminha mensagens ao núcleo local.
A versão visual original deve substituir este arquivo após conferência byte a byte com o backup.
"""
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("SERMAX_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import sermax_core as core
except Exception as exc:
    print("SERMAX: não foi possível carregar o núcleo.")
    print(f"Detalhe: {type(exc).__name__}: {exc}")
    input("Pressione Enter para fechar.")
    raise SystemExit(1)

def _diagnostico():
    print("SERMAX — terminal de integração")
    print("Raiz:", ROOT)
    print("Memória:", core.ARQUIVO_MEMORIA)
    print("Comandos: /ajuda, /memoria, /memoria termo, /sistema, /plano objetivo, /executar ação")
    print("Aviso: interface de contingência; o rosto original ainda precisa ser restaurado.")

def main():
    _diagnostico()
    while True:
        try:
            mensagem = input("\nSERMAX > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando SERMAX.")
            break
        if not mensagem:
            continue
        if mensagem.lower() in {"/sair", "sair", "exit", "quit"}:
            print("Encerrando SERMAX.")
            break
        inicio = time.perf_counter()
        try:
            resposta = core.perguntar(mensagem)
            if resposta:
                print("\n" + str(resposta))
        except Exception as exc:
            print(f"Erro: {type(exc).__name__}: {exc}")
            traceback.print_exc()
        finally:
            print(f"[tempo: {time.perf_counter()-inicio:.2f}s]")

if __name__ == "__main__":
    main()
