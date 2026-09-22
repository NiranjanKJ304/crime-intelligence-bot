# ==============================================================================
# Run Crime-Bot Streamlit Frontend (Local Native Execution)
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

# Check / install frontend requirements
Write-Host "Checking / installing frontend dependencies..." -ForegroundColor Cyan
pip install -r "$ScriptDir\frontend\requirements.txt"

# Set environment
$env:BACKEND_URL = "http://127.0.0.1:8000"

Write-Host "`nStarting Streamlit UI on http://localhost:8501 ..." -ForegroundColor Green

Set-Location "$ScriptDir\frontend"
streamlit run app.py --server.port 8501
