@echo off
echo === Test React SPA on iPhone (same Wi-Fi) ===
echo 1. Start this server (keep open)
echo 2. On iPhone Chrome: open https://<YOUR-PC-IP>:8443/scanner/
echo 3. First visit: Advanced -> Proceed (self-signed cert)
echo 4. For camera/OCR: must be HTTPS (this server is HTTPS)
echo 5. Add to Home screen for PWA test
python -m uvicorn "personalized-product-scanner.dist-scanner:app" --host 0.0.0.0 --port 8443 --ssl-certfile "medmatch/backend/data/dev_cert.pem" --ssl-keyfile "medmatch/backend/data/dev_key.pem" 2>nul || echo "Uvicorn not found — try: pip install uvicorn"
echo Server running. Press Ctrl+C to stop.
