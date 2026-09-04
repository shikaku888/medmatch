@echo off
rem Serve React SPA (dist-scanner) over HTTPS for iPhone test
rem Same concept as medmatch/start_https.bat but for scanner build
cd /d "%~dp0\..\personalized-product-scanner"
echo Serving scanner build on HTTPS...
python -m http.server 8766 --bind 0.0.0.0 &
echo Open on iPhone (same Wi-Fi): https://%COMPUTERNAME%.local:8766/  or use LAN IP above
pause
