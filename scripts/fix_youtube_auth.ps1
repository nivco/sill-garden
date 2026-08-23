# Fix Sill Garden YouTube upload OAuth - re-login if revoked, then sync to GitHub Actions.
# Usage: .\scripts\fix_youtube_auth.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Python {
    param(
        [string[]]$PyArgs,
        [switch]$AllowFail
    )
    & python @PyArgs
    if (-not $AllowFail -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "=== Fix Sill Garden YouTube upload OAuth ===" -ForegroundColor Cyan
Write-Host ""

Invoke-Python -PyArgs @("-m", "pip", "install", "-q", "-r", "requirements-youtube.txt")

Write-Host "Checking stored YouTube token..." -ForegroundColor Yellow
Invoke-Python -PyArgs @("scripts\youtube_access_gate.py") -AllowFail
if ($LASTEXITCODE -eq 0) {
    Write-Host "YouTube upload token OK locally (Sill Garden channel)." -ForegroundColor Green
    gh auth switch --user nivco | Out-Null
    Invoke-Python -PyArgs @("scripts\youtube_token_sync.py")
    exit 0
}

Write-Host ""
Write-Host "Token missing or invalid - browser login required." -ForegroundColor Yellow
Write-Host "In the Google channel picker, select Sill Garden (not Maker Tool Stack)."
Write-Host "If login loops, revoke the app at https://myaccount.google.com/permissions"
Write-Host ""
Invoke-Python -PyArgs @("scripts\youtube_oauth_login.py", "--force")

Invoke-Python -PyArgs @("scripts\youtube_access_gate.py")
gh auth switch --user nivco | Out-Null
Invoke-Python -PyArgs @("scripts\youtube_token_sync.py")
Write-Host ""
Write-Host "Done. Re-run CI with gh workflow run on nivco/sill-garden" -ForegroundColor Green
Write-Host ""
