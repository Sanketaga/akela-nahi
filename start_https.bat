@echo off
rem Start Akela Nahi for phones on the same Wi-Fi (the microphone needs https).
rem Makes a fresh certificate each time, in case the laptop's Wi-Fi address changed.
cd /d "%~dp0"
.venv\Scripts\python make_cert.py
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile data\key.pem --ssl-certfile data\cert.pem
