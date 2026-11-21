"""Registro explícito da Plataforma SERMAX no Agendador de Tarefas do Windows.

Este módulo nunca instala uma tarefa durante a inicialização normal da aplicação.
A criação e a remoção exigem comandos explícitos do operador.
"""
from __future__ import annotations

import getpass
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

TASK_NAME = "SERMAX Platform"
_TASK_NOT_FOUND_MARKERS = (
    "0x80070002",
    "cannot find the file specified",
    "não foi possível localizar o arquivo",
    "não foi possível encontrar o arquivo",
    "o sistema não pode encontrar o arquivo",
)


def _is_windows() -> bool:
    return os.name == "nt"


def _current_user_id() -> str:
    username = os.environ.get("USERNAME") or getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    return f"{domain}\\{username}" if domain else username


def build_task_xml(platform_root: Path, executable: str | None = None,
                   frozen: bool | None = None, user_id: str | None = None) -> str:
    """Gera tarefa ONLOGON limitada ao usuário interativo atual."""
    root_path = Path(platform_root).resolve()
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        command = executable or sys.executable
        arguments = ["--no-browser"]
    else:
        backend_venv_dir = root_path / "backend" / ".venv" / "Scripts"
        backend_venv_pythonw = backend_venv_dir / "pythonw.exe"
        backend_venv_python = backend_venv_dir / "python.exe"
        if executable:
            command = executable
        elif backend_venv_pythonw.is_file():
            command = str(backend_venv_pythonw)
        elif backend_venv_python.is_file():
            command = str(backend_venv_python)
        else:
            command = sys.executable
        arguments = [str(root_path / "sermax_platform_launcher.py"), "--no-browser"]

    task = ET.Element("Task", {"version": "1.4", "xmlns": "http://schemas.microsoft.com/windows/2004/02/mit/task"})
    registration = ET.SubElement(task, "RegistrationInfo")
    ET.SubElement(registration, "Description").text = (
        "Inicia a API local da Plataforma SERMAX na sessão do usuário atual."
    )
    triggers = ET.SubElement(task, "Triggers")
    trigger = ET.SubElement(triggers, "LogonTrigger")
    ET.SubElement(trigger, "Enabled").text = "true"
    ET.SubElement(trigger, "UserId").text = user_id or _current_user_id()

    principals = ET.SubElement(task, "Principals")
    principal = ET.SubElement(principals, "Principal", {"id": "Author"})
    ET.SubElement(principal, "UserId").text = user_id or _current_user_id()
    ET.SubElement(principal, "LogonType").text = "InteractiveToken"
    ET.SubElement(principal, "RunLevel").text = "LeastPrivilege"

    settings = ET.SubElement(task, "Settings")
    settings_values = {
        "MultipleInstancesPolicy": "IgnoreNew",
        "DisallowStartIfOnBatteries": "false",
        "StopIfGoingOnBatteries": "false",
        "StartWhenAvailable": "true",
        "Enabled": "true",
        "Hidden": "false",
        "RunOnlyIfIdle": "false",
        "WakeToRun": "false",
        "ExecutionTimeLimit": "PT0S",
        "Priority": "7",
    }
    for tag, value in settings_values.items():
        ET.SubElement(settings, tag).text = value
    restart = ET.SubElement(settings, "RestartOnFailure")
    ET.SubElement(restart, "Interval").text = "PT1M"
    ET.SubElement(restart, "Count").text = "3"

    actions = ET.SubElement(task, "Actions", {"Context": "Author"})
    action = ET.SubElement(actions, "Exec")
    ET.SubElement(action, "Command").text = command
    ET.SubElement(action, "Arguments").text = subprocess.list2cmdline(arguments)
    ET.SubElement(action, "WorkingDirectory").text = str(root_path)
    return ET.tostring(task, encoding="utf-16", xml_declaration=True).decode("utf-16")


def _run_schtasks(arguments: list[str], runner=None):
    if not _is_windows():
        raise RuntimeError("O gerenciamento de inicialização automática está disponível somente no Windows.")
    execute = runner or subprocess.run
    try:
        return execute(
            ["schtasks.exe", *arguments],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise RuntimeError(f"Não foi possível executar schtasks.exe: {exc}") from exc


def install_autostart(platform_root: Path, runner=None) -> None:
    """Registra execução no logon do usuário atual, sem privilégios elevados."""
    xml_text = build_task_xml(platform_root)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-16", suffix=".xml", delete=False
    ) as task_file:
        task_file.write(xml_text)
        xml_path = Path(task_file.name)
    try:
        result = _run_schtasks(
            ["/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"], runner=runner
        )
    finally:
        xml_path.unlink(missing_ok=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "erro sem detalhes").strip()
        raise RuntimeError(f"Falha ao registrar tarefa do SERMAX: {detail}")


def autostart_status(runner=None) -> bool:
    """Retorna se a tarefa registrada existe para o Agendador do Windows."""
    result = _run_schtasks(
        ["/Query", "/TN", TASK_NAME, "/FO", "LIST"], runner=runner
    )
    if result.returncode == 0:
        return True
    detail = (result.stderr or result.stdout or "").strip()
    normalized = detail.casefold()
    if any(marker in normalized for marker in _TASK_NOT_FOUND_MARKERS):
        return False
    raise RuntimeError(
        "Falha ao consultar a tarefa do SERMAX no Agendador: "
        + (detail or f"código de saída {result.returncode}")
    )


def remove_autostart(runner=None) -> bool:
    """Remove a tarefa, sem afetar arquivos ou dados da Plataforma."""
    if not autostart_status(runner=runner):
        return False
    result = _run_schtasks(
        ["/Delete", "/TN", TASK_NAME, "/F"], runner=runner
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "erro sem detalhes").strip()
        raise RuntimeError(f"Falha ao remover tarefa do SERMAX: {detail}")
    return True
