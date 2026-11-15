"""SERMAX setup wizard. Development preview, not a distributable installer."""
from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from sermax_installer_core import install_package, package_snapshot, preflight


def close_block_message(busy: bool) -> str | None:
    """Return the user-facing reason to block closing during installation."""
    if busy:
        return "Aguarde o término da operação antes de fechar o assistente."
    return None


class SermaxSetup(tk.Tk):
    def __init__(self, package: Path | None):
        super().__init__()
        self.title("Instalação do SERMAX")
        self.geometry("610x420")
        self.minsize(610, 420)
        self.configure(bg="#f2f3f5")
        self.package = tk.StringVar(value=str(package or ""))
        self.destination = tk.StringVar(value=str(Path.home() / "SERMAX"))
        self.mode = tk.StringVar(value="Detecção automática")
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    def _build(self):
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="SERMAX", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Assistente de instalação e atualização").pack(anchor="w", pady=(0, 14))

        ttk.Label(outer, text="Tipo de operação").pack(anchor="w")
        ttk.Combobox(outer, textvariable=self.mode, state="readonly",
                     values=["Detecção automática", "Instalação inicial", "Atualização existente"]).pack(fill="x", pady=(3, 10))

        ttk.Label(outer, text="Pasta do pacote").pack(anchor="w")
        line = ttk.Frame(outer)
        line.pack(fill="x", pady=(3, 10))
        ttk.Entry(line, textvariable=self.package).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Procurar...", command=self._choose_package).pack(side="left", padx=(8, 0))

        ttk.Label(outer, text="Pasta de instalação").pack(anchor="w")
        line = ttk.Frame(outer)
        line.pack(fill="x", pady=(3, 10))
        ttk.Entry(line, textvariable=self.destination).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Alterar...", command=self._choose_destination).pack(side="left", padx=(8, 0))

        self.status = tk.StringVar(value="Aguardando seleção do pacote.")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(5, 5))
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        self.details = tk.Text(outer, height=7, state="disabled", wrap="word")
        self.details.pack(fill="both", expand=True, pady=(10, 12))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.install_button = ttk.Button(buttons, text="Verificar e instalar", command=self._start)
        self.install_button.pack(side="right")
        self.close_button = ttk.Button(buttons, text="Fechar", command=self._on_close)
        self.close_button.pack(side="right", padx=(0, 8))

    def _on_close(self):
        reason = close_block_message(self.busy)
        if reason:
            messagebox.showwarning("Instalação em andamento", reason)
            return
        self.destroy()

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
            confirmed_snapshot = package_snapshot(package, destination)
            if (report["version"] != confirmed_snapshot["version"] or
                    report["file_count"] != len(confirmed_snapshot["files"])):
                raise RuntimeError("O pacote mudou durante a verificação. Repita a operação.")
        except Exception as exc:
            messagebox.showerror("Verificação do pacote", str(exc))
            return

        installed = report["installation"]
        detected = "Atualização existente" if installed["installed"] else "Instalação inicial"
        selected = self.mode.get()
        if selected == "Detecção automática":
            selected = detected
        if selected == "Instalação inicial" and installed["installed"]:
            messagebox.showerror("Instalação inicial", "Já existe uma instalação nesta pasta. Escolha outro destino ou selecione atualização.")
            return
        if selected == "Atualização existente" and not installed["installed"]:
            messagebox.showerror("Atualização", "Nenhuma instalação SERMAX foi identificada nesta pasta.")
            return

        current_version = installed.get("version") or "não identificada"
        summary = (
            f"Operação: {selected}\n"
            f"Versão do pacote: {report['version']}\n"
            f"Versão instalada: {current_version}\n"
            f"Arquivos: {report['file_count']}\n"
            f"Espaço necessário: {report['required_bytes']:,} bytes\n\n"
            "Os arquivos substituídos terão backup. Arquivos fora do manifesto serão preservados. Prosseguir?"
        )
        if not messagebox.askyesno("Confirmar operação", summary):
            return

        self.mode.set(selected)
        self.busy = True
        self.install_button.configure(state="disabled")
        self.close_button.configure(state="disabled")
        self.progress.configure(value=0)
        self.status.set("Preparando instalação...")
        self._log(f"Iniciando {selected} em {destination}")
        threading.Thread(target=self._worker, args=(package, destination, confirmed_snapshot), daemon=True).start()

    def _worker(self, package: Path, destination: Path, expected_snapshot: dict):
        try:
            def on_progress(phase, current, total, name):
                self.events.put(("progress", (phase, current, total, name)))
            result = install_package(package, destination, progress=on_progress,\n                                      expected_snapshot=expected_snapshot)
            self.events.put(("success", result))
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    phase, current, total, name = payload
                    percent = int((current / total) * 100) if total else 0
                    self.progress.configure(value=percent)
                    labels = {
                        "preparing": "Preparando arquivos...",
                        "staging": "Validando e preparando cópias...",
                        "installing": "Instalando arquivos...",
                        "complete": "Finalizando..."
                    }
                    self.status.set(f"{labels.get(phase, phase)} {percent}%")
                    if name:
                        self._log(f"{phase}: {name}")
                    continue

                self.busy = False
                self.install_button.configure(state="normal")
                self.close_button.configure(state="normal")
                if kind == "success":
                    self.progress.configure(value=100)
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
        self.after(100, self._poll)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    SermaxSetup(args.package).mainloop()


if __name__ == "__main__":
    main()
