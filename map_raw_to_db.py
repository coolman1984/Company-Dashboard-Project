"""
map_raw_to_db.py - load extracted spreadsheet raw JSON into the pl_detail database.

This is the bridge between the extraction engine (extractor/, which captures
client files into raw/*.raw.json) and the dashboard database (pl_detail.db).
Because every client's spreadsheet is laid out differently, the mapping from
their columns to the canonical ledger is described in a small, reviewable JSON
config (see mapping.example.json) rather than hard-coded.

Design goals (production-safe loading of large client captures):
  * Column types come straight from schema.sql - one source of truth, no
    duplicated type list to drift.
  * Strict, actionable validation: required ledger fields (year/version/period),
    known target columns, no duplicate targets, and the project's
    period = year + period_number/1000 encoding. Errors carry file + row.
  * Bounded memory: rows are validated and inserted in batches, never all held
    at once.
  * Indexes are created AFTER the bulk insert (the documented SQLite plan).
  * Failure-safe: the database is built in a temporary file, integrity-checked,
    and only then atomically swapped in. A failed load never corrupts or
    replaces an existing dashboard database.

Usage:
    python3 map_raw_to_db.py --mapping mapping.example.json --dry-run
    python3 map_raw_to_db.py --mapping mapping.example.json
    python3 map_raw_to_db.py --mapping mapping.example.json --force
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import math
import os
import re
import sqlite3
import sys
import tempfile

from extractor import arabic
import import_workspace as iw
import db_schema

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
DEFAULT_RAW_DIR = os.path.join(BASE_DIR, "raw")
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "pl_detail.db")

INSERT_BATCH = 10_000
REQUIRED_FIELDS = ("year", "version", "period")
VALID_VERSIONS = ("Actual", "T06", "T07")


class MappingError(Exception):
    """Configuration or data problem the operator must fix."""


# --------------------------------------------------------------------------- #
# Schema (single source of truth for column names and types)
# --------------------------------------------------------------------------- #
def load_schema_columns(schema_path=SCHEMA_PATH):
    """Parse `CREATE TABLE pl_detail (...)` from schema.sql -> {column: type}.

    Thin wrapper over the canonical db_schema module so there is exactly one
    parser shared by every load path (mapper, seed, COM ingest).
    """
    try:
        return db_schema.column_types(schema_path)
    except ValueError as error:
        raise MappingError(str(error))


def split_schema_statements(schema_path=SCHEMA_PATH):
    """Return (table_ddl, post_ddl): table/drop first, indexes+views after.

    Lets us create the table, bulk-insert, THEN build indexes and views, which
    matches the project's documented performance plan for large loads. Delegates
    to db_schema so all paths split the schema identically.
    """
    return db_schema.split_statements(schema_path)


# --------------------------------------------------------------------------- #
# Mapping config
# --------------------------------------------------------------------------- #
def load_mapping(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            mapping = json.load(handle)
    except FileNotFoundError:
        raise MappingError(f"Mapping file not found: {path}")
    except json.JSONDecodeError as error:
        raise MappingError(f"Mapping file is not valid JSON: {error}")
    if not isinstance(mapping, dict):
        raise MappingError("Mapping must be a JSON object.")
    return mapping


def validate_mapping(mapping, schema_columns):
    """Fail fast on malformed config before we touch any data."""
    columns = mapping.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise MappingError("Mapping must include a non-empty 'columns' object "
                           "(spreadsheet header -> database column).")
    constants = mapping.get("constants", {})
    if not isinstance(constants, dict):
        raise MappingError("'constants' must be an object (column -> value).")
    if not mapping.get("source_glob"):
        raise MappingError("Mapping must include 'source_glob' "
                           "(which raw files to load, e.g. '*PL*.raw.json').")
    if not (mapping.get("sheet") or "sheet_index" in mapping):
        raise MappingError("Mapping must include 'sheet' (name) or 'sheet_index'.")

    targets = list(columns.values()) + list(constants.keys())
    unknown = sorted(set(t for t in targets if t not in schema_columns))
    if unknown:
        raise MappingError(
            "Unknown target column(s) not in schema.sql: " + ", ".join(unknown))

    seen, duplicates = set(), set()
    for target in targets:
        if target in seen:
            duplicates.add(target)
        seen.add(target)
    if duplicates:
        raise MappingError(
            "Duplicate target column(s) mapped more than once: "
            + ", ".join(sorted(duplicates)))

    missing = [f for f in REQUIRED_FIELDS if f not in seen]
    if missing:
        raise MappingError(
            "Required ledger field(s) not provided by columns or constants: "
            + ", ".join(missing))


# --------------------------------------------------------------------------- #
# Value conversion + record validation
# --------------------------------------------------------------------------- #
def convert(value, sql_type, where):
    """Coerce a raw cell to its schema type, with context on failure.

    Text is cleaned of invisible bidi/format junk and tatweel (but never letter-
    folded), and numbers are parsed with the Arabic-aware parser so Arabic-Indic
    digits, ٬/٫ separators, currency and accounting negatives all work.
    """
    if value is None or value == "":
        return None
    try:
        if sql_type == "TEXT":
            cleaned = arabic.clean_display(value)
            return cleaned if cleaned != "" else None
        if sql_type == "INTEGER":
            number = arabic.parse_number(value)
            if number is None:
                return None
            if not math.isfinite(number):
                raise MappingError(f"{where}: non-finite number {value!r} (NaN/Infinity).")
            return int(round(number))
        if sql_type == "REAL":
            number = arabic.parse_number(value)
            if number is None:
                return None
            number = float(number)
            # NaN/Infinity would poison every SUM in the views and serialise as
            # null over the API — reject them at the door.
            if not math.isfinite(number):
                raise MappingError(f"{where}: non-finite number {value!r} (NaN/Infinity).")
            return number
    except (ValueError, TypeError):
        raise MappingError(f"{where}: cannot convert {value!r} to {sql_type}.")
    return value


def validate_required(record, where):
    """Enforce the project's year / version / period conventions."""
    year = record.get("year")
    if not isinstance(year, int) or not (1900 <= year <= 2100):
        raise MappingError(f"{where}: 'year' must be a 4-digit year, got {year!r}.")

    version = record.get("version")
    if version not in VALID_VERSIONS:
        raise MappingError(
            f"{where}: 'version' must be one of {VALID_VERSIONS}, got {version!r}.")

    period = record.get("period")
    if not isinstance(period, (int, float)):
        raise MappingError(f"{where}: 'period' is required, got {period!r}.")
    # Accept a bare period number (1-12) and encode it as year + n/1000.
    if float(period).is_integer() and 1 <= int(period) <= 12:
        period = round(year + int(period) / 1000.0, 3)
        record["period"] = period
    int_part = int(period)
    number = round((period - int_part) * 1000)
    if int_part != year or not (1 <= number <= 12):
        raise MappingError(
            f"{where}: 'period' {period!r} must follow year + period_number/1000 "
            f"(e.g. {year}.001..{year}.012).")


# --------------------------------------------------------------------------- #
# Reading raw captures
# --------------------------------------------------------------------------- #
def find_raw_files(raw_dir, source_glob):
    files = []
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.raw.json"))):
        if fnmatch.fnmatch(os.path.basename(path), source_glob):
            files.append(path)
    return files


def select_sheet(envelope, mapping, where):
    sheets = (envelope.get("content") or {}).get("sheets") or []
    if not sheets:
        raise MappingError(f"{where}: no sheets in capture.")
    if mapping.get("sheet"):
        target = arabic.match_key(mapping["sheet"])
        for sheet in sheets:
            if arabic.match_key(sheet.get("name")) == target:
                return sheet
        raise MappingError(f"{where}: sheet '{mapping['sheet']}' not found "
                           f"(available: {[s.get('name') for s in sheets]}).")
    index = int(mapping.get("sheet_index", 0))
    if index >= len(sheets):
        raise MappingError(f"{where}: sheet_index {index} out of range.")
    return sheets[index]


def iter_records(mapping, schema_columns, raw_dir):
    """Yield (record_dict, where) for every data row across matching files."""
    header_row = int(mapping.get("header_row", 0))
    skip_blank = mapping.get("skip_blank_rows", True)
    constants = mapping.get("constants", {})
    columns = mapping["columns"]

    files = find_raw_files(raw_dir, mapping["source_glob"])
    if not files:
        raise MappingError(
            f"No raw files in {raw_dir} matched '{mapping['source_glob']}'. "
            "Run the extractor first.")

    for path in files:
        fname = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as handle:
            envelope = json.load(handle)
        sheet = select_sheet(envelope, mapping, fname)
        cells = sheet.get("cells") or []
        if header_row >= len(cells):
            raise MappingError(f"{fname}: header_row {header_row} beyond sheet.")
        headers = [str(h) if h is not None else "" for h in cells[header_row]]

        # Match on the Arabic-normalized key so a header still matches across
        # spelling variants, diacritics, tatweel and stray bidi/format marks.
        header_index_by_key = {}
        for position, header in enumerate(headers):
            key = arabic.match_key(header)
            if key and key not in header_index_by_key:
                header_index_by_key[key] = position

        index_of = {}
        for source_header in columns:
            key = arabic.match_key(source_header)
            if key not in header_index_by_key:
                raise MappingError(
                    f"{fname}, sheet '{sheet.get('name')}': mapped header "
                    f"'{source_header}' not found in {headers}.")
            index_of[source_header] = header_index_by_key[key]

        for row_no, row in enumerate(cells[header_row + 1:], start=header_row + 2):
            if skip_blank and not any(c not in (None, "") for c in row):
                continue
            where = f"{fname} row {row_no}"
            record = dict(constants)
            for source_header, target in columns.items():
                idx = index_of[source_header]
                value = row[idx] if idx < len(row) else None
                record[target] = convert(value, schema_columns[target], where)
            validate_required(record, where)
            yield record, where


# --------------------------------------------------------------------------- #
# Database build (temp file -> integrity check -> atomic replace)
# --------------------------------------------------------------------------- #
_PL_IDENTITY_TOLERANCE = 1.0
_GRAIN_COLS = ("year", "version", "period",
               "region_desc", "country_name", "customer_name", "m_group_desc")


def _validate_loaded_data(conn, stats):
    # Fatal issues mean the database is structurally unusable for the dashboard
    # (no data, ambiguous grain, missing required keys) — these abort the load
    # so the live database is never swapped out for a broken one. Warnings flag
    # data-quality concerns (e.g. P&L arithmetic drift) that are worth surfacing
    # but may be legitimate source artifacts, so they don't block the swap.
    fatal = []
    warnings = []

    row = conn.execute("SELECT COUNT(*) FROM pl_detail").fetchone()
    total = row[0] if row else 0
    if total == 0:
        fatal.append("No rows loaded.")

    gross_margin_failures = conn.execute("""
        SELECT COUNT(*) FROM pl_detail
        WHERE ABS(gross_margin - (net_sales - cost_of_goods_sold)) > ?
    """, (_PL_IDENTITY_TOLERANCE,)).fetchone()[0]
    if gross_margin_failures > 0:
        warnings.append(f"{gross_margin_failures} rows where gross_margin != net_sales - cogs "
                        f"(tolerance {_PL_IDENTITY_TOLERANCE}).")

    grain_cols_expr = ", ".join(_GRAIN_COLS)
    dups = conn.execute(f"""
        SELECT {grain_cols_expr}, COUNT(*) AS cnt
        FROM pl_detail
        WHERE year IS NOT NULL
        GROUP BY {grain_cols_expr}
        HAVING cnt > 1
        LIMIT 1
    """).fetchone()
    if dups:
        fatal.append(
            f"Duplicate grain rows found (sample: {dict(zip(_GRAIN_COLS, dups))}).")

    null_counts = {}
    for col in ("year", "version", "period", "net_sales"):
        n = conn.execute(
            f"SELECT COUNT(*) FROM pl_detail WHERE {col} IS NULL").fetchone()[0]
        if n > 0:
            null_counts[col] = n
    if null_counts:
        fatal.append(f"Null values in required columns: {null_counts}.")

    coverage = conn.execute("""
        SELECT year, version, COUNT(DISTINCT period) AS periods, COUNT(*) AS rows
        FROM pl_detail
        GROUP BY year, version
        ORDER BY year, version
    """).fetchall()
    coverage_lines = [f"  {r[0]} {r[1]:6s}  {r[2]:2d} periods  {r[3]:,d} rows"
                      for r in coverage]

    years = sorted(set(r[0] for r in coverage))
    versions = sorted(set(r[1] for r in coverage))
    stats["validation"] = {
        "total_rows": total,
        "years": years,
        "versions": versions,
        "coverage": [{"year": r[0], "version": r[1], "periods": r[2], "rows": r[3]}
                     for r in coverage],
        "pandl_identity_failures": gross_margin_failures,
        "fatal": fatal,
        "warnings": warnings,
        # Back-compat: combined view of everything flagged.
        "issues": fatal + warnings,
    }

    print(f"  validation    : {total:,d} rows, {len(years)} years, {len(versions)} versions")
    if warnings:
        print("  WARNINGS:")
        for warning in warnings:
            print(f"    - {warning}")
    else:
        print("  WARNINGS      : none")
    for line in coverage_lines:
        print(line)

    if fatal:
        print("  FATAL:")
        for issue in fatal:
            print(f"    - {issue}")
        raise MappingError(
            "Post-load validation failed; database not swapped in. "
            + " ".join(fatal))


def load(mapping_path, raw_dir=DEFAULT_RAW_DIR, db_path=DEFAULT_DB_PATH,
         dry_run=False, force=False, batch_size=INSERT_BATCH, verbose=True,
         client_id=None, use_workspace=True):
    """Load raw captures into pl_detail.db.

    Phase 2: when `client_id` is provided (and use_workspace is True), the load
    also:
      * creates a per-run workspace under workspaces/<client>/runs/<run-id>/
      * snapshots the matched raw captures into the run's raw/ folder
      * copies the existing database to <run>/db-before.db
      * writes a per-run validation.json
      * appends an entry to import_history.json (status: success/failed)
    When client_id is None the function behaves exactly as before.
    """
    schema_columns = load_schema_columns()
    mapping = load_mapping(mapping_path)
    validate_mapping(mapping, schema_columns)

    if os.path.exists(db_path) and not dry_run and not force:
        raise MappingError(
            f"{db_path} already exists. Re-run with --force to overwrite it.")

    # Phase 2: prepare the per-run workspace if a client_id was supplied.
    run_path = None
    history_entry = None
    backup_path = ""
    effective_client = client_id
    run_id = iw.make_run_id()
    workspace_log_path = None

    if effective_client and use_workspace and not dry_run:
        run_path = iw.run_workspace(effective_client, run_id)
        iw.ensure_run_dirs(run_path)
        # Copy the raw files this run will consume (best-effort, never fatal).
        try:
            iw.copy_raw_inputs(raw_dir, mapping["source_glob"], run_path / "raw")
        except Exception as exc:  # noqa: BLE001 — we never want a copy issue
            # to abort a real load; the run will still proceed.
            if verbose:
                print(f"  warning       : could not snapshot raw inputs ({exc})")
        # Back up the live database before the atomic swap.
        try:
            backup_path = iw.backup_database(db_path, run_path)
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"  warning       : could not back up existing database ({exc})")
        # Mirror load output to logs/load.log for post-hoc debugging.
        workspace_log_path = run_path / "logs" / iw.LOG_FILENAME
        workspace_log_path.parent.mkdir(parents=True, exist_ok=True)
        # Parse the run_id into a proper ISO timestamp.
        # run_id format: run-YYYYMMDD-HHMMSS-microseconds
        parts = run_id.split("-")
        # parts = ['run', '20260615', '130000', '123456']
        date_part = parts[1]  # 20260615
        time_part = parts[2]  # 130000
        micro_part = parts[3] if len(parts) > 3 else "000000"
        iso_ts = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}T{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}.{micro_part}"
        history_entry = {
            "run_id": run_id,
            "timestamp": iso_ts,
            "client_id": effective_client,
            "mapping": str(mapping_path),
            "status": "running",
            "row_count": 0,
            "warnings": [],
            "fatal": [],
        }
        try:
            iw.append_history(effective_client, history_entry)
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"  warning       : could not append to import_history ({exc})")

    ordered_targets = list(dict.fromkeys(
        list(mapping["columns"].values()) + list(mapping.get("constants", {}).keys())
    ))
    table_ddl, post_ddl = split_schema_statements()

    stats = {"files": len(find_raw_files(raw_dir, mapping["source_glob"])),
             "rows_read": 0, "rows_inserted": 0, "batches": 0}

    # Dry run: validate + convert everything, write nothing.
    if dry_run:
        for _record, _where in iter_records(mapping, schema_columns, raw_dir):
            stats["rows_read"] += 1
        if verbose:
            _report(stats, db_path, dry_run=True)
        return stats

    fd, tmp_path = tempfile.mkstemp(prefix=".pl_detail.", suffix=".tmp",
                                    dir=os.path.dirname(db_path) or ".")
    os.close(fd)
    os.remove(tmp_path)  # sqlite will create it fresh
    final_validation = None
    load_succeeded = False
    failure_error = None
    try:
        conn = sqlite3.connect(tmp_path)
        try:
            for stmt in table_ddl:
                conn.execute(stmt)

            placeholders = ", ".join("?" for _ in ordered_targets)
            col_list = ", ".join(f'"{c}"' for c in ordered_targets)
            insert_sql = f"INSERT INTO pl_detail ({col_list}) VALUES ({placeholders})"

            batch = []
            for record, _where in iter_records(mapping, schema_columns, raw_dir):
                stats["rows_read"] += 1
                batch.append(tuple(record.get(c) for c in ordered_targets))
                if len(batch) >= batch_size:
                    conn.executemany(insert_sql, batch)
                    stats["rows_inserted"] += len(batch)
                    stats["batches"] += 1
                    batch.clear()
            if batch:
                conn.executemany(insert_sql, batch)
                stats["rows_inserted"] += len(batch)
                stats["batches"] += 1

            # Build indexes + views AFTER the bulk load.
            for stmt in post_ddl:
                conn.execute(stmt)
            conn.commit()

            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise MappingError(f"Integrity check failed on new database: {integrity}")

            _validate_loaded_data(conn, stats)
            final_validation = stats.get("validation", {})
        finally:
            conn.close()

        os.replace(tmp_path, db_path)  # atomic swap; existing DB only now replaced
        load_succeeded = True
    except BaseException as exc:
        failure_error = str(exc)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)  # never leave a half-built file or touch the live DB
        # Surface the failure in the per-run history (best-effort).
        if run_path is not None and effective_client is not None:
            try:
                iw.write_validation(run_path, {
                    "status": "failed",
                    "error": failure_error,
                    "row_count": stats.get("rows_inserted", 0),
                })
                iw.update_run(effective_client, run_id,
                              status="failed",
                              error=failure_error,
                              row_count=stats.get("rows_inserted", 0),
                              run_path=str(run_path))
            except Exception:  # noqa: BLE001
                pass
        raise
    finally:
        # On success, persist the validation.json and update the history.
        if load_succeeded and run_path is not None and effective_client is not None:
            try:
                payload = dict(final_validation or {})  # type: ignore[arg-type]
                payload["status"] = "success"
                payload["row_count"] = stats.get("rows_inserted", 0)
                iw.write_validation(run_path, payload)
                iw.update_run(effective_client, run_id,
                              status="success",
                              row_count=stats.get("rows_inserted", 0),
                              backup_path=backup_path,
                              run_path=str(run_path))
            except Exception:  # noqa: BLE001
                pass
        if workspace_log_path is not None:
            try:
                workspace_log_path.write_text(
                    f"run_id={run_id}\nstatus={'success' if load_succeeded else 'failed'}\n"
                    f"row_count={stats.get('rows_inserted', 0)}\n"
                    f"error={failure_error or ''}\n",
                    encoding="utf-8",
                )
            except Exception:  # noqa: BLE001
                pass

    if verbose:
        _report(stats, db_path, dry_run=False)
    return stats


def _report(stats, db_path, dry_run):
    label = "DRY RUN (no database written)" if dry_run else f"Wrote {db_path}"
    print(label)
    print(f"  files matched : {stats['files']}")
    print(f"  rows read     : {stats['rows_read']}")
    if not dry_run:
        print(f"  rows inserted : {stats['rows_inserted']}")
        print(f"  insert batches: {stats['batches']}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Map extracted spreadsheet raw JSON into pl_detail.db.")
    parser.add_argument("--mapping", required=True, help="Client mapping JSON file.")
    parser.add_argument("--raw", default=DEFAULT_RAW_DIR, help="Folder of raw captures.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Output database path.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and convert everything; write nothing.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing database.")
    parser.add_argument("--client", default=None,
                        help="Phase 2: client_id for the import-run workspace "
                             "(creates workspaces/<client>/runs/<run>/ and "
                             "snapshots raw + db before swapping).")
    parser.add_argument("--no-workspace", action="store_true",
                        help="Phase 2: skip the workspace scaffolding even if "
                             "--client is provided (rarely useful).")
    args = parser.parse_args(argv)
    try:
        load(args.mapping, raw_dir=args.raw, db_path=args.db,
             dry_run=args.dry_run, force=args.force,
             client_id=args.client, use_workspace=not args.no_workspace)
    except MappingError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
