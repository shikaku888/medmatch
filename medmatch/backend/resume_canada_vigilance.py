"""Resume a partially ingested Canada Vigilance ZIP member.

The regular importer resumes at table granularity. This utility resumes after
an external timeout interrupts a committed 50k-row batch.

Usage:
    python -m backend.resume_canada_vigilance --member reactions
    python -m backend.resume_canada_vigilance --member report_drug
"""
import argparse
import sqlite3
import zipfile
from pathlib import Path

from .crawler.sources import canada_vigilance as cv
from .db import DB_PATH


def resume_member(conn: sqlite3.Connection, member: str) -> dict:
    table = cv._MEMBER_TABLES[member]
    conn.executescript(cv.SCHEMA)
    already = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    info = None
    with zipfile.ZipFile(cv._fetch_zip()) as zf:
        for candidate in zf.infolist():
            if Path(candidate.filename.replace("\\", "/")).name.lower() == f"{member}.txt":
                info = candidate
                break
    if info is None:
        raise RuntimeError(f"{member}.txt not found in Canada Vigilance ZIP")

    sql, getter = cv._INSERT_SPECS[table]
    n = 0
    inserted = 0
    batch = []
    with zipfile.ZipFile(cv.ZIP_PATH) as zf:
        for vals in cv._iter_member(zf, info):
            n += 1
            if n <= already:
                continue
            batch.append(getter(vals))
            if len(batch) >= 50000:
                conn.executemany(sql, batch)
                conn.commit()
                inserted += len(batch)
                batch = []
                print(f"{member} resumed: {n} source rows, {inserted} inserted")
    if batch:
        conn.executemany(sql, batch)
        conn.commit()
        inserted += len(batch)
    final = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return {"member": member, "source_rows": n, "already": already,
            "inserted": inserted, "final": final}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--member", choices=("report_drug", "reactions"), required=True)
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        print(resume_member(conn, args.member))
        if args.member == "report_drug":
            print({"coprescription": cv.build_coprescription(conn)})
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
