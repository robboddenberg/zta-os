<#
.SYNOPSIS
  Universelles GitHub-Sync-Skript fuer Klarschiff und alle zukuenftigen Apps in D:\G-Drive\Canvas.
.DESCRIPTION
  - Prueft Git & GitHub CLI (gh)
  - Schuetzt sensible Daten (.gitignore)
  - Initialisiert das Git-Repo (Branch: main), erstellt Commits und synchronisiert mit GitHub (standardmaessig als privates Repo).
.PARAMETER AppDir
  Pfad zum App-Ordner (Standard: das Projektverzeichnis).
.PARAMETER RepoName
  Name des GitHub-Repositories (Standard: Ordnername, z. B. "klarschiff").
.PARAMETER Message
  Commit-Nachricht (Standard: "Update <Datum>").
.PARAMETER Public
  Falls gesetzt, wird ein neues Repo als public statt private angelegt.
#>
param(
    [string]$AppDir = "",
    [string]$RepoName = "",
    [string]$Message = "",
    [switch]$Public,
    [switch]$CommitOnly
)

$ErrorActionPreference = "Stop"

if (-not $AppDir) {
    if ((Split-Path -Leaf $PSScriptRoot) -ieq "scripts") {
        $AppDir = Split-Path -Parent $PSScriptRoot
    } else {
        $AppDir = $PSScriptRoot
    }
}

function Find-Binary([string]$Name, [string[]]$FallbackPaths) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in $FallbackPaths) {
        $resolved = Resolve-Path $p -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($resolved -and (Test-Path $resolved.Path)) { return $resolved.Path }
    }
    return $null
}

$GitExe = Find-Binary "git" @(
    "C:\Program Files\Git\cmd\git.exe",
    "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\git.exe",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Git.MinGit*\cmd\git.exe"
)
$GhExe = Find-Binary "gh" @(
    "C:\Program Files\GitHub CLI\gh.exe",
    "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\gh.exe"
)

if (-not $GitExe) {
    Write-Error "git.exe wurde nicht gefunden. Bitte 'winget install --id Git.MinGit -e' ausfuehren."
    exit 1
}

$GitBinDir = Split-Path -Parent $GitExe
if ($env:PATH -notlike "*$GitBinDir*") {
    $env:PATH = "$GitBinDir;$env:PATH"
}
if ($GhExe) {
    $GhBinDir = Split-Path -Parent $GhExe
    if ($env:PATH -notlike "*$GhBinDir*") {
        $env:PATH = "$GhBinDir;$env:PATH"
    }
}

$ResolvedDir = (Resolve-Path $AppDir).Path
if (-not $RepoName) {
    $RepoName = (Split-Path -Leaf $ResolvedDir).ToLower() -replace "[^a-z0-9\-_]", "-"
}
if (-not $Message) {
    $Message = "Sync $RepoName (" + (Get-Date -Format "yyyy-MM-dd HH:mm") + ")"
}

Push-Location $ResolvedDir
try {
    # 1. Sicherheits-.gitignore sicherstellen, falls in einer neuen App noch keine existiert
    if (-not (Test-Path ".gitignore")) {
        @(
            "# Sensible Nutzerdaten & Backups (niemals ins Git!)",
            "data/",
            "secrets/",
            ".env",
            ".env.*",
            "credentials.json",
            "token.json",
            "*.bak.*",
            "*.tmp.*",
            ".venv/",
            "venv/",
            "__pycache__/",
            "*.py[cod]",
            ".pytest_cache/",
            "*.pid",
            "*.log"
        ) | Set-Content -Path ".gitignore" -Encoding UTF8
        Write-Host "[Git-Sync] Standard-.gitignore zum Schutz persoenlicher Daten angelegt."
    }

    # 2. Git-Repo initialisieren, falls noch nicht vorhanden
    if (-not (Test-Path ".git")) {
        & $GitExe init -b main | Out-Null
        Write-Host "[Git-Sync] Neues Git-Repository in $ResolvedDir initialisiert (Branch: main)."
    }

    # 3. Git User-Config pruefen (lokaler Fallback, falls global noch leer)
    $uName = & $GitExe config user.name
    if (-not $uName) {
        & $GitExe config user.name "Robin"
    }
    $uEmail = & $GitExe config user.email
    if (-not $uEmail) {
        & $GitExe config user.email "robin@users.noreply.github.com"
    }

    # 4. Aenderungen stagen und committen
    & $GitExe add -A
    $status = & $GitExe status --porcelain
    if ($status) {
        & $GitExe commit -m $Message
        Write-Host "[Git-Sync] Commit erstellt: $Message"
    } else {
        Write-Host "[Git-Sync] Arbeitsverzeichnis ist bereits sauber committed."
    }

    # 5. GitHub-Synchronisation ueber gh CLI
    if ($CommitOnly) {
        Write-Host "[Git-Sync] Lokaler Commit in $ResolvedDir abgeschlossen (-CommitOnly)." -ForegroundColor Green
        exit 0
    }

    if (-not $GhExe) {
        Write-Warning "GitHub CLI (gh) nicht gefunden. Lokaler Commit ist gespeichert."
        exit 0
    }

    $ErrorActionPreference = "Continue"
    & $GhExe auth status 2>&1 | Out-Null
    $authOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = "Stop"

    if (-not $authOk) {
        Write-Host ""
        Write-Host "=== GitHub Anmeldung erforderlich (einmalig) ===" -ForegroundColor Cyan
        Write-Host "Starte 'gh auth login --web -p https' ..."
        & $GhExe auth login --web -p https
    }

    & $GhExe auth setup-git 2>$null

    $ErrorActionPreference = "Continue"
    $originUrl = & $GitExe remote get-url origin 2>$null
    $hasOrigin = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($originUrl))
    $ErrorActionPreference = "Stop"

    if (-not $hasOrigin) {
        $visFlag = if ($Public) { "--public" } else { "--private" }
        Write-Host "[Git-Sync] Erstelle GitHub-Repository '$RepoName' ($visFlag) und lade hoch ..."
        $ErrorActionPreference = "Continue"
        & $GhExe repo create $RepoName $visFlag --source=. --remote=origin --push
        if ($LASTEXITCODE -ne 0) {
            $ghUser = (& $GhExe api user --jq .login).Trim()
            & $GitExe remote add origin "https://github.com/$ghUser/$RepoName.git" 2>$null
            & $GitExe push -u origin main
        }
        $ErrorActionPreference = "Stop"
    } else {
        Write-Host "[Git-Sync] Lade Aenderungen hoch nach $originUrl ..."
        & $GitExe push -u origin main
    }

    Write-Host "[Git-Sync] Fertig! $RepoName ist mit GitHub synchronisiert." -ForegroundColor Green
} finally {
    Pop-Location
}
