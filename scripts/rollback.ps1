# DTCall Rollback Script (Windows / PowerShell)
$ErrorActionPreference = "Stop"
$Dir = Split-Path -Parent $PSScriptRoot
Set-Location $Dir

function Write-Step { Write-Host "[ROLLBACK] $args" -ForegroundColor Green }
function Write-Err  { Write-Host "[ERROR] $args" -ForegroundColor Red }

if (-not (Test-Path .rollback_state)) {
    Write-Err "No rollback state found"
    exit 1
}

$state = Get-Content .rollback_state -Raw | ConvertFrom-Json
Write-Step "Rolling back to $($state.previous_version) ($($state.previous_commit))"

git checkout $state.previous_commit
Set-Content VERSION $state.previous_version -Encoding UTF8

$Python = if (Test-Path "venv\Scripts\python.exe") { "venv\Scripts\python.exe" } else { "python" }
& $Python manage.py migrate --noinput 2>&1
& $Python manage.py collectstatic --noinput 2>$null

Remove-Item .rollback_state -ErrorAction SilentlyContinue
Write-Step "Rollback complete. Restored to $($state.previous_version)."
