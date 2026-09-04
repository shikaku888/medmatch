"""Build a compact read-only runtime snapshot from the full MedMatch DB.

The source database contains raw import material needed for refreshes and
large pharmacovigilance/label staging tables that are not read by the public
API. The runtime image receives only derived tables and request-time indexes.
Raw source files remain outside the image and are used by a separate refresh
workflow.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


# Tables required by the request-time engine/API are retained. These are raw
# staging tables or build-only ontology inputs; their derived products remain
# in the snapshot.
EXCLUDED_TABLES = frozenset(
    {
        # OnSIDES raw release rows; runtime reads onsides_ingredient_effects.
        "onsides_effects_raw",
        # FAERS raw rows; runtime reads faers_adverse_events/faers_counts.
        "fda_drug",
        "fda_indication",
        "fda_therapy",
        "fda_report",
        "fda_reaction",
        "fda_outcome",
        # Canada Vigilance raw rows; no public request path reads these tables.
        "can_dpd_atc",
        "can_dpd_form",
        "can_dpd_ingredient",
        "can_dpd_product",
        "can_dpd_route",
        "can_dpd_schedule",
        "can_dpd_status",
        "can_vig_coprescription",
        "can_vig_drug_ingredient",
        "can_vig_drug_product",
        "can_vig_reaction",
        "can_vig_report_drug",
        "can_vig_report_drug_indication",
        "can_vig_reports",
        # These source tables are used only by offline rebuild/import jobs;
        # product_index and DrugCentral structure/target facts are the runtime views.
        "ndc_products",
        "drugcentral_products",
        "faers_coprescription",
        "zenodo_ddi_2026",
        # matching; trusted mapping results are persisted in smaller tables.
        "rxnorm_attrs",
        "rxnorm_concepts",
        "rxnorm_names",
        "rxnorm_relations",
    }
)

EXCLUDED_INDEXES = frozenset({"idx_faers_events_pt", "idx_faers_events_quarter"})

RUNTIME_INDEXES = (
    # The public FAERS endpoint filters by drug_key first. The source DB had
    # only broad pt/quarter indexes, which both cost space and missed that
    # request path.
    "CREATE INDEX IF NOT EXISTS idx_faers_events_drug_key "
    "ON faers_adverse_events(drug_key)",
)

RUNTIME_SIZE_BUDGET_BYTES = 5_000_000_000

def _faers_runtime_keys(conn: sqlite3.Connection) -> set[str]:
    """Return names reachable by the public class/drug FAERS endpoints."""
    normalize = lambda value: re.sub(
        r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", str(value or "").casefold())
    ).strip()
    keys: set[str] = set()
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drug_classes'"
    ).fetchone():
        for row in conn.execute("SELECT drugs FROM drug_classes"):
            for name in json.loads(row[0] or "[]"):
                if normalize(name):
                    keys.add(normalize(name))
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drug_name_mapping'"
    ).fetchone():
        for row in conn.execute(
            "SELECT raw_name FROM drug_name_mapping WHERE entity_type='drug_ingredient'"
        ):
            if normalize(row[0]):
                keys.add(normalize(row[0]))
    return keys


def prune_faers_runtime(target: sqlite3.Connection) -> int:
    """Drop FAERS aggregate rows unreachable through the public drug APIs."""
    if not target.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='faers_adverse_events'"
    ).fetchone():
        return 0
    keys = _faers_runtime_keys(target)
    if not keys:
        return 0
    before = target.execute("SELECT COUNT(*) FROM faers_adverse_events").fetchone()[0]
    target.execute("CREATE TEMP TABLE _runtime_faers_keys (drug_key TEXT PRIMARY KEY)")
    target.executemany(
        "INSERT OR IGNORE INTO _runtime_faers_keys(drug_key) VALUES (?)",
        ((key,) for key in keys),
    )
    target.execute(
        "DELETE FROM faers_adverse_events "
        "WHERE drug_key NOT IN (SELECT drug_key FROM _runtime_faers_keys)"
    )
    target.execute("DROP TABLE _runtime_faers_keys")
    return before - target.execute("SELECT COUNT(*) FROM faers_adverse_events").fetchone()[0]



def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def source_uri(path: Path) -> str:
    # sqlite accepts this URI form on Windows; Path.as_uri() yields a
    # file:///G:/... URI that the bundled SQLite build rejects for ATTACH.
    return f"file:{path.resolve().as_posix()}?mode=ro"


def manifest_path(snapshot: Path) -> Path:
    return snapshot.with_name(snapshot.name + ".manifest.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}




def build_snapshot(source: Path, output: Path, *, force: bool = False) -> dict[str, int | str]:
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("source and output must be different files")
    if not source.exists():
        raise FileNotFoundError(source)
    if output.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing snapshot: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_tmp = output.with_name(f".{output.name}.build-{os.getpid()}")
    manifest = manifest_path(output)
    manifest_tmp = manifest.with_name(f".{manifest.name}.build-{os.getpid()}")
    previous = output.with_name(output.name + ".previous")
    previous_manifest = manifest_path(previous)
    for path in (snapshot_tmp, manifest_tmp):
        if path.exists():
            path.unlink()

    source_conn = sqlite3.connect(source_uri(source), uri=True, timeout=30)
    source_conn.row_factory = sqlite3.Row
    target = sqlite3.connect(snapshot_tmp, uri=True, timeout=30)
    target.execute("PRAGMA foreign_keys=OFF")
    target.execute("PRAGMA synchronous=FULL")
    target.execute("ATTACH DATABASE ? AS source_db", (source_uri(source),))

    copied_tables = 0
    copied_rows = 0
    copied_indexes = 0
    pruned_faers_rows = 0
    integrity = ""
    build_failed = False
    try:
        objects = source_conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL "
            "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, name"
        ).fetchall()
        tables = [
            row
            for row in objects
            if row["type"] == "table" and row["name"] not in EXCLUDED_TABLES
        ]
        indexes = [
            row
            for row in objects
            if (
                row["type"] == "index"
                and row["tbl_name"] not in EXCLUDED_TABLES
                and row["name"] not in EXCLUDED_INDEXES
            )
        ]

        for row in tables:
            table = row["name"]
            target.execute(row["sql"])
            columns = [
                r[1]
                for r in source_conn.execute(f"PRAGMA table_info({quote_identifier(table)})")
            ]
            if columns:
                cols = ", ".join(quote_identifier(column) for column in columns)
                target.execute(
                    f"INSERT INTO main.{quote_identifier(table)} ({cols}) "
                    f"SELECT {cols} FROM source_db.{quote_identifier(table)}"
                )
                copied_rows += target.execute(
                    f"SELECT COUNT(*) FROM main.{quote_identifier(table)}"
                ).fetchone()[0]
            target.commit()
            copied_tables += 1

        pruned_faers_rows = prune_faers_runtime(target)
        copied_rows -= pruned_faers_rows
        target.commit()

        for row in indexes:
            target.execute(row["sql"])
            copied_indexes += 1
        for sql in RUNTIME_INDEXES:
            if not target.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='faers_adverse_events'"
            ).fetchone():
                continue
            target.execute(sql)
            copied_indexes += 1
        target.commit()

        target.execute("ANALYZE main")
        target.commit()
        target.execute("DETACH DATABASE source_db")
        target.execute("VACUUM")
        target.commit()
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"runtime snapshot integrity check failed: {integrity}")
        if snapshot_tmp.stat().st_size > RUNTIME_SIZE_BUDGET_BYTES:
            raise RuntimeError(
                "runtime snapshot exceeds "
                f"{RUNTIME_SIZE_BUDGET_BYTES} byte budget: {snapshot_tmp.stat().st_size}"
            )
    except Exception:
        build_failed = True
        raise
    finally:
        target.close()
        source_conn.close()
        if build_failed:
            for path in (snapshot_tmp, manifest_tmp):
                if path.exists():
                    path.unlink()

    try:
        snapshot_sha256 = sha256_file(snapshot_tmp)
        old_manifest = read_manifest(manifest)
        rollback_pointer: dict[str, str] | None = None
        if output.exists():
            previous_tmp = previous.with_name(f".{previous.name}.tmp-{os.getpid()}")
            previous_manifest_tmp = previous_manifest.with_name(
                f".{previous_manifest.name}.tmp-{os.getpid()}"
            )
            try:
                if previous_tmp.exists():
                    previous_tmp.unlink()
                shutil.copyfile(output, previous_tmp)
                os.replace(previous_tmp, previous)
                if manifest.exists():
                    if previous_manifest_tmp.exists():
                        previous_manifest_tmp.unlink()
                    shutil.copyfile(manifest, previous_manifest_tmp)
                    os.replace(previous_manifest_tmp, previous_manifest)
                old_sha256 = old_manifest.get("snapshot_sha256") or sha256_file(previous)
                rollback_pointer = {
                    "path": previous.name,
                    "sha256": str(old_sha256),
                }
            finally:
                for path in (previous_tmp, previous_manifest_tmp):
                    if path.exists():
                        path.unlink()

        payload = {
            "schema_version": 1,
            "snapshot_version": f"sha256:{snapshot_sha256[:16]}",
            "snapshot_sha256": snapshot_sha256,
            "snapshot_size_bytes": snapshot_tmp.stat().st_size,
            "source_bytes": source.stat().st_size,
            "copied_tables": copied_tables,
            "copied_rows": copied_rows,
            "pruned_faers_rows": pruned_faers_rows,
            "copied_indexes": copied_indexes,
            "excluded_tables": len(EXCLUDED_TABLES),
            "integrity": integrity,
            "rollback_pointer": rollback_pointer,
        }
        manifest_tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            os.replace(snapshot_tmp, output)
            os.replace(manifest_tmp, manifest)
        except Exception:
            if previous.exists():
                os.replace(previous, output)
                if previous_manifest.exists():
                    os.replace(previous_manifest, manifest)
            elif output.exists():
                output.unlink()
            raise
    finally:
        for path in (snapshot_tmp, manifest_tmp):
            if path.exists():
                path.unlink()
    return {
        "source_bytes": source.stat().st_size,
        "output_bytes": output.stat().st_size,
        "copied_tables": copied_tables,
        "copied_rows": copied_rows,
        "pruned_faers_rows": pruned_faers_rows,
        "copied_indexes": copied_indexes,
        "excluded_tables": len(EXCLUDED_TABLES),
        "integrity": integrity,
        "snapshot_sha256": snapshot_sha256,
        "manifest": str(manifest),
    }




def restore_previous_snapshot(output: Path) -> None:
    previous = output.with_name(output.name + ".previous")
    manifest = manifest_path(output)
    previous_manifest = manifest_path(previous)
    if not previous.is_file():
        raise RuntimeError("evaluation failed and no previous runtime snapshot exists")
    failed = output.with_name(output.name + ".failed")
    failed_manifest = manifest.with_name(manifest.name + ".failed")
    if failed.exists():
        failed.unlink()
    if failed_manifest.exists():
        failed_manifest.unlink()
    if output.exists():
        os.replace(output, failed)
    if manifest.exists():
        os.replace(manifest, failed_manifest)
    os.replace(previous, output)
    if previous_manifest.exists():
        os.replace(previous_manifest, manifest)
    for path in (failed, failed_manifest):
        if path.exists():
            path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("backend/medmatch.db"))
    parser.add_argument("--output", type=Path, default=Path("deploy/runtime/medmatch.db"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--evaluation", action="store_true", help="run R5 fixtures against source before promotion")
    parser.add_argument("--evaluation-output", type=Path, default=Path("deploy/runtime/medmatch.db.evaluation.json"))
    args = parser.parse_args()
    if args.evaluation:
        environment = os.environ.copy()
        environment["MEDMATCH_DB"] = str(args.source.resolve())
        environment["MEDMATCH_DB_READ_ONLY"] = "1"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "backend.evaluate_release",
                "--output",
                str(args.evaluation_output),
            ],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            check=True,
        )
    result = build_snapshot(args.source, args.output, force=args.force)
    if args.evaluation:
        environment = os.environ.copy()
        environment["MEDMATCH_DB"] = str(args.output.resolve())
        environment["MEDMATCH_DB_READ_ONLY"] = "1"
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "backend.evaluate_release",
                    "--output",
                    str(args.evaluation_output),
                ],
                cwd=Path(__file__).resolve().parent.parent,
                env=environment,
                check=True,
            )
        except subprocess.CalledProcessError:
            restore_previous_snapshot(args.output.resolve())
            raise
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
