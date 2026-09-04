from __future__ import annotations

import json
import sqlite3

import deploy.build_runtime_db as builder
from deploy import backup_runtime_db


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


def test_backup_and_restore_carry_runtime_manifest(tmp_path) -> None:
    source = tmp_path / "source.db"
    accepted = tmp_path / "accepted.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    _make_source(source)
    builder.build_snapshot(source, accepted)

    backup_runtime_db._backup(accepted, backup, force=False)
    backup_runtime_db._backup(backup, restored, force=False)
    source_manifest = builder.manifest_path(accepted).read_text(encoding="utf-8")
    backup_manifest = backup_runtime_db._manifest_path(backup)
    restored_manifest = backup_runtime_db._manifest_path(restored)
    assert json.loads(backup_manifest.read_text(encoding="utf-8"))["artifact_type"] == "runtime-backup"
    assert json.loads(restored_manifest.read_text(encoding="utf-8"))["artifact_type"] == "runtime-backup"
    assert json.loads(backup_manifest.read_text(encoding="utf-8"))["source_snapshot_sha256"] == (
        json.loads(source_manifest)["snapshot_sha256"]
    )
    assert json.loads(restored_manifest.read_text(encoding="utf-8"))["source_snapshot_sha256"] == (
        json.loads(source_manifest)["snapshot_sha256"]
    )
    assert json.loads(backup_manifest.read_text(encoding="utf-8"))["snapshot_sha256"] == (
        builder.sha256_file(backup)
    )
    assert json.loads(restored_manifest.read_text(encoding="utf-8"))["snapshot_sha256"] == (
        builder.sha256_file(restored)
    )
    assert builder.sha256_file(restored) == builder.sha256_file(backup)
