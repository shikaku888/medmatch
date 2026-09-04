from __future__ import annotations

import asyncio
import json

from backend.app import privacy, privacy_page
from backend.scanner import ext_clients


def test_privacy_endpoint_matches_server_side_storage_contract() -> None:
    payload = asyncio.run(privacy())

    assert "server-side" in payload["policy"]
    assert payload["export_endpoint"] == "/api/data/export"
    assert payload["delete_endpoint"] == "/api/data"
    assert payload["purge_endpoint"] == "/api/user-data/purge"
    assert "100 entries" in payload["retention"]
    assert "10 MiB" in payload["retention"]


def test_privacy_policy_is_exposed_at_public_route() -> None:
    response = asyncio.run(privacy_page())

    assert response.media_type == "text/markdown"
    assert str(response.path).replace("\\", "/").endswith("docs/privacy-policy.md")


def test_coverage_telemetry_has_no_device_identifier_and_is_bounded(tmp_path, monkeypatch) -> None:
    path = tmp_path / "coverage_events.jsonl"
    monkeypatch.setattr(ext_clients, "_coverage_file", lambda: path)

    ext_clients.log_coverage("private product", hit=False, source="none")
    first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert first["key"] == "private product"
    assert first["hit"] is False
    assert first["source"] == "none"
    assert "device" not in first

    monkeypatch.setattr(ext_clients, "_COVERAGE_MAX_BYTES", 1)
    ext_clients.log_coverage("new product", hit=True, source="local")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["key"] == "new product"


def test_coverage_stats_redacts_miss_keys_and_reports_duplicates(tmp_path, monkeypatch) -> None:
    path = tmp_path / "coverage_events.jsonl"
    monkeypatch.setattr(ext_clients, "_coverage_file", lambda: path)
    ext_clients.log_coverage("private product", hit=False, source="none", latency_ms=120, unmatched_count=1, severity="major", stale=True)
    ext_clients.log_coverage("private product", hit=False, source="none", latency_ms=240, unmatched_count=1, severity="moderate")
    ext_clients.log_coverage("known product", hit=True, source="openfoodfacts", latency_ms=60)

    stats = ext_clients.coverage_stats()
    assert stats["totalScans"] == 3
    assert stats["uniqueMisses"] == 1
    assert stats["duplicateMissRate"] == 50.0
    assert stats["unmatchedRate"] == 66.7
    assert stats["staleRate"] == 33.3
    assert stats["latencyP50Ms"] == 120.0
    assert stats["latencyP95Ms"] == 240.0
    assert stats["severityCounts"] == {"major": 1, "moderate": 1}
    assert stats["topMisses"][0]["key"] == "redacted"
    assert len(stats["topMisses"][0]["keyHash"]) == 16
