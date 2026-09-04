#!/bin/sh
# Production entrypoint for the compact, read-only runtime snapshot.
#
# Data refresh is a separate operation:
#   python deploy/build_runtime_db.py
#   fly deploy
#
# Never run importers during API boot. A failed refresh must not mutate the
# accepted snapshot shared by all workers.
set -eu

DATA_DIR="${SCANNER_DATA_DIR:-/app/backend/data/devices}"
DB="${MEDMATCH_DB:-/app/backend/data/medmatch.db}"
SEED="${MEDMATCH_DB_SEED:-/app/seed/medmatch.db}"
MANIFEST="${MEDMATCH_DB_MANIFEST:-${DB}.manifest.json}"
SEED_MANIFEST="${MEDMATCH_DB_SEED_MANIFEST:-${SEED}.manifest.json}"
R5_EVALUATION="${MEDMATCH_R5_EVALUATION:-${DB}.evaluation.json}"
SEED_EVALUATION="${MEDMATCH_DB_SEED_EVALUATION:-${SEED}.evaluation.json}"

mkdir -p "$DATA_DIR" "$(dirname "$DB")"

if [ ! -f "$DB" ]; then
    if [ ! -s "$SEED" ]; then
        echo "[start] fatal: runtime DB seed is missing: $SEED" >&2
        exit 1
    fi
    if [ ! -s "$SEED_MANIFEST" ]; then
        echo "[start] fatal: runtime DB manifest seed is missing: $SEED_MANIFEST" >&2
        exit 1
    fi
    if [ "${REQUIRE_R5_EVALUATION:-0}" = "1" ] && [ ! -s "$SEED_EVALUATION" ]; then
        echo "[start] fatal: R5 evaluation seed is missing: $SEED_EVALUATION" >&2
        exit 1
    fi
    echo "[start] seeding runtime database from image..."
    tmp="${DB}.seed.$$"
    manifest_tmp="${MANIFEST}.seed.$$"
    evaluation_tmp="${R5_EVALUATION}.seed.$$"
    rm -f "$tmp" "$manifest_tmp" "$evaluation_tmp"
    cp "$SEED" "$tmp"
    cp "$SEED_MANIFEST" "$manifest_tmp"
    if [ "${REQUIRE_R5_EVALUATION:-0}" = "1" ]; then
        cp "$SEED_EVALUATION" "$evaluation_tmp"
    fi
    mv "$tmp" "$DB"
    mv "$manifest_tmp" "$MANIFEST"
    if [ "${REQUIRE_R5_EVALUATION:-0}" = "1" ]; then
        mv "$evaluation_tmp" "$R5_EVALUATION"
    fi
fi

if [ "${RUN_IMPORTERS_ON_BOOT:-0}" = "1" ]; then
    echo "[start] fatal: RUN_IMPORTERS_ON_BOOT is disabled; build a new snapshot before deploy" >&2
    exit 1
fi

if [ ! -s "$DB" ]; then
    echo "[start] fatal: runtime database is empty: $DB" >&2
    exit 1
fi

echo "[start] validating runtime database..."
python - "$DB" "$MANIFEST" "$R5_EVALUATION" <<'PY'
import hashlib
import json
import os
import sqlite3
import sys

path = sys.argv[1]
manifest_path = sys.argv[2]
evaluation_path = sys.argv[3]
uri = f"file:{path}?mode=ro"
conn = sqlite3.connect(uri, uri=True, timeout=5)
try:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise SystemExit(f"runtime database integrity check failed: {integrity}")
    required = {
        "canonical_finding",
        "finding_evidence",
        "evidence_record",
        "dataset_release",
        "source_license",
        "interaction_unified",
        "product_index",
    }
    found = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing = sorted(required - found)
    if missing:
        raise SystemExit("runtime database missing required tables: " + ", ".join(missing))
finally:
    conn.close()

if not os.path.isfile(manifest_path):
    print(f"[start] warning: runtime DB manifest is missing: {manifest_path}", file=sys.stderr)
else:
    with open(manifest_path, encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    expected = manifest.get("snapshot_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise SystemExit("runtime DB manifest has no valid snapshot_sha256")
    digest = hashlib.sha256()
    with open(path, "rb") as database_file:
        for chunk in iter(lambda: database_file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise SystemExit("runtime DB checksum does not match its manifest")
    if manifest.get("integrity") != "ok":
        raise SystemExit("runtime DB manifest is not marked integrity=ok")
if os.environ.get("REQUIRE_R5_EVALUATION", "0") == "1":
    if not os.path.isfile(evaluation_path):
        raise SystemExit("required R5 evaluation report is missing: " + evaluation_path)
    with open(evaluation_path, encoding="utf-8") as evaluation_file:
        evaluation = json.load(evaluation_file)
    if evaluation.get("fixtureVersion") != "r5-safety-matrix.v1":
        raise SystemExit("R5 evaluation report has an unsupported fixture version")
    if evaluation.get("failed") != 0 or evaluation.get("passed") != evaluation.get("total"):
        raise SystemExit("R5 evaluation report is not a complete pass")
PY

echo "[start] starting uvicorn in read-only database mode..."
MEDMATCH_DB_READ_ONLY=1 exec python -m uvicorn backend.app:app \
    --host 0.0.0.0 \
    --port "${PORT:-8080}" \
    --workers "${WEB_CONCURRENCY:-2}"
