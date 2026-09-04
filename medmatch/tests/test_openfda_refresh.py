from __future__ import annotations

import asyncio
import io
import json
import sqlite3
from email.message import Message

from backend import app as app_module
from backend.refresh_openfda import SCHEMA, fetch_page, refresh


def _record() -> dict:
    return {
        "id": "label-sirolimus-1",
        "effective_time": "20260902",
        "openfda": {
            "generic_name": ["SIROLIMUS"],
            "brand_name": ["RAPAMUNE"],
            "spl_set_id": ["set-sirolimus"],
        },
        "boxed_warning": ["Serious warning"],
        "warnings": ["Monitor patients."],
        "drug_interactions": ["Avoid strong CYP3A4 inhibitors."],
        "pregnancy": ["Use only when benefit outweighs risk."],
        "nursing_mothers": ["Discontinue nursing or treatment."],
        "pediatric_use": ["Safety below age 13 is not established."],
    }


def test_refresh_upserts_label_manifest_and_release() -> None:
    conn = sqlite3.connect(":memory:")
    result = refresh(conn, ["sirolimus"], fetcher=lambda _: ([_record()], "2026-09-02"))

    assert result == {"requested": 1, "ok": 1, "empty": 0, "errors": 0, "labels": 1}
    row = conn.execute(
        "SELECT generic_name, brand_name, warnings_and_precautions, lactation, source "
        "FROM openfda_label_sections"
    ).fetchone()
    assert tuple(row) == (
        "SIROLIMUS",
        "RAPAMUNE",
        "Monitor patients.",
        "Discontinue nursing or treatment.",
        "openFDA",
    )
    manifest = conn.execute(
        "SELECT status, attempts, note FROM crawl_manifest WHERE source='openfda' AND item_key='sirolimus'"
    ).fetchone()
    assert tuple(manifest) == ("ok", 1, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM dataset_release WHERE source_code='openfda'"
    ).fetchone()[0] == 1
    conn.close()


def test_refresh_failure_preserves_previous_label_and_records_error() -> None:
    conn = sqlite3.connect(":memory:")
    refresh(conn, ["sirolimus"], fetcher=lambda _: ([_record()], None))

    def fail(_: str):
        raise RuntimeError("temporary upstream failure")

    result = refresh(conn, ["sirolimus"], fetcher=fail)
    assert result["errors"] == 1
    assert conn.execute("SELECT COUNT(*) FROM openfda_label_sections").fetchone()[0] == 1
    status, attempts, note = conn.execute(
        "SELECT status, attempts, note FROM crawl_manifest WHERE source='openfda' AND item_key='sirolimus'"
    ).fetchone()
    assert (status, attempts) == ("error", 2)
    assert "temporary upstream failure" in note
    conn.close()


def test_fetch_page_retries_rate_limit() -> None:
    calls = []
    sleeps = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        if len(calls) == 1:
            headers = Message()
            headers["Retry-After"] = "0"
            raise __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
                request.full_url, 429, "rate limited", headers, io.BytesIO()
            )
        return Response(json.dumps({"results": [{"id": "ok"}]}).encode())

    payload = fetch_page("sirolimus", retries=1, opener=opener, sleep=sleeps.append)
    assert payload["results"][0]["id"] == "ok"
    assert len(calls) == 2
    assert sleeps == [0.0]


def test_label_api_reads_refreshed_openfda_sections(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("CREATE TABLE drug_classes (id TEXT PRIMARY KEY, drugs TEXT)")
    refresh(conn, ["sirolimus"], fetcher=lambda _: ([_record()], None))
    monkeypatch.setattr(app_module, "get_conn", lambda: conn)

    payload = asyncio.run(app_module.drug_label("sirolimus"))

    sections = {item["section"]: item for item in payload["sections"]}
    assert sections["warnings_and_precautions"]["source"] == "openFDA"
    assert sections["pregnancy"]["text"] == "Use only when benefit outweighs risk."
    assert sections["lactation"]["source_url"].startswith("https://api.fda.gov/drug/label.json")
    conn.close()
