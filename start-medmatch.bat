@echo off
REM MedMatch AI — single app runtime (FastAPI serves the React production UI)
REM App + API + MedMatch engine: http://127.0.0.1:8765

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%medmatch"
set "MEDMATCH_DB=%APP_DIR%\deploy\runtime\medmatch.db"
set "SCANNER_DATA_DIR=%APP_DIR%\backend\data\devices"

if not exist "%MEDMATCH_DB%" (
  echo Missing canonical runtime snapshot: "%MEDMATCH_DB%"
  echo Build it first with: cd /d "%APP_DIR%" ^&^& python deploy\build_runtime_db.py --source backend\medmatch.db --output deploy\runtime\medmatch.db --force
  exit /b 1
)

start "MedMatch" /min /d "%APP_DIR%" cmd /c "python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765"

timeout /t 5 /nobreak >nul
start http://127.0.0.1:8765/
echo MedMatch AI running: http://127.0.0.1:8765/
