from __future__ import annotations

import json
import sqlite3

import pytest

import deploy.build_runtime_db as builder


_REQUIRED_TABLES = {
    "canonical_finding",
    "finding_evidence",
    "evidence_record",
    "dataset_release",
    "source_license",
    "interaction_unified",
    "product_index",
    "faers_adverse_events",
}


def _make_source(path) -> None:
    with sqlite3.connect(path) as conn:
        for table in _REQUIRED_TABLES:
            column = "drug_key TEXT" if table == "faers_adverse_events" else "value TEXT"
            conn.execute(f"CREATE TABLE {table} ({column})")
        conn.execute("CREATE TABLE fda_drug (value TEXT)")
        conn.execute("INSERT INTO interaction_unified(value) VALUES ('initial')")


def test_snapshot_manifest_and_rollback_pointer(tmp_path) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "runtime.db"
    _make_source(source)

    first = builder.build_snapshot(source, output)
    first_manifest = json.loads(
        builder.manifest_path(output).read_text(encoding="utf-8")
    )
    assert first_manifest["snapshot_sha256"] == builder.sha256_file(output)
    assert first_manifest["snapshot_version"].startswith("sha256:")
    assert first_manifest["rollback_pointer"] is None
    assert first["integrity"] == "ok"

    with sqlite3.connect(source) as conn:
        conn.execute("INSERT INTO interaction_unified(value) VALUES ('updated')")

    builder.build_snapshot(source, output, force=True)
    second_manifest = json.loads(
        builder.manifest_path(output).read_text(encoding="utf-8")
    )
    pointer = second_manifest["rollback_pointer"]
    previous = output.with_name(output.name + ".previous")
    assert pointer["path"] == previous.name
    assert pointer["sha256"] == first_manifest["snapshot_sha256"]
    assert builder.sha256_file(previous) == first_manifest["snapshot_sha256"]



def test_runtime_prunes_unreachable_faers_and_records_size(tmp_path) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "runtime.db"
    _make_source(source)
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE drug_classes (drugs TEXT)")
        conn.execute(
            "INSERT INTO drug_classes(drugs) VALUES (?)",
            (json.dumps(["Aspirin"]),),
        )
        conn.execute(
            "INSERT INTO faers_adverse_events(drug_key) VALUES ('aspirin'), ('unreachable')"
        )

    result = builder.build_snapshot(source, output)
    manifest = json.loads(builder.manifest_path(output).read_text(encoding="utf-8"))
    with sqlite3.connect(output) as conn:
        assert conn.execute("SELECT COUNT(*) FROM faers_adverse_events").fetchone()[0] == 1
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='fda_drug'"
        ).fetchone() is None
    assert result["pruned_faers_rows"] == 1
    assert manifest["pruned_faers_rows"] == 1
    assert manifest["snapshot_size_bytes"] == output.stat().st_size


def test_runtime_size_budget_rejects_oversized_candidate(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "runtime.db"
    _make_source(source)
    monkeypatch.setattr(builder, "RUNTIME_SIZE_BUDGET_BYTES", 1)

    with pytest.raises(RuntimeError, match="exceeds .* byte budget"):
        builder.build_snapshot(source, output)

    assert not output.exists()

def test_failed_snapshot_refresh_preserves_accepted_output(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "runtime.db"
    _make_source(source)
    builder.build_snapshot(source, output)
    accepted_hash = builder.sha256_file(output)

    monkeypatch.setattr(
        builder,
        "RUNTIME_INDEXES",
        ("CREATE INDEX broken ON missing_table(value)",),
    )
    with pytest.raises(sqlite3.OperationalError):
        builder.build_snapshot(source, output, force=True)



def test_evaluation_failure_restore_returns_previous_snapshot(tmp_path) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "runtime.db"
    _make_source(source)
    builder.build_snapshot(source, output)
    accepted_hash = builder.sha256_file(output)
    with sqlite3.connect(source) as conn:
        conn.execute("INSERT INTO interaction_unified(value) VALUES ('candidate')")
    builder.build_snapshot(source, output, force=True)
    assert builder.sha256_file(output) != accepted_hash

    builder.restore_previous_snapshot(output)

    assert builder.sha256_file(output) == accepted_hash
    manifest = json.loads(builder.manifest_path(output).read_text(encoding="utf-8"))
    assert manifest["snapshot_sha256"] == accepted_hash
