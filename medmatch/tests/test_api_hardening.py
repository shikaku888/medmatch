from __future__ import annotations

import asyncio
import sqlite3

import pytest

from backend.app import (
    AnalyzeRequest,
    DrugMappingReviewRequest,
    _require_admin,
    analyze,
    ddi_mapping_review_resolve,
)
from backend.scanner.ext_clients import _CircuitBreaker, _CircuitOpen
from backend import app as app_module
from backend import unify


def test_analyze_rejects_oversized_item_list() -> None:
    request = AnalyzeRequest(items=[{"name": f"item-{index}"} for index in range(51)])
    with pytest.raises(Exception) as exc_info:
        asyncio.run(analyze(request))
    assert getattr(exc_info.value, "status_code", None) == 413


def test_admin_review_guard_is_closed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    with pytest.raises(Exception) as exc_info:
        _require_admin(None)
    assert getattr(exc_info.value, "status_code", None) == 503


def test_mapping_review_rejects_invalid_resolution_status(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    payload = DrugMappingReviewRequest(
        source="zenodo_ddi_2026",
        raw_name="unknown",
        status="pending",
    )
    with pytest.raises(Exception) as exc_info:
        asyncio.run(ddi_mapping_review_resolve(payload, "test-token"))
    assert getattr(exc_info.value, "status_code", None) == 400
def test_mapping_review_rejection_removes_untrusted_target(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(unify.SCHEMA)
    conn.execute(
        "INSERT INTO drug_name_mapping "
        "(source, raw_name, normalized_name, entity_type, entity_id, rxcui, "
        "confidence, match_method, reviewed) VALUES (?,?,?,?,?,?,?,?,0)",
        (
            "zenodo_ddi_2026", "Maybe Drug", "maybe drug",
            "drug_ingredient", "123", "123", 0.9, "rxnorm_token_exact",
        ),
    )
    conn.execute(
        "INSERT INTO drug_name_mapping_review "
        "(source, raw_name, reason, entity_type, entity_id, rxcui, confidence, "
        "candidate_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            "zenodo_ddi_2026", "Maybe Drug", "rxnorm_token_exact",
            "drug_ingredient", "123", "123", 0.9, '{"entity_id":"123"}',
        ),
    )
    conn.commit()
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)
    monkeypatch.setattr(unify, "build_unified", lambda _conn: {"pairs": 0})

    result = asyncio.run(ddi_mapping_review_resolve(
        DrugMappingReviewRequest(
            source="zenodo_ddi_2026",
            raw_name="Maybe Drug",
            status="rejected",
            note="Ambiguous candidate",
        ),
        "test-token",
    ))

    mapping = conn.execute(
        "SELECT entity_id, match_method, reviewed FROM drug_name_mapping "
        "WHERE source = ? AND raw_name = ?",
        ("zenodo_ddi_2026", "Maybe Drug"),
    ).fetchone()
    queue = conn.execute(
        "SELECT status, note FROM drug_name_mapping_review "
        "WHERE source = ? AND raw_name = ?",
        ("zenodo_ddi_2026", "Maybe Drug"),
    ).fetchone()
    assert result["status"] == "rejected"
    assert dict(mapping) == {"entity_id": None, "match_method": "unmapped", "reviewed": 1}
    assert dict(queue) == {"status": "rejected", "note": "Ambiguous candidate"}
    conn.close()


def test_reminder_validation_normalizes_schedule() -> None:
    from backend.scanner.router import _validated_reminder

    reminder = _validated_reminder({
        "label": "Morning medication",
        "medication": "Warfarin",
        "time": "08:05",
        "days": [5, 1, 1],
        "enabled": True,
        "timezone": "Asia/Ho_Chi_Minh",
    })
    assert reminder["days"] == [1, 5]
    assert reminder["timezone"] == "Asia/Ho_Chi_Minh"


def test_reminder_validation_rejects_invalid_time() -> None:
    from backend.scanner.router import _validated_reminder

    with pytest.raises(ValueError, match="time must use HH:MM"):
        _validated_reminder({"label": "Invalid", "time": "25:00"})




def test_circuit_breaker_opens_after_repeated_failures() -> None:
    circuit = _CircuitBreaker(threshold=2, cooldown=60)
    circuit.result(False)
    circuit.result(False)
    with pytest.raises(_CircuitOpen):
        circuit.before()


def test_read_only_connection_does_not_mutate_database(tmp_path, monkeypatch) -> None:
    from backend import db

    path = tmp_path / "readonly.db"
    seed = sqlite3.connect(path)
    seed.execute("CREATE TABLE marker (value TEXT)")
    seed.execute("INSERT INTO marker VALUES ('ok')")
    seed.commit()
    seed.close()
    monkeypatch.setenv("MEDMATCH_DB_READ_ONLY", "1")

    conn = db.get_conn(path)
    assert conn.execute("SELECT value FROM marker").fetchone()["value"] == "ok"
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO marker VALUES ('blocked')")
    conn.close()
