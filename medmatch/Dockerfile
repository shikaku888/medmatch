# MedMatch — compact runtime image for Fly.io / Railway / Render / Docker hosts
#
# Build contract:
#   1. Run `python deploy/build_runtime_db.py` first.
#   2. The generated deploy/runtime/medmatch.db is the only DB shipped.
#   3. Raw source archives stay outside the image and are refreshed separately.
#
# The mounted DB is seeded once, then served read-only. Importers are not run
# during API boot because a failed refresh must never replace an accepted
# runtime snapshot.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY static ./static
COPY docs/privacy-policy.md /app/docs/privacy-policy.md
COPY deploy/start.sh /app/start.sh
COPY deploy/runtime/medmatch.db /app/seed/medmatch.db
COPY deploy/runtime/medmatch.db.manifest.json /app/seed/medmatch.db.manifest.json
COPY deploy/runtime/medmatch.db.evaluation.json /app/seed/medmatch.db.evaluation.json

RUN chmod +x /app/start.sh \
    && mkdir -p /app/backend/data/devices

ENV MEDMATCH_DB=/app/backend/data/medmatch.db \
    MEDMATCH_DB_MANIFEST=/app/backend/data/medmatch.db.manifest.json \
    MEDMATCH_DB_SEED_MANIFEST=/app/seed/medmatch.db.manifest.json \
    MEDMATCH_DB_SEED_EVALUATION=/app/seed/medmatch.db.evaluation.json \
    MEDMATCH_R5_EVALUATION=/app/backend/data/medmatch.db.evaluation.json \
    REQUIRE_R5_EVALUATION=1 \
    RATE_LIMIT_DB=/app/backend/data/rate-limit.db \
    SCANNER_DATA_DIR=/app/backend/data/devices \
    CANONICAL_EVIDENCE_READ=1

EXPOSE 8080
ENTRYPOINT ["/app/start.sh"]
