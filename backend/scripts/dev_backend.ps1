# dev_backend.ps1 | Inicia o backend local do Painel de Equipamentos com salvaguardas.
#
# O que ele faz antes de subir o uvicorn:
#   1. Garante que o venv do projeto existe (oferece bootstrap se faltar).
#   2. Mata filhos orfaos do uvicorn --reload (spawn_main cujo pai ja morreu),
#      que ficam presos segurando a porta e causam [Errno 10048] no proximo start.
#   3. Se a porta escolhida seguir ocupada, mostra o dono e pergunta se pode encerrar.
#   4. Sobe o servidor com o python do venv, a partir da pasta backend/.
#
# Uso (de qualquer lugar):
#   powershell -ExecutionPolicy Bypass -File scripts\dev_backend.ps1              # porta 8000
#   powershell -ExecutionPolicy Bypass -File scripts\dev_backend.ps1 -Port 8010   # outra porta
#
# Ctrl+C para parar o servidor.

[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$Bind = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

# Sempre opera a partir da pasta backend/, onde ficam o app/ e o .env.
Set-Location (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"

Write-Host "== Painel de Equipamentos | backend ==" -ForegroundColor Cyan

# --- 1) venv ------------------------------------------------------------------
if (-not (Test-Path $venvPython)) {
    Write-Host "Virtualenv nao encontrado em .venv\" -ForegroundColor Yellow
    $r = Read-Host "Criar venv e instalar dependencias agora? (S/N)"
    if ($r -notmatch '^[sS]') {
        Write-Host "Sem venv nao da para rodar. Abortando." -ForegroundColor Red
        exit 1
    }
    python -m venv .venv
    & $venvPython -m pip install -e ".[dev]"
}

Write-Host "Python do projeto: $venvPython"

# --- 2) zumbis de reload --------------------------------------------------------
Write-Host "Procurando filhos orfaos do uvicorn --reload (spawn_main sem pai vivo)..." -ForegroundColor DarkGray
$zumbis = @()
foreach ($proc in (Get-CimInstance Win32_Process -Filter "Name like 'python%' AND CommandLine like '%spawn_main%'")) {
    if ($proc.CommandLine -match 'parent_pid=(\d+)') {
        $idPai = [int]$Matches[1]
        if (-not (Get-CimInstance Win32_Process -Filter "ProcessId=$idPai")) {
            $zumbis += [pscustomobject]@{ Id = $proc.ProcessId; Pai = $idPai; Cmd = $proc.CommandLine }
        }
    }
}
foreach ($z in $zumbis) {
    Write-Host "Encerrando zumbi PID $($z.Id) (pai $($z.Pai) ja morto): $($z.Cmd)" -ForegroundColor Yellow
    Stop-Process -Id $z.Id -Force -ErrorAction SilentlyContinue
}
if ($zumbis.Count -eq 0) {
    Write-Host "Nenhum zumbi encontrado." -ForegroundColor DarkGray
}

# --- 3) porta ocupada -----------------------------------------------------------
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    $owner = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($owner) {
        Write-Host "Porta $Port em uso por PID $($conn.OwningProcess) [$($owner.ProcessName)] $($owner.Path)" -ForegroundColor Yellow
    } else {
        Write-Host "Porta $Port aponta para o PID $($conn.OwningProcess), que nao existe mais (socket zumbi)." -ForegroundColor Yellow
    }
    $r = Read-Host "Liberar a porta encerrando esse processo? (S/N)"
    if ($r -notmatch '^[sS]') {
        Write-Host "Preferiu nao encerrar. Abortando." -ForegroundColor Red
        exit 1
    }
    if ($owner) {
        Stop-Process -Id $owner.Id -Force
    } elseif ((Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)")) {
        Stop-Process -Id $conn.OwningProcess -Force
    } else {
        Write-Host "PID fantasma sem processo real. Reboot e a saida mais confiavel; ou tente -Port $((Get-Random -Minimum 8010 -Maximum 8090))." -ForegroundColor Red
        exit 1
    }
    Start-Sleep -Seconds 1
}

# --- 4) start -------------------------------------------------------------------
Write-Host "Subindo uvicorn em http://$Bind`:$Port (Ctrl+C para parar)" -ForegroundColor Green
Write-Host "Health: /api/v1/health/live  |  /api/v1/health/ready"
& $venvPython -m uvicorn app.main:app --reload --host $Bind --port $Port
