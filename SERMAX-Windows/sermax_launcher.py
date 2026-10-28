import os
import sys
import runpy


def main():
    frozen = bool(getattr(sys, "frozen", False))
    root = os.path.dirname(os.path.abspath(sys.executable)) if frozen else os.path.dirname(os.path.abspath(__file__))
    bundle_root = getattr(sys, "_MEIPASS", root) if frozen else root
    terminal_dir = os.path.join(bundle_root, "SERMAX_terminal")
    terminal_script = os.path.join(terminal_dir, "sermax_terminal.py")
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
