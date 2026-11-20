import os
import sys
import runpy

from sermax_startup_gate import (
    StartupGateError,
    inspect_update_recovery_at_startup,
)


def resolver_caminhos(frozen, executable, arquivo_fonte, meipass=None):
    """Resolve a pasta persistente da instalação e a pasta da interface empacotada."""
    root = os.path.dirname(os.path.abspath(executable if frozen else arquivo_fonte))
    bundle_root = meipass if frozen and meipass else root
    terminal_dir = os.path.join(bundle_root, "SERMAX_terminal")
    terminal_script = os.path.join(terminal_dir, "sermax_terminal.py")
    return root, bundle_root, terminal_dir, terminal_script


def main():
    frozen = bool(getattr(sys, "frozen", False))
    root, bundle_root, terminal_dir, terminal_script = resolver_caminhos(
        frozen,
        sys.executable,
        __file__,
        getattr(sys, "_MEIPASS", None),
    )
    os.environ["SERMAX_ROOT"] = root
    if not os.path.isfile(terminal_script):
        print("SERMAX: não encontrei a interface terminal em:")
        print(terminal_script)
        input("Pressione Enter para fechar.")
        return

    try:
        recovery = inspect_update_recovery_at_startup(root)
    except StartupGateError as erro:
        print("SERMAX: inicialização bloqueada.")
        print("Não foi possível validar a área de atualização com segurança.")
        print(erro)
        print("Nenhum rollback automático foi executado.")
        input("Pressione Enter para fechar.")
        return

    if recovery.get("startup_allowed") is not True:
        print("SERMAX: existe uma atualização interrompida.")
        for item in recovery.get("transactions", ()):
            if item.get("startup_action") == "HOLD_FOR_OPERATOR_DECISION":
                print(
                    "Transação pendente: "
                    + str(item.get("transaction_id", "identificador indisponível"))
                )
                print("Último evento: " + str(item.get("last_event")))
        print("A inicialização normal foi suspensa.")
        print("Nenhum rollback automático foi executado.")
        input("Solicite a recuperação autorizada. Pressione Enter para fechar.")
        return

    if recovery.get("pending_count", 0):
        print("SERMAX: existe preparação de atualização incompleta.")
        print("Os arquivos ativos não foram alterados por essa fase.")
        print("Backup, staging e journal foram preservados para revisão.")
        input("Pressione Enter para continuar.")

    os.chdir(root)
    for path in (root, bundle_root, terminal_dir):
        if path not in sys.path:
            sys.path.insert(0, path)
    runpy.run_path(terminal_script, run_name="__main__")


if __name__ == "__main__":
    main()
