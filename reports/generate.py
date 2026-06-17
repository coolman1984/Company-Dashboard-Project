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

from . import render
from . import safe_str as _safe
from .definitions import REPORTS, REPORTS_BY_NAME


def _utc_now_iso():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_report(conn, report):
    """Execute one report -> (columns, rows-as-dicts, extra-metadata)."""
    if report.builder is not None:
        result = report.builder(conn)
        columns, rows = result[0], result[1]
        extra = result[2] if len(result) > 2 else {}
        return columns, rows, extra
    cursor = conn.execute(report.sql)
    columns = [c[0] for c in cursor.description]
    rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
    return columns, rows, {}


def build_envelope(report, columns, rows, db_path, ledger_rows, extra=None):
    envelope = {
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
    if extra:
        envelope.update(extra)
    return envelope


def write_json(envelope, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{envelope['report']}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(envelope, handle, ensure_ascii=False, indent=2, default=str)
    return path


def write_csv(envelope, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{envelope['report']}.csv")
    # utf-8-sig writes a BOM so Excel (especially on Arabic Windows) opens the
    # file as UTF-8 instead of the local code page, which is what mangles Arabic.
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=envelope["columns"])
        writer.writeheader()
        safe_rows = [
            {k: _safe(v) for k, v in row.items()} for row in envelope["rows"]
        ]
        writer.writerows(safe_rows)
    return path


def _check_formats(formats):
    """Fail fast with an actionable message if a render library is missing."""
    if "xlsx" in formats and not render.excel_available():
        raise RuntimeError("Excel output needs openpyxl (pip install openpyxl).")
    if "pdf" in formats and not render.pdf_available():
        raise RuntimeError("PDF output needs reportlab (pip install reportlab).")


def _run_sql(conn, sql, title=None):
    """Execute a raw SQL string, returning (columns, rows, extra)."""
    cursor = conn.execute(sql)
    columns = [c[0] for c in cursor.description]
    rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
    extra = {}
    if title:
        extra["title"] = title
    return columns, rows, extra


def _run_builder(conn, report):
    """Execute a report that has a builder callable."""
    result = report.builder(conn)
    columns, rows = result[0], result[1]
    extra = result[2] if len(result) > 2 else {}
    return columns, rows, extra


def compute_envelopes(db_path, names=None, client_slug=None):
    """Run the selected reports and return their envelopes (no files written).

    When client_slug is provided, client-specific report SQL from
    workspaces/<slug>/templates.json overrides or extends the catalogue.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it (python3 seed_db.py) or load "
            "client data (python3 map_raw_to_db.py) first.")
    selected = REPORTS if not names else [REPORTS_BY_NAME[n] for n in names]

    # Gather client-specific SQL overrides
    client_sql: dict[str, str] = {}
    if client_slug:
        from .client_templates import get_client_sql as _get_client_sql
        for report in selected:
            sql = _get_client_sql(client_slug, report.name)
            if sql:
                client_sql[report.name] = sql

    conn = sqlite3.connect(db_path)
    try:
        ledger_rows = conn.execute("SELECT COUNT(*) FROM pl_detail").fetchone()[0]
        envelopes = []
        for report in selected:
            if report.name in client_sql:
                # Client-specific report: use the template SQL directly
                columns, rows, extra = _run_sql(conn, client_sql[report.name],
                                                report.title)
            elif report.builder is not None:
                columns, rows, extra = _run_builder(conn, report)
            else:
                columns, rows, extra = _run_sql(conn, report.sql, report.title)
            envelopes.append(build_envelope(report, columns, rows, db_path,
                                            ledger_rows, extra))
        return envelopes
    finally:
        conn.close()


def generate(db_path, out_dir, names=None, formats=("json",), verbose=True,
             client_slug=None):
    """Generate the requested reports, one file per report. Returns result dicts."""
    _check_formats(formats)
    envelopes = compute_envelopes(db_path, names, client_slug=client_slug)
    results = []
    for envelope in envelopes:
        name = envelope["report"]
        written = []
        if "json" in formats:
            written.append(write_json(envelope, out_dir))
        if "csv" in formats:
            written.append(write_csv(envelope, out_dir))
        if "xlsx" in formats:
            written.append(render.render_excel(envelope, os.path.join(out_dir, f"{name}.xlsx")))
        if "pdf" in formats:
            written.append(render.render_pdf(envelope, os.path.join(out_dir, f"{name}.pdf")))
        results.append({"report": name, "rows": envelope["row_count"], "files": written})
        if verbose:
            print(f"  {name:<18} {envelope['row_count']:>4} rows -> "
                  + ", ".join(os.path.basename(f) for f in written))
    return results


def generate_board_pack(db_path, out_dir, names=None, formats=("xlsx", "pdf"),
                        title="Board Pack", verbose=True, client_slug=None):
    """Bundle all selected reports into single combined file(s)."""
    _check_formats(formats)
    envelopes = compute_envelopes(db_path, names, client_slug=client_slug)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    if "xlsx" in formats:
        written.append(render.render_excel_pack(
            envelopes, os.path.join(out_dir, "board-pack.xlsx"), title=title))
    if "pdf" in formats:
        written.append(render.render_pdf_pack(
            envelopes, os.path.join(out_dir, "board-pack.pdf"), title=title))
    if verbose:
        print(f"  Board pack ({len(envelopes)} reports) -> "
              + ", ".join(os.path.basename(f) for f in written))
    return written
