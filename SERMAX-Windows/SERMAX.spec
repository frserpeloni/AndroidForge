# -*- mode: python ; coding: utf-8 -*-
# Spec portátil: scripts chamados via runpy precisam ser incluídos como dados.
import os
from PyInstaller.utils.hooks import collect_all

# Pestinha é uma integração prevista no pacote SERMAX. Falhas de coleta
# devem interromper o build, nunca gerar um executável silenciosamente parcial.
extra_datas, extra_binaries, extra_hiddenimports = collect_all("pestinha")

ROOT = os.path.abspath(os.path.dirname(SPEC))
TERMINAL = os.path.join(ROOT, "SERMAX_terminal")

a = Analysis(
    [os.path.join(ROOT, "sermax_launcher.py")],
    pathex=[ROOT, TERMINAL],
    binaries=extra_binaries,
    datas=[
        (os.path.join(TERMINAL, "sermax_terminal.py"), "SERMAX_terminal"),
        (os.path.join(TERMINAL, "sermax_voz.py"), "SERMAX_terminal"),
        (os.path.join(TERMINAL, "sermax_integracao_comandos.py"), "SERMAX_terminal"),
        (os.path.join(ROOT, "sermax_jarvis_worker.py"), "."),
        (os.path.join(ROOT, "THIRD_PARTY_NOTICES", "Pestinha-GPL-3.0.txt"), "THIRD_PARTY_NOTICES"),
        (os.path.join(ROOT, "THIRD_PARTY_NOTICES", "Pestinha-ORIGIN.md"), "THIRD_PARTY_NOTICES"),
    ] + extra_datas,
    hiddenimports=[
        "sermax_core", "sermax_historico_comandos", "sermax_planejador",
        "sermax_executor", "sermax_tarefas", "ferramenta_windows",
        "sermax_jarvis_adapter", "sermax_pestinha_adapter", "sermax_widget_state",
        "sermax_voz", "sermax_integracao_comandos",
    ] + extra_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SERMAX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
