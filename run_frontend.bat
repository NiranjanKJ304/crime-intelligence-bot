@echo off
REM ==============================================================================
REM Run Crime-Bot Streamlit Frontend (Local Native Execution)
REM ==============================================================================

cd /d "%~dp0"

if not exist ".venv" (
    echo Creating Python virtual environment (.venv)...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Checking / installing frontend dependencies...
pip install -r frontend\requirements.txt

set BACKEND_URL=http://127.0.0.1:8000

echo.
echo Starting Streamlit UI on http://localhost:8501 ...
echo.

cd frontend
streamlit run app.py --server.port 8501
pause
