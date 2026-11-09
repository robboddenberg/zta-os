# ZTA OS Startskript fuer Windows PowerShell
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

$Port = if ($env:PORT) { [int]$env:PORT } else { 8020 }
$BindHost = if ($env:ALLOW_LAN -in @("1", "true", "yes")) { "0.0.0.0" } else { "127.0.0.1" }
$HealthUrl = "http://127.0.0.1:$Port/api/health"

# 1. Pruefen, ob der Port bereits belegt ist
$PortBusy = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($PortBusy) {
    $ExistingPid = $PortBusy[0].OwningProcess
    Write-Host "[FEHLER] Port $Port ist bereits belegt (PID: $ExistingPid)." -ForegroundColor Red
    Write-Host "Bitte beende zuerst den laufenden Prozess (Stop-Process -Id $ExistingPid) oder setze eine andere PORT-Umgebungsvariable."
    exit 1
}

# 2. Virtuelle Umgebung (.venv) pruefen oder gemeinsames Canvas-Venv nutzen
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
$SharedVenvPython = "D:\G-Drive\Canvas\Leben backup\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    if (Test-Path $SharedVenvPython) {
        $VenvPython = $SharedVenvPython
    } else {
        Write-Host "Erstelle virtuelle Python-Umgebung (.venv)..." -ForegroundColor Cyan
        $SysPython = "python"
        $LocalPy312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        if (Test-Path $LocalPy312) {
            $SysPython = $LocalPy312
        }
        & $SysPython -m venv .venv
        & $VenvPython -m pip install --upgrade pip | Out-Null
        & $VenvPython -m pip install -r backend\requirements.txt
    }
}

# 3. Initiale synthetische Agenturdaten erzeugen, falls data\data.json noch fehlt
$DataJson = Join-Path $RootDir "data\data.json"
if (-not (Test-Path $DataJson)) {
    & $VenvPython scripts\build_initial_data.py
}

# 4. Server im Hintergrund starten
$LogOut = Join-Path $RootDir "zta-os-server.log"
$LogErr = Join-Path $RootDir "zta-os-server.err.log"
$PidFile = Join-Path $RootDir "zta-os.pid"

$Proc = Start-Process -FilePath $VenvPython `
    -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", $BindHost, "--port", "$Port") `
    -WorkingDirectory $RootDir `
    -RedirectStandardOutput $LogOut `
    -RedirectStandardError $LogErr `
    -PassThru `
    -WindowStyle Hidden

$Proc.Id | Set-Content -Path $PidFile -Encoding ascii

# 5. Auf /api/health warten
$Ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 300
    try {
        $Resp = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2 -ErrorAction Stop
        if ($Resp.status -eq "ok") {
            $Ready = $true
            break
        }
    } catch {
        # Noch im Startvorgang
    }
}

if (-not $Ready) {
    Write-Host "[FEHLER] ZTA OS ist nicht rechtzeitig auf $HealthUrl gestartet. Siehe $LogErr" -ForegroundColor Red
    exit 1
}

Write-Host "ZTA OS laeuft im Hintergrund!" -ForegroundColor Green
Write-Host "  URL:  http://127.0.0.1:$Port"
Write-Host "  PID:  $($Proc.Id) (gespeichert in zta-os.pid)"
Write-Host "  Data: $($Resp.data_file) (Revision $($Resp.revision), has_data=$($Resp.has_data))"
