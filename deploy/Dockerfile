# MedMatch AI — single-container deploy (Cloud Run / any Docker host)
# One public URL: FastAPI serves the React bundle and all APIs.
FROM python:3.12-slim

WORKDIR /app

# FastAPI engine, OCR runtime, and SQLite-backed scanner services.
COPY medmatch/requirements.txt /app/medmatch/requirements.txt
RUN pip install --no-cache-dir -r /app/medmatch/requirements.txt

COPY medmatch/backend /app/medmatch/backend
COPY medmatch/static /app/medmatch/static

COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/app/start.sh"]
