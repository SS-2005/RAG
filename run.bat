@echo off
title DOCX Local RAG Assistant
echo ========================================================
echo        DOCX Local RAG Assistant (Dark UI)
echo ========================================================
echo.
echo Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Starting Local DOCX RAG Assistant Server on http://127.0.0.1:8000 ...
echo Press Ctrl+C in this terminal to stop the server.
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
