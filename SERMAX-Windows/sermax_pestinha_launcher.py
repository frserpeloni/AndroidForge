"""Inicializador opcional da interface completa do Pestinha, isolada do terminal SERMAX."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from sermax_pestinha.pestinha import config, store
from sermax_pestinha.pestinha.paths import Paths
from sermax_pestinha.pestinha.settings_store import SettingsStore
from sermax_pestinha.pestinha.app import PestinhaApp
from sermax_pestinha.pestinha.ui.onboarding import Onboarding
from sermax_pestinha.pestinha.ui.ui import SettingsDialog, face_icon


def _pestinha_root() -> Path:
    configured = os.environ.get("SERMAX_PESTINHA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "sermax_pestinha"
    return Path(__file__).resolve().parent / "sermax_pestinha"


def apagar_memoria(paths: Paths):
    """Apaga somente os dados do subsistema Pestinha, nunca a memória SERMAX."""
    falhas = store.apagar_pasta(paths.memory) if paths.memory.exists() else []
    return not falhas and not paths.memory.exists(), falhas


def main(argv=None):
    parser = argparse.ArgumentParser(description="SERMAX, interface complementar Pestinha")
    parser.add_argument("--direto", action="store_true", help="usa as permissões já salvas")
    parser.add_argument("--sair-em", type=float, default=0.0, help="fecha após N segundos, para testes")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(face_icon())

    paths = Paths(root=_pestinha_root())
    settings = SettingsStore(paths)
    perms = settings.perms
    if not args.direto:
        first_time = not paths.permissions.exists()
        if first_time:
            pet_id = config.escolher_pet(paths, perms["pet"])
            pet = config.load_pet(paths, pet_id)
            Onboarding(pet["nome"]).exec()
        dialog = SettingsDialog(perms, paths, first_run=True)
        dialog.changed.connect(settings.update)

        def wipe():
            success, failures = apagar_memoria(paths)
            if not success:
                detail = "\\n\\nArquivos que falharam: " + ", ".join(failures) if failures else ""
                QMessageBox.warning(
                    dialog, "Não foi possível apagar tudo",
                    "Alguns dados continuam na pasta memory/. Feche programas que possam estar "
                    "usando esses arquivos e tente novamente." + detail,
                )
                return
            dialog.reject()

        dialog.wipe_all.connect(wipe)
        if dialog.exec() != QDialog.Accepted:
            return 0
        settings.save()

    pet_app = PestinhaApp(settings, paths)
    if args.sair_em > 0:
        QTimer.singleShot(int(args.sair_em * 1000), pet_app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
