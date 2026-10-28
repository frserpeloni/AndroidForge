"""Consultas locais somente de leitura para o SERMAX v2.2.2."""
import platform
import shutil
import subprocess
import sys


def _ram_via_powershell():
    comando = [
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "[string]((Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory)"
    ]
    resultado = subprocess.run(
        comando, capture_output=True, text=True, timeout=8,
        encoding="utf-8", errors="replace", check=False
    )
    valor = resultado.stdout.strip()
    if resultado.returncode == 0 and valor.isdigit():
        bytes_ram = int(valor)
        if bytes_ram > 0:
            return f"{bytes_ram / (1024 ** 3):.2f} GB"
    return None


def _ram_via_ctypes():
    """Fallback nativo do Windows, independente do idioma do PowerShell."""
    if not sys.platform.startswith("win"):
        return None
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    func = ctypes.windll.kernel32.GlobalMemoryStatusEx
    func.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
    func.restype = ctypes.c_int
    if not func(ctypes.byref(status)) or status.ullTotalPhys <= 0:
        return None
    return f"{status.ullTotalPhys / (1024 ** 3):.2f} GB"


def memoria_ram_instalada():
    """Tenta duas fontes independentes; falha de uma não impede a outra."""
    try:
        valor = _ram_via_powershell()
        if valor:
            return valor
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    try:
        valor = _ram_via_ctypes()
        if valor:
            return valor
    except (OSError, AttributeError, TypeError, ValueError):
        pass
    return "Não disponível"


def informacoes_sistema():
    """Consulta informações básicas do Windows sem alterar configurações."""
    info = {
        "windows": platform.platform(),
        "versao_windows": platform.version(),
        "arquitetura": platform.machine(),
        "processador": platform.processor() or "Não identificado",
        "disco": {},
        "memoria_ram": memoria_ram_instalada(),
    }
    try:
        total, usado, livre = shutil.disk_usage("C:\\")
        info["disco"] = {
            "total_gb": round(total / (1024 ** 3), 2),
            "usado_gb": round(usado / (1024 ** 3), 2),
            "livre_gb": round(livre / (1024 ** 3), 2),
        }
    except Exception as erro:
        info["disco"] = {"erro": str(erro)}
    return info


def responder_consulta(pergunta):
    """Responde consultas de leitura do sistema. Retorna None se não for ferramenta."""
    texto = " ".join(str(pergunta).lower().split())
    palavras_ram = ("ram", "memória ram", "memoria ram", "memória instalada", "memoria instalada")
    pergunta_sobre_memoria_pc = ("memória" in texto or "memoria" in texto)
    if any(p in texto for p in palavras_ram) or (
        pergunta_sobre_memoria_pc and any(p in texto for p in ("computador", "notebook", "pc", "máquina", "maquina"))
    ):
        return f"RAM instalada: {memoria_ram_instalada()}"
    if any(p in texto for p in ("disco", "espaço livre", "espaco livre", "armazenamento", "hd", "ssd")):
        disco = informacoes_sistema()["disco"]
        if "erro" in disco:
            return "Não consegui consultar o disco C:."
        return f"Disco C: total {disco['total_gb']} GB, usado {disco['usado_gb']} GB, livre {disco['livre_gb']} GB."
    if "windows" in texto or "versão do sistema" in texto or "versao do sistema" in texto:
        return f"Windows: {platform.platform()}"
    if "processador" in texto or "cpu" in texto:
        return f"Processador: {platform.processor() or 'Não identificado'}"
    if "arquitetura" in texto:
        return f"Arquitetura do sistema: {platform.machine()}"
    return None
