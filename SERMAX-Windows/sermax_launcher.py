import os
import sys
import runpy


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
    os.chdir(root)
    for path in (root, bundle_root, terminal_dir):
        if path not in sys.path:
            sys.path.insert(0, path)
    runpy.run_path(terminal_script, run_name="__main__")


if __name__ == "__main__":
    main()
