#!/bin/bash
# FastAPI engine (internal) then Express BFF + React build (public $PORT)
cd /app/medmatch
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8765 &
ENGINE_PID=$!

cd /app/scanner
node dist/server.cjs &
APP_PID=$!

trap "kill $ENGINE_PID $APP_PID 2>/dev/null" TERM INT
wait -n $ENGINE_PID $APP_PID
EXIT=$?
echo "a service exited ($EXIT) — shutting down"
kill $ENGINE_PID $APP_PID 2>/dev/null
exit $EXIT
