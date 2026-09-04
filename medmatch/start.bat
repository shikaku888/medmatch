@echo off
rem MedMatch — HTTP mode (PC testing). Phone camera needs HTTPS: use start_https.bat
cd /d "%~dp0"
echo MedMatch: http://127.0.0.1:8765  (Scanner UI: /scanner/)
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8765
