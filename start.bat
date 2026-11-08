@echo off
rem Start Akela Nahi on this laptop only: open http://localhost:8000
cd /d "%~dp0"
.venv\Scripts\python -m uvicorn app.main:app --port 8000
