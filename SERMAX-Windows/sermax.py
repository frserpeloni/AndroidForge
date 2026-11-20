import os
import time
import sermax_core

ARQUIVO_DIAGNOSTICO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "diagnostico_velocidade_sermax.txt",
)


def registrar_diagnostico(pergunta, inicio, primeira_saida, fim):
    """Registra tempos, sem salvar pergunta nem resposta do usuário."""
    primeira = "sem saída" if primeira_saida is None else f"{primeira_saida:.2f} s"
    total = f"{fim - inicio:.2f} s"
    metricas = getattr(sermax_core, "ultimo_diagnostico_ollama", {}) or {}
    def segundos(chave):
        valor = metricas.get(chave)
        return "n/d" if valor is None else f"{valor / 1_000_000_000:.2f} s"
    linha = (
        f"Primeira saída: {primeira} | Tempo total: {total}"
        f" | Carga modelo: {segundos('load_duration')}"
        f" | Avaliação prompt: {segundos('prompt_eval_duration')}"
        f" | Geração: {segundos('eval_duration')}"
        f" | Tokens prompt: {metricas.get('prompt_eval_count', 'n/d')}"
        f" | Tokens gerados: {metricas.get('eval_count', 'n/d')}\n"
    )
    try:
        with open(ARQUIVO_DIAGNOSTICO, "a", encoding="utf-8") as arquivo:
            arquivo.write(linha)
    except OSError:
        pass
    print(f"\n[Diagnóstico] Primeira saída: {primeira} | Total: {total}")
    if metricas:
        print(
            "[Ollama] Carga: " + segundos("load_duration")
            + " | Prompt: " + segundos("prompt_eval_duration")
            + " | Geração: " + segundos("eval_duration")
        )


def main():
    print("SERMAX v1.6 iniciado.")
    print("Digite sair para encerrar.")

    while True:
        try:
            mensagem = input("Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSERMAX encerrado.")
            break
        except OSError as erro:
            if getattr(erro, "winerror", None) == 6 or getattr(erro, "errno", None) == 9:
                print(
                    "\nSERMAX: O console perdeu o acesso à entrada. "
                    "Feche esta janela e inicie novamente pelo PowerShell."
                )
                break
            print(f"\nSERMAX: Falha ao ler a entrada: {erro}")
            break

        if mensagem.lower() in {"sair", "/sair", "/bye", "bye", "exit", "quit"}:
            print("SERMAX: Até logo, Fabiano.")
            break

        if not mensagem:
            continue

        inicio = time.perf_counter()
        primeira_saida = None
        tamanho_exibido = 0
        print("SERMAX: ", end="", flush=True)

        def mostrar_parte(resposta_acumulada):
            nonlocal primeira_saida, tamanho_exibido
            if not resposta_acumulada:
                return
            parte_nova = resposta_acumulada[tamanho_exibido:]
            if not parte_nova:
                return
            if primeira_saida is None:
                primeira_saida = time.perf_counter() - inicio
            print(parte_nova, end="", flush=True)
            tamanho_exibido = len(resposta_acumulada)

        try:
            resposta = sermax_core.perguntar(mensagem, receber_parte=mostrar_parte)
            fim = time.perf_counter()
            if resposta and tamanho_exibido == 0:
                print(resposta, end="", flush=True)
                primeira_saida = fim - inicio
            print()
            registrar_diagnostico(mensagem, inicio, primeira_saida, fim)
        except Exception as erro:
            fim = time.perf_counter()
            print("\nSERMAX: Erro:", erro)
            registrar_diagnostico(mensagem, inicio, primeira_saida, fim)


if __name__ == "__main__":
    main()
