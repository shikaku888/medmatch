#!/usr/bin/env python3
"""Create and restore verified SQLite runtime database backups.

The API opens the runtime database read-only, so SQLite's online backup API can
copy it without stopping the service. Restore writes a verified replacement in
the same directory and uses os.replace for an atomic cutover.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

REQUIRED_TABLES = {
    "canonical_finding",
    "finding_evidence",
    "evidence_record",
    "dataset_release",
    "source_license",
    "interaction_unified",
    "product_index",
}


def _uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _manifest_path(path: Path) -> Path:
    return path.with_name(path.name + ".manifest.json")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_manifest(database: Path, manifest: Path) -> None:
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid database manifest: {manifest}") from exc
    expected = payload.get("snapshot_sha256") if isinstance(payload, dict) else None
    if not isinstance(expected, str) or len(expected) != 64:
        raise RuntimeError(f"database manifest has no valid checksum: {manifest}")
    if _sha256_file(database) != expected:
        raise RuntimeError(f"database checksum does not match manifest: {database}")
    if payload.get("integrity") != "ok":
        raise RuntimeError(f"database manifest is not marked integrity=ok: {manifest}")


def _write_artifact_manifest(database: Path, source_manifest: Path, output: Path) -> None:
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    source_sha256 = payload.get("source_snapshot_sha256") or payload["snapshot_sha256"]
    snapshot_sha256 = _sha256_file(database)
    payload["source_snapshot_sha256"] = source_sha256
    payload["snapshot_sha256"] = snapshot_sha256
    payload["snapshot_size_bytes"] = database.stat().st_size
    payload["snapshot_version"] = f"sha256:{snapshot_sha256[:16]}"
    payload["artifact_type"] = "runtime-backup"
    payload["rollback_pointer"] = None
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"database is missing or empty: {path}")
    with closing(sqlite3.connect(_uri(path), uri=True)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError(f"integrity check failed: {path}")
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        raise RuntimeError(f"required tables missing from {path}: {', '.join(missing)}")


def _backup(source: Path, output: Path, *, force: bool) -> None:
    _validate(source)
    source_manifest = _manifest_path(source)
    if source_manifest.is_file():
        _validate_manifest(source, source_manifest)
    if output.exists() and not force:
        raise RuntimeError(f"output exists; pass --force to replace it: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    temporary_manifest = _manifest_path(temporary)
    output_manifest = _manifest_path(output)
    try:
        for path in (temporary, temporary_manifest):
            if path.exists():
                path.unlink()
        with closing(sqlite3.connect(_uri(source), uri=True)) as source_conn:
            with closing(sqlite3.connect(temporary)) as output_conn:
                source_conn.backup(output_conn)
                output_conn.execute("PRAGMA journal_mode=DELETE")
                output_conn.commit()
        _validate(temporary)
        if source_manifest.is_file():
            _write_artifact_manifest(temporary, source_manifest, temporary_manifest)
            _validate_manifest(temporary, temporary_manifest)
        os.replace(temporary, output)
        if source_manifest.is_file():
            os.replace(temporary_manifest, output_manifest)
        elif output_manifest.exists():
            output_manifest.unlink()
    finally:
        for path in (temporary, temporary_manifest):
            if path.exists():
                path.unlink()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="create a verified backup")
    backup.add_argument("--source", type=Path, required=True)
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--force", action="store_true")

    restore = subparsers.add_parser("restore", help="atomically restore a backup")
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--target", type=Path, required=True)
    restore.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "backup":
            _backup(args.source, args.output, force=args.force)
            print(f"backup_ok source={args.source} output={args.output}")
        else:
            if args.target.exists() and not args.force:
                raise RuntimeError(
                    f"target exists; pass --force to replace it: {args.target}"
                )
            _backup(args.source, args.target, force=True)
            print(f"restore_ok source={args.source} target={args.target}")
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
