from __future__ import annotations

import sqlite3

from backend.db_cleanup import deduplicate_table


def test_deduplicate_table_keeps_schema_and_index() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE onsides_effects_raw (
            row_id INTEGER PRIMARY KEY,
            product_label_id TEXT NOT NULL,
            source_region TEXT NOT NULL,
            effect_meddra_id TEXT NOT NULL,
            effect TEXT NOT NULL
        );
        CREATE INDEX idx_raw_region ON onsides_effects_raw(source_region);
        INSERT INTO onsides_effects_raw VALUES
            (10, 'label-1', 'US', '1001', 'Headache'),
            (11, 'label-1', 'US', '1001', 'Headache'),
            (12, 'label-2', 'EU', '1002', 'Nausea');
        """
    )

    result = deduplicate_table(
        conn,
        "onsides_effects_raw",
        ("product_label_id", "source_region", "effect_meddra_id", "effect"),
        surrogate_column="row_id",
    )

    assert result == {
        "table": "onsides_effects_raw",
        "before": 3,
        "after": 2,
        "removed": 1,
        "status": "cleaned",
    }
    assert conn.execute("PRAGMA table_info(onsides_effects_raw)").fetchone()[1] == "row_id"
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='idx_raw_region'"
    ).fetchone()[0] == 1
    assert conn.execute("SELECT row_id FROM onsides_effects_raw ORDER BY row_id").fetchall() == [
        (10,),
        (12,),
    ]
    conn.close()


def test_deduplicate_table_removes_exact_rows_without_surrogate() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE fda_reaction (
            primaryid TEXT,
            caseid TEXT,
            pt TEXT,
            drug_rec_act TEXT,
            quarter TEXT
        );
        INSERT INTO fda_reaction VALUES
            ('1', '1', 'Headache', NULL, '2026Q2'),
            ('1', '1', 'Headache', NULL, '2026Q2'),
            ('2', '2', 'Nausea', NULL, '2026Q2');
        """
    )

    result = deduplicate_table(
        conn,
        "fda_reaction",
        ("primaryid", "caseid", "pt", "drug_rec_act", "quarter"),
    )

    assert result["before"] == 3
    assert result["after"] == 2
    assert result["removed"] == 1
    assert conn.execute("SELECT COUNT(*) FROM fda_reaction").fetchone()[0] == 2
    conn.close()
