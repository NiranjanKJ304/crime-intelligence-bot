# ==============================================================================
# Run Crime-Bot Backend (Local Native Execution)
# ==============================================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Check / create virtual environment
if (-not (Test-Path "$ScriptDir\.venv")) {
    Write-Host "Creating Python virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv "$ScriptDir\.venv"
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& "$ScriptDir\.venv\Scripts\Activate.ps1"

# Check / install backend requirements
Write-Host "Checking / installing backend dependencies..." -ForegroundColor Cyan
pip install -r "$ScriptDir\backend\requirements.txt"

# Set environment
$env:PYTHONPATH = "$ScriptDir\backend"

Write-Host "`nStarting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "Interactive Swagger docs available at: http://127.0.0.1:8000/docs`n" -ForegroundColor Yellow

Set-Location "$ScriptDir\backend"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
