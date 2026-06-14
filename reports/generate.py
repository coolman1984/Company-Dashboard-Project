"""
generate.py - run report definitions against the database and save them.

Each report is wrapped in a self-describing JSON envelope (the "target report"
format from the roadmap): metadata + columns + rows. CSV output is also
available for spreadsheet users. Mirrors the raw-capture philosophy: an envelope
of metadata around the actual content, so a report is auditable on its own.
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import sqlite3

from .definitions import REPORTS, REPORTS_BY_NAME


def _utc_now_iso():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_report(conn, report):
    """Execute one report -> (columns, rows-as-dicts)."""
    cursor = conn.execute(report.sql)
    columns = [c[0] for c in cursor.description]
    rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
    return columns, rows


def build_envelope(report, columns, rows, db_path, ledger_rows):
    return {
        "report": report.name,
        "title": report.title,
        "description": report.description,
        "generated_at": _utc_now_iso(),
        "source": {
            "database": os.path.basename(db_path),
            "rows_in_ledger": ledger_rows,
        },
        "columns": columns,
        "row_count": len(rows),
        "rows": rows,
    }


def write_json(envelope, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{envelope['report']}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(envelope, handle, ensure_ascii=False, indent=2, default=str)
    return path


def write_csv(envelope, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{envelope['report']}.csv")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=envelope["columns"])
        writer.writeheader()
        writer.writerows(envelope["rows"])
    return path


def generate(db_path, out_dir, names=None, formats=("json",), verbose=True):
    """Generate the requested reports. Returns a list of result dicts."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it (python3 seed_db.py) or load "
            "client data (python3 map_raw_to_db.py) first.")

    selected = REPORTS if not names else [REPORTS_BY_NAME[n] for n in names]
    results = []
    conn = sqlite3.connect(db_path)
    try:
        ledger_rows = conn.execute("SELECT COUNT(*) FROM pl_detail").fetchone()[0]
        for report in selected:
            columns, rows = run_report(conn, report)
            envelope = build_envelope(report, columns, rows, db_path, ledger_rows)
            written = []
            if "json" in formats:
                written.append(write_json(envelope, out_dir))
            if "csv" in formats:
                written.append(write_csv(envelope, out_dir))
            results.append({"report": report.name, "rows": len(rows), "files": written})
            if verbose:
                print(f"  {report.name:<18} {len(rows):>4} rows -> "
                      + ", ".join(os.path.basename(f) for f in written))
    finally:
        conn.close()
    return results
