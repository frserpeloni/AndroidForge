$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$MainVenv = Join-Path $Root '.venv-integracoes'
$MainPython = Join-Path $MainVenv 'Scripts\python.exe'
$JarvisVenv = Join-Path $Root '.venv-jarvis'
$JarvisPython = Join-Path $JarvisVenv 'Scripts\python.exe'

Write-Host 'SERMAX | Preparacao isolada das integracoes' -ForegroundColor Green
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python Launcher (py) nao encontrado. Nenhum arquivo funcional foi substituido.'
}
& py -3.14 --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.14 nao encontrado. O ambiente principal nao sera alterado.'
}

if (-not (Test-Path $MainPython)) {
    & py -3.14 -m venv $MainVenv
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python 3.14.' }
}
& $MainPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar pip do ambiente principal.' }
& $MainPython -m pip install 'numpy>=2.4.6' 'pyinstaller>=6.11'
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar NumPy/PyInstaller.' }
& $MainPython -m pip install --no-deps 'git+https://github.com/mille-okws/pestinha.git@1b16bd21bb5ba9dd4c460c153f865824f53d05c8'
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar o codigo Pestinha.' }

& py -3.13 --version 2>$null
if ($LASTEXITCODE -eq 0) {
    if (-not (Test-Path $JarvisPython)) {
        & py -3.13 -m venv $JarvisVenv
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python 3.13 do OpenJarvis.' }
    }
    & $JarvisPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar pip do OpenJarvis.' }
    & $JarvisPython -m pip install 'git+https://github.com/open-jarvis/OpenJarvis.git@c6c782b924c9040d7c35f76ff693d4057bc0032f'
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar OpenJarvis.' }
    Write-Host 'OpenJarvis instalado em ambiente Python 3.13 separado.' -ForegroundColor Green
} else {
    Write-Host 'Python 3.13 ausente. Pestinha fica preparado; OpenJarvis permanece opcional.' -ForegroundColor Yellow
}

Write-Host 'Ambientes isolados preparados. Nenhum arquivo de memoria ou executavel foi substituido.' -ForegroundColor Green
