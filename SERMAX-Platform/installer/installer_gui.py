"""SERMAX graphical setup wizard (Windows Tkinter).

Run from a prepared package with:
    py installer_gui.py --package <package-folder>
This is a development preview, not a signed/distributable setup executable.
"""
from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from sermax_installer_core import PackageError, install_package, preflight


class SermaxSetup(tk.Tk):
    def __init__(self, package: Path | None):
        super().__init__()
        self.title("Instalação do SERMAX")
        self.geometry("590x390")
        self.minsize(590, 390)
        self.configure(bg="#f2f3f5")
        self.package = tk.StringVar(value=str(package or ""))
        self.destination = tk.StringVar(value=str(Path.home() / "SERMAX"))
        self.mode = tk.StringVar(value="Instalação / Atualização")
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self._build()
        self.after(120, self._poll)

    def _build(self):
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="SERMAX", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Assistente de instalação e atualização",
                  font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 16))

        ttk.Label(outer, text="Tipo de operação").pack(anchor="w")
        ttk.Combobox(outer, textvariable=self.mode, state="readonly",
                     values=["Instalação inicial", "Atualização existente"]).pack(fill="x", pady=(3, 12))

        ttk.Label(outer, text="Pasta do pacote").pack(anchor="w")
        line = ttk.Frame(outer)
        line.pack(fill="x", pady=(3, 12))
        ttk.Entry(line, textvariable=self.package).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Procurar...", command=self._choose_package).pack(side="left", padx=(8, 0))

        ttk.Label(outer, text="Pasta de instalação").pack(anchor="w")
        line = ttk.Frame(outer)
        line.pack(fill="x", pady=(3, 14))
        ttk.Entry(line, textvariable=self.destination).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Alterar...", command=self._choose_destination).pack(side="left", padx=(8, 0))

        self.status = tk.StringVar(value="Aguardando seleção do pacote.")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(4, 5))
        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x")
        self.details = tk.Text(outer, height=5, state="disabled", wrap="word")
        self.details.pack(fill="both", expand=True, pady=(10, 12))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.install_button = ttk.Button(buttons, text="Verificar e instalar", command=self._start)
        self.install_button.pack(side="right")
        ttk.Button(buttons, text="Fechar", command=self.destroy).pack(side="right", padx=(0, 8))

    def _choose_package(self):
        selected = filedialog.askdirectory(title="Selecione a pasta do pacote SERMAX")
        if selected:
            self.package.set(selected)

    def _choose_destination(self):
        selected = filedialog.askdirectory(title="Selecione a pasta de instalação")
        if selected:
            self.destination.set(selected)

    def _log(self, line: str):
        self.details.configure(state="normal")
        self.details.insert("end", line + "\n")
        self.details.see("end")
        self.details.configure(state="disabled")

    def _start(self):
        if self.busy:
            return
        package = Path(self.package.get()).expanduser()
        destination = Path(self.destination.get()).expanduser()
        try:
            report = preflight(package, destination)
        except Exception as exc:
            messagebox.showerror("Verificação do pacote", str(exc))
            return
        summary = (
            f"Versão: {report['version']}\n"
            f"Arquivos: {report['file_count']}\n"
            f"Espaço necessário: {report['required_bytes']:,} bytes\n\n"
            "Os arquivos existentes que forem substituídos terão backup. "
            "Arquivos fora do manifesto serão preservados. Prosseguir?"
        )
        if not messagebox.askyesno("Confirmar operação", summary):
            return
        self.busy = True
        self.install_button.configure(state="disabled")
        self.progress.start(12)
        self.status.set("Instalando arquivos do pacote...")
        self._log(f"Iniciando {self.mode.get()} para {destination}")
        threading.Thread(target=self._worker, args=(package, destination), daemon=True).start()

    def _worker(self, package: Path, destination: Path):
        try:
            result = install_package(package, destination)
            self.events.put(("success", result))
        except (PackageError, OSError, Exception) as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self.progress.stop()
                self.busy = False
                self.install_button.configure(state="normal")
                if kind == "success":
                    self.status.set("Operação concluída.")
                    self._log(f"Versão instalada: {payload['version']}")
                    self._log(f"Arquivos instalados: {payload['installed_files']}")
                    self._log(f"Backup: {payload['backup_directory'] or 'não necessário'}")
                    messagebox.showinfo("SERMAX", "Operação concluída. Consulte os detalhes.")
                else:
                    self.status.set("Falha na operação.")
                    self._log(payload)
                    messagebox.showerror("Falha na instalação", payload)
        except queue.Empty:
            pass
        self.after(120, self._poll)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    SermaxSetup(args.package).mainloop()


if __name__ == "__main__":
    main()
