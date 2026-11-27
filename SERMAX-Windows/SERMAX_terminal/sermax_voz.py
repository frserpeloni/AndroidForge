"""Camada local de reconhecimento de voz para SERMAX v2.7.2.
Validação WAV sem importar o módulo wave, que pode faltar no executável congelado.
Não baixa arquivos nem chama serviços externos.
"""
from pathlib import Path
import os
import subprocess

TERMINAL_DIR = Path(__file__).resolve().parent
SERMAX_DIR = Path(os.environ.get("SERMAX_ROOT", str(TERMINAL_DIR.parent))).resolve()
USER_DOWNLOADS = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads"

def _arquivos_por_nome(raiz, nome):
    """Procura arquivos já instalados sem acessar a internet."""
    if not raiz.is_dir():
        return
    try:
        for pasta, diretorios, arquivos in os.walk(raiz):
            diretorios[:] = [d for d in diretorios if d.lower() not in {
                "__pycache__", ".git", "build", "dist", "backups", "backup"
            }]
            if nome in arquivos:
                yield Path(pasta) / nome
    except (OSError, PermissionError):
        return

def localizar_whisper_e_modelo():
    """Localiza Whisper e modelo em pastas conhecidas, sem baixar nem alterar arquivos."""
    exe_alvos = [
        SERMAX_DIR / "voz" / "whisper" / "Release" / "whisper-cli.exe",
        SERMAX_DIR / "voz" / "whisper-cli.exe",
    ]
    mod_alvos = [SERMAX_DIR / "voz" / "modelos" / "ggml-tiny.bin"]
    exe = next((p for p in exe_alvos if p.is_file()), None)
    modelo = next((p for p in mod_alvos if p.is_file()), None)
    raizes = [SERMAX_DIR, USER_DOWNLOADS]
    if not exe:
        for raiz in raizes:
            exe = next(_arquivos_por_nome(raiz, "whisper-cli.exe"), None)
            if exe: break
    if not modelo:
        for raiz in raizes:
            modelo = next(_arquivos_por_nome(raiz, "ggml-tiny.bin"), None)
            if modelo: break
    return (str(exe) if exe else None, str(modelo) if modelo else None)

def diagnostico_voz():
    exe, modelo = localizar_whisper_e_modelo()
    return {"whisper": exe, "modelo": modelo, "pronto": bool(exe and modelo)}

def _validar_wav(caminho):
    """Valida RIFF/WAVE lendo cabeçalhos, sem depender do módulo wave."""
    with open(caminho, "rb") as f:
        cab = f.read(12)
        if len(cab) < 12 or cab[0:4] != b"RIFF" or cab[8:12] != b"WAVE":
            raise ValueError("Arquivo inválido: precisa ser WAV RIFF, não basta renomear M4A para WAV.")
        formato = None
        canais = taxa = bits = None
        tem_dados = False
        while True:
            chunk = f.read(8)
            if len(chunk) < 8: break
            nome, tamanho = chunk[:4], int.from_bytes(chunk[4:8], "little")
            conteudo = f.read(min(tamanho, 64) if nome == b"fmt " else min(tamanho, 0))
            if nome == b"fmt ":
                if len(conteudo) < 16: raise ValueError("Cabeçalho WAV incompleto.")
                formato = int.from_bytes(conteudo[0:2], "little")
                canais = int.from_bytes(conteudo[2:4], "little")
                taxa = int.from_bytes(conteudo[4:8], "little")
                bits = int.from_bytes(conteudo[14:16], "little")
                f.seek(max(0, tamanho - len(conteudo)), 1)
            else:
                if nome == b"data" and tamanho > 0: tem_dados = True
                f.seek(tamanho, 1)
            if tamanho & 1: f.seek(1, 1)
            if formato is not None and tem_dados: break
    if not tem_dados or not canais or not taxa:
        raise ValueError("WAV vazio ou sem dados de áudio.")
    if formato != 1:
        raise ValueError("WAV deve usar PCM não comprimido. Converta para PCM 16-bit, mono, 16 kHz.")
    if canais not in (1, 2) or taxa < 8000 or bits not in (8, 16, 24, 32):
        raise ValueError("Parâmetros WAV incompatíveis. Recomendado: PCM 16-bit, mono, 16 kHz.")

def transcrever_arquivo(caminho_audio):
    audio = Path(caminho_audio).expanduser()
    if not audio.is_absolute(): audio = Path.cwd() / audio
    if not audio.is_file(): raise FileNotFoundError(f"Áudio não encontrado: {audio}")
    if audio.suffix.lower() != ".wav":
        raise ValueError("O arquivo precisa estar convertido para WAV; renomear M4A não converte o áudio.")
    _validar_wav(audio)
    exe, modelo = localizar_whisper_e_modelo()
    if not exe or not modelo:
        raise FileNotFoundError("Whisper/modelo não localizados. Coloque os arquivos em C:\\SERMAX\\voz conforme LEIA-ME.")
    saida = audio.with_name(audio.stem + "_sermax_transcricao")
    cmd = [exe, "-m", modelo, "-f", str(audio), "-l", "pt", "-otxt", "-of", str(saida), "-nt"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, cwd=str(Path(exe).parent), shell=False)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("O Whisper ultrapassou 180 segundos.") from exc
    txt = Path(str(saida) + ".txt")
    texto = txt.read_text(encoding="utf-8-sig", errors="replace").strip() if txt.is_file() else proc.stdout.strip()
    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout or "sem detalhes")[-1200:]
        raise RuntimeError(f"Whisper encerrou com código {proc.returncode}: {detalhe}")
    if not texto: raise RuntimeError("Whisper terminou sem produzir transcrição.")
    return texto
