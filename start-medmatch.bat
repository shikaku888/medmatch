@echo off
REM MedMatch AI — start both services (single app, single entry http://localhost:3000)
REM Engine (FastAPI) :8765 — medical data + 7-layer logic (internal service)
REM UI (React+Express) :3000 — the app users open

start "MedMatch Engine" /min cmd /c "cd /d H:\aisuckhoe\medmatch && python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765"

timeout /t 2 /nobreak >nul

start "MedMatch App" /min cmd /c "cd /d H:\aisuckhoe\personalized-product-scanner && C:\Users\ok\AppData\Roaming\npm\node_modules\bun\bin\bun.exe run dev"

timeout /t 5 /nobreak >nul
start http://localhost:3000
echo MedMatch AI running: http://localhost:3000  (engine: http://127.0.0.1:8765)
