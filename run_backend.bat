@echo off
REM ==============================================================================
REM Run Crime-Bot Backend (Local Native Execution)
REM ==============================================================================

cd /d "%~dp0"

if not exist ".venv" (
    echo Creating Python virtual environment (.venv)...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Checking / installing backend dependencies...
pip install -r backend\requirements.txt

set PYTHONPATH=%~dp0backend

echo.
echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
echo Interactive Swagger docs available at: http://127.0.0.1:8000/docs
echo.

cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
