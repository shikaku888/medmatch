@echo off
rem MedMatch — HTTPS mode (phone testing over Wi-Fi).
rem Camera barcode/OCR scanning requires a secure context; accept the self-signed
rem certificate warning once on the phone, then everything works + PWA installable.
cd /d "%~dp0"
if not exist backend\data\dev_cert.pem (
    echo Generating self-signed certificate...
    python backend\dev_cert.py || exit /b 1
)
for /f "tokens=2 delims=:" %%a in ('netsh interface ip show addresses ^| findstr /i "IPv4"') do echo LAN IP:%%a
echo Open on phone:  https://^<LAN-IP^>:8443/scanner/
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8443 --ssl-certfile backend\data\dev_cert.pem --ssl-keyfile backend\data\dev_key.pem
