"""Pharmacist review workflow: triage low-trust (inferred) interactions.

CYP-inferred rows (trust 0.5) land in review_queue as pending. A reviewer
verifies (trust bumps to 0.9, shown normally) or rejects (excluded from
analyze results). Verified pairs are remembered by pair_key.

Usage:
    python -m backend.quality_gate seed    # populate queue from cyp inference
"""
import json
import sqlite3
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_key TEXT NOT NULL,
    a_label TEXT NOT NULL,
    b_label TEXT NOT NULL,
    a_kind TEXT NOT NULL,
    b_kind TEXT NOT NULL,
    a_id TEXT NOT NULL,
    b_id TEXT NOT NULL,
    mechanism TEXT,
    trust REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT,
    reviewed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rq_pair ON review_queue(pair_key);
"""


def seed_queue(conn: sqlite3.Connection) -> int:
    """Populate queue with pairs currently inferred via CYP450 (trust 0.5)."""
    conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    n = 0
    roles = conn.execute("SELECT * FROM cyp_roles").fetchall()
    by_entity: dict[tuple, dict[str, set]] = {}
    for r in roles:
        ent = by_entity.setdefault((r["entity_type"], r["entity_id"]),
                                   {"substrate": set(), "inhibitor": set(), "inducer": set()})
        ent[r["role"]].add(r["enzyme"])
    names = {
        ("drug_class", r["id"]): r["name_en"]
        for r in conn.execute("SELECT id, name_en FROM drug_classes")
    }
    names.update({
        ("herb", r["id"]): r["name_en"]
        for r in conn.execute("SELECT id, name_en FROM herbs")
    })
    for (ta, ia), ra in by_entity.items():
        for (tb, ib), rb in by_entity.items():
            a, b = sorted([(ta, ia), (tb, ib)])
            if a == b:
                continue
            if (ta, ia) != a:
                continue  # only seed each unordered pair once
            overlap = (
                (ra.get("inhibitor", set()) & rb.get("substrate", set()))
                | (ra.get("inducer", set()) & rb.get("substrate", set()))
                | (rb.get("inhibitor", set()) & ra.get("substrate", set()))
                | (rb.get("inducer", set()) & ra.get("substrate", set()))
            )
            if not overlap:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO review_queue"
                " (pair_key, a_label, b_label, a_kind, b_kind, a_id, b_id, mechanism, trust)"
                " VALUES (?,?,?,?,?,?,?,?,0.5)",
                (f"cyp:{a[1]}|{b[1]}", names[a], names[b],
                 a[0], b[0], a[1], b[1],
                 f"Enzyme overlap: {', '.join(sorted(overlap))}"),
            )
            n += 1
    conn.commit()
    return n


def next_pending(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM review_queue WHERE status = 'pending' ORDER BY id LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def review(conn: sqlite3.Connection, queue_id: int, status: str, note: str = "") -> bool:
    if status not in ("verified", "rejected"):
        raise ValueError("status must be verified or rejected")
    cur = conn.execute(
        "UPDATE review_queue SET status = ?, note = ?, reviewed_at = datetime('now')"
        " WHERE id = ? AND status = 'pending'",
        (status, note, queue_id),
    )
    conn.commit()
    return cur.rowcount > 0


if __name__ == "__main__":
    from .db import DB_PATH

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "seed":
            print(f"seeded {seed_queue(conn)} pairs")
        else:
            n = conn.execute(
                "SELECT COUNT(*) FROM review_queue WHERE status='pending'"
            ).fetchone()[0]
            print(f"pending reviews: {n}")
    finally:
        conn.close()
