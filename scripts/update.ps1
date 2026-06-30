# DTCall Online Update Script (Windows / PowerShell)
param([string]$TargetVersion = "")
$ErrorActionPreference = "Stop"
$Dir = Split-Path -Parent $PSScriptRoot
Set-Location $Dir

function Write-Step { Write-Host "[UPDATE] $args" -ForegroundColor Green }
function Write-Warn { Write-Host "[WARN]  $args" -ForegroundColor Yellow }
function Write-Err  { Write-Host "[ERROR] $args" -ForegroundColor Red }

try { git rev-parse --git-dir | Out-Null } catch { Write-Err "Not a git repo"; exit 1 }

$CurrentVersion = if (Test-Path VERSION) { (Get-Content VERSION -Raw).Trim() } else { "0.0.0" }
$CurrentCommit = git rev-parse --short HEAD
Write-Step "Current: $CurrentVersion ($CurrentCommit)"

git fetch --tags --quiet
if (-not $TargetVersion) {
    $TargetVersion = git tag --sort=-version:refname | Where-Object { $_ -match '^\d+' } | Select-Object -First 1
}
if (-not $TargetVersion) { Write-Err "No version tags found"; exit 1 }
if ($TargetVersion -eq $CurrentVersion) { Write-Step "Already latest"; exit 0 }
Write-Step "Target: $TargetVersion"

New-Item -ItemType Directory -Force -Path "backups\pre_update" | Out-Null
$BackupFile = "backups\pre_update\pre_update_${CurrentVersion}_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
if (Test-Path db.sqlite3) {
    Copy-Item db.sqlite3 "${BackupFile}.sqlite3"
    Write-Step "Backup: ${BackupFile}.sqlite3"
}

@{
    previous_commit = $CurrentCommit
    previous_version = $CurrentVersion
    target_version = $TargetVersion
    timestamp = (Get-Date -Format "o")
} | ConvertTo-Json | Set-Content .rollback_state -Encoding UTF8

git checkout $TargetVersion
Set-Content VERSION $TargetVersion -Encoding UTF8

$Python = if (Test-Path "venv\Scripts\python.exe") { "venv\Scripts\python.exe" } else { "python" }
$migResult = & $Python manage.py migrate --noinput 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "Migration failed!"
    git checkout $CurrentCommit
    Set-Content VERSION $CurrentVersion -Encoding UTF8
    Remove-Item .rollback_state -ErrorAction SilentlyContinue
    exit 1
}
& $Python manage.py collectstatic --noinput 2>$null

$NewCommit = git rev-parse --short HEAD
Write-Step "Done: $CurrentVersion -> $TargetVersion ($CurrentCommit -> $NewCommit)"
Write-Step "Rollback: .\scriptsollback.ps1"
