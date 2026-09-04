#!/bin/sh
set -eu

# FastAPI is the only production runtime; it serves React and /api/*.
cd /app/medmatch
exec python3 -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-8080}"
