from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
CADDY = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")



def test_compose_runs_prebuilt_image_on_vps() -> None:
    assert "build:" not in COMPOSE
    assert "image: medmatch-api:local" in COMPOSE

def test_compose_keeps_runtime_snapshot_read_only_and_state_separate() -> None:
    assert "medmatch.db:/data/medmatch.db:ro" in COMPOSE
    assert "medmatch.db.manifest.json:/data/medmatch.db.manifest.json:ro" in COMPOSE
    assert "medmatch.db.evaluation.json:/data/medmatch.db.evaluation.json:ro" in COMPOSE
    assert "SCANNER_DATA_DIR: /data/devices" in COMPOSE
    assert "RATE_LIMIT_DB: /data/state/rate-limit.db" in COMPOSE
    assert "${MEDMATCH_DEVICES_DIR:-/srv/medmatch/devices}:/data/devices" in COMPOSE
    assert "${MEDMATCH_STATE_DIR:-/srv/medmatch/state}:/data/state" in COMPOSE
    assert "PRODUCT_GRAPH_DB: /data/graph/product-graph.db" in COMPOSE
    assert "${MEDMATCH_GRAPH_DIR:-/srv/medmatch/graph}:/data/graph" in COMPOSE


def test_compose_requires_health_before_public_proxy() -> None:
    assert "condition: service_healthy" in COMPOSE
    assert "http://127.0.0.1:8080/api/health" in COMPOSE
    assert '"80:80"' in COMPOSE
    assert '"443:443"' in COMPOSE


def test_caddy_uses_configured_domain_and_internal_service() -> None:
    assert "{$MEDMATCH_DOMAIN}" in CADDY
    assert "reverse_proxy medmatch:8080" in CADDY
    assert "127.0.0.1" not in CADDY
