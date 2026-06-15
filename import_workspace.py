"""
import_workspace.py — per-client import-run scaffolding (Phase 2).

Owns the directory layout for a real client import:

    workspaces/<client>/runs/<run-id>/
        raw/                  (copies of input raw captures used by the run)
        logs/load.log         (stdout mirror of map_raw_to_db)
        reports/              (reserved for future per-run exports)
        validation.json       (post-load validation summary)
        db-before.db          (previous good database; empty on first run)
        db-after.db           (newly built database before the atomic swap)

Plus, at the client root:

    workspaces/<client>/import_history.json
        (append-only manifest, capped at HISTORY_MAX_ENTRIES, newest first)

The module is intentionally CLI-agnostic. Callers (map_raw_to_db.load, the
rollback command, future tests) use the helpers directly. No new dependencies.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = Path(BASE_DIR) / "workspaces"

HISTORY_FILENAME = "import_history.json"
HISTORY_MAX_ENTRIES = 50

VALIDATION_FILENAME = "validation.json"
BACKUP_FILENAME = "db-before.db"
LOG_FILENAME = "load.log"

RUN_SUBDIRS = ("raw", "logs", "reports")


def make_run_id(timestamp=None):
    """Return a sortable run id like 'run-20260615-130000'."""
    stamp = timestamp or datetime.now()
    return stamp.strftime("run-%Y%m%d-%H%M%S")


def client_workspace(client_id):
    """Path to a client workspace root: workspaces/<client_id>/."""
    if not client_id or not isinstance(client_id, str):
        raise ValueError("client_id must be a non-empty string")
    return WORKSPACE_ROOT / client_id


def run_workspace(client_id, run_id):
    """Path to a specific run directory: workspaces/<client>/runs/<run>/."""
    if not run_id or not isinstance(run_id, str):
        raise ValueError("run_id must be a non-empty string")
    return client_workspace(client_id) / "runs" / run_id


def ensure_run_dirs(run_path):
    """Create raw/, logs/, reports/ under run_path; return Path."""
    run_path = Path(run_path)
    run_path.mkdir(parents=True, exist_ok=True)
    for sub in RUN_SUBDIRS:
        (run_path / sub).mkdir(exist_ok=True)
    return run_path


def history_path(client_id):
    """Path to the per-client import_history.json file."""
    return client_workspace(client_id) / HISTORY_FILENAME


def load_history(client_id):
    """Return the import_history dict, creating an empty one if missing."""
    path = history_path(client_id)
    if not path.exists():
        return {"client_id": client_id, "runs": []}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "runs" not in data:
        return {"client_id": client_id, "runs": []}
    return data


def append_history(client_id, entry):
    """Prepend entry to the per-client history, trimming to the cap."""
    if not isinstance(entry, dict):
        raise TypeError("history entry must be a dict")
    if "run_id" not in entry:
        raise ValueError("history entry must include 'run_id'")
    data = load_history(client_id)
    data.setdefault("client_id", client_id)
    data["runs"].insert(0, entry)
    data["runs"] = data["runs"][:HISTORY_MAX_ENTRIES]
    path = history_path(client_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    return entry


def update_run(client_id, run_id, **fields):
    """Merge `fields` into the run entry whose 'run_id' matches `run_id`."""
    data = load_history(client_id)
    for run in data["runs"]:
        if run.get("run_id") == run_id:
            run.update(fields)
            break
    else:
        raise KeyError(f"no run with run_id={run_id!r} in {client_id!r} history")
    path = history_path(client_id)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def backup_database(db_path, run_dir):
    """Copy `db_path` to <run_dir>/db-before.db.

    Returns the absolute backup path. Returns "" if the source does not exist
    (e.g. first import of a new client).
    """
    db_path = Path(db_path)
    run_dir = Path(run_dir)
    if not db_path.exists():
        return ""
    target = run_dir / BACKUP_FILENAME
    shutil.copy2(db_path, target)
    return str(target)


def promote_database(staging_db, live_db):
    """Atomically replace live_db with staging_db.

    Raises FileNotFoundError if the staging file is missing. Uses os.replace
    so the swap is atomic on the same filesystem.
    """
    staging_db = Path(staging_db)
    live_db = Path(live_db)
    if not staging_db.exists():
        raise FileNotFoundError(f"staging database missing: {staging_db}")
    live_db.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_db, live_db)


def latest_good_run(client_id):
    """Return the most recent history entry with status='success', or None."""
    data = load_history(client_id)
    for run in data.get("runs", []):
        if run.get("status") == "success":
            return run
    return None


def write_validation(run_dir, payload):
    """Write validation.json next to a run's database."""
    path = Path(run_dir) / VALIDATION_FILENAME
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return str(path)


def copy_raw_inputs(raw_dir, source_glob, run_raw_dir):
    """Copy matching raw captures into the run's raw/ folder.

    Returns the list of copied filenames. Pure copy — the originals stay put
    so the capture stays the single source of truth.
    """
    import fnmatch
    import glob as _glob

    run_raw_dir = Path(run_raw_dir)
    run_raw_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(_glob.glob(os.path.join(str(raw_dir), "*.raw.json"))):
        if fnmatch.fnmatch(os.path.basename(src), source_glob):
            dest = run_raw_dir / os.path.basename(src)
            shutil.copy2(src, dest)
            copied.append(dest.name)
    return copied
