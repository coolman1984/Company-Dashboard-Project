# Phase 2 — Import-Run Workspace & Rollback

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the first real client import **repeatable** by adding a per-run
workspace (intake → raw → db → reports → logs), an `import_history.json`
manifest, automatic database backups before each import, and a one-command
rollback to the last known-good database.

**Architecture:** Extend `map_raw_to_db.py` and add a new thin module
`import_workspace.py`. The workspace module owns directory layout, backups,
history persistence, and rollback. The mapper writes a `validation.json` next
to the database. No changes to the raw-JSON envelope, `schema.sql`, or the
server API — all Phase-2 changes are additive.

**Tech Stack:** Python 3 stdlib + existing project deps. No new dependencies.

**Branch:** `mohamed/phase-2-import-workspace` (already created).

**Reference files (read first):**
- `/root/Company-Dashboard/map_raw_to_db.py` (the loader we extend)
- `/root/Company-Dashboard/mapping.example.json` (the mapping format)
- `/root/Company-Dashboard/AGENTS.md` (agent protocol)
- `/root/Company-Dashboard/CLIENT_READINESS_REVIEW.md` Phase 2 section
- `/root/Company-Dashboard/.gitignore` (must keep `intake/`, `raw/`,
  `workspaces/`, generated reports ignored)

---

## Locked scope decisions

- **Workspace layout** lives under `workspaces/<client>/runs/<run-id>/`.
- Each run has: `raw/` (copy of input), `logs/load.log`, `validation.json`,
  `db-before.db` (previous good DB) and `db-after.db` (new DB).
- `import_history.json` is per-client, append-only, capped at 50 runs.
- Rollback swaps `db-after.db` → `pl_detail.db` and updates history status.
- Server/API is untouched. The workspace is CLI-only in this phase.
- The validation report builder in `reports/validation.py` is reused, not
  duplicated.
- No new pip dependency.

## Out of scope (deferred)

- Source drill-back from dashboard numbers to source rows (Phase 2 #4).
- Mapping review UI (Phase 2 #2).
- Visible validation page in the dashboard UI.

---

## Task 1: Read existing patterns

**Files:** Read-only.
- `/root/Company-Dashboard/.gitignore`
- `/root/Company-Dashboard/mapping.example.json`
- `/root/Company-Dashboard/map_raw_to_db.py` (lines 385–460)
- `/root/Company-Dashboard/reports/validation.py` (entire file)

**Verification:** Write a 5-line summary of:
1. The current CLI flags `--raw`, `--db`, `--mapping`, `--force`, `--dry-run`.
2. Where `_validate_loaded_data` writes its output (stdout only).
3. The validation keys we want to mirror in `validation.json`.

Commit: not required (read-only).

---

## Task 2: Add `workspaces/` and `intake_<client>/` patterns to `.gitignore`

**File:** `/root/Company-Dashboard/.gitignore`

**Step 1:** Append these lines:

```gitignore
# Phase 2 import-run workspaces (never commit client data)
workspaces/
*.db
*.db.bak
import_history*.json
```

**Step 2:** Run `git status --short` to confirm `workspaces/` and `*.db` are
now hidden. Expected: nothing new tracked.

**Step 3:** Commit:

```bash
git add .gitignore
git commit -m "chore: gitignore phase 2 import workspaces and client databases"
```

---

## Task 3: Create `import_workspace.py` skeleton

**File:** `/root/Company-Dashboard/import_workspace.py`

**Step 1:** Create the file with module docstring, imports, and a
`WORKSPACE_ROOT = os.path.join(BASE_DIR, "workspaces")` constant.

**Step 2:** Add `make_run_id(timestamp=None)` returning
`f"run-{YYYYMMDD-HHMMSS}"` and `client_workspace(client_id) -> Path` returning
`workspaces/<client_id>/`.

**Step 3:** Add `run_workspace(client_id, run_id) -> Path` returning
`workspaces/<client_id>/runs/<run_id>/`.

**Step 4:** Add `ensure_run_dirs(...)` that creates the subfolders
`raw/`, `logs/`, `reports/` and returns the path.

**Step 5:** Run `python3 -c "from import_workspace import run_workspace; import
shutil; p = run_workspace('test', 'run-20260615-130000'); p.mkdir(parents=True,
exist_ok=True); print(p); shutil.rmtree(p.parent.parent)"`. Expected: prints
the run path and exits 0.

**Step 6:** Commit:

```bash
git add import_workspace.py
git commit -m "feat(phase-2): add import_workspace scaffolding"
```

---

## Task 4: Add history persistence

**File:** `/root/Company-Dashboard/import_workspace.py`

**Step 1:** Add `HISTORY_FILENAME = "import_history.json"` and
`HISTORY_MAX_ENTRIES = 50` constants.

**Step 2:** Add `append_history(client_id, entry)` that:
- Reads the existing history (or `{"client_id": client_id, "runs": []}` if
  none).
- Prepends the new entry to `runs`.
- Trims to `HISTORY_MAX_ENTRIES`.
- Writes back with `indent=2`.

**Step 3:** Add `load_history(client_id)` returning the dict or
`{"client_id": client_id, "runs": []}`.

**Step 4:** Run a quick test:

```bash
python3 -c "
import import_workspace as iw
from pathlib import Path
import shutil, json
base = Path('workspaces')
if base.exists(): shutil.rmtree(base)
iw.append_history('test', {'run_id': 'r1', 'status': 'pending'})
iw.append_history('test', {'run_id': 'r2', 'status': 'pending'})
print(iw.load_history('test'))
shutil.rmtree(base)
"
```

Expected: JSON dict with two runs, `r2` first.

**Step 5:** Commit:

```bash
git add import_workspace.py
git commit -m "feat(phase-2): history persistence with cap"
```

---

## Task 5: Add backup and restore helpers

**File:** `/root/Company-Dashboard/import_workspace.py`

**Step 1:** Add `backup_database(db_path, run_dir) -> str` that:
- Returns empty string if `db_path` doesn't exist.
- Copies the database to `run_dir / "db-before.db"`.
- Returns the absolute backup path.

**Step 2:** Add `promote_database(staging_db, live_db) -> None` that uses
`os.replace` for an atomic swap. Reject if `staging_db` doesn't exist.

**Step 3:** Run a quick test:

```bash
python3 -c "
import import_workspace as iw
import sqlite3, os, shutil
from pathlib import Path
base = Path('workspaces')
if base.exists(): shutil.rmtree(base)
run = iw.run_workspace('test', 'run-1'); run.mkdir(parents=True)
db = Path('pl_detail.db')
con = sqlite3.connect(db); con.execute('CREATE TABLE IF NOT EXISTS t (a)'); con.commit(); con.close()
backup = iw.backup_database(db, run)
print('backup:', backup)
print('exists:', os.path.exists(backup))
shutil.rmtree(base)
"
```

Expected: backup path printed and `exists: True`.

**Step 4:** Commit:

```bash
git add import_workspace.py
git commit -m "feat(phase-2): database backup and promote helpers"
```

---

## Task 6: Wire `import_workspace` into `map_raw_to_db.load`

**File:** `/root/Company-Dashboard/map_raw_to_db.py`

**Step 1:** Import `import_workspace as iw` at the top.

**Step 2:** Extend the CLI to accept `--client` (default: `default`) and
`--workspace` (default: `workspaces/`).

**Step 3:** In `load()`, before creating the temp file, if `client` and not
`dry_run`:
- Create the run workspace.
- Copy each matched raw file to `raw/`.
- Back up the existing database to `db-before.db`.
- Open a log file at `logs/load.log` and `print` with `file=...` for both
  stdout and the log.

**Step 4:** After successful swap, append a history entry with
`status=success`, `validation=stats["validation"]`, `row_count`, and the run
path.

**Step 5:** If `_validate_loaded_data` raises, append a history entry with
`status=failed` and the error message; do not swap.

**Step 6:** Run the existing tests:

```bash
cd /root/Company-Dashboard
python3 test_map_raw_to_db.py
```

Expected: passes (existing test must still work; the new flags default to
backwards-compatible behaviour).

**Step 7:** Commit:

```bash
git add map_raw_to_db.py import_workspace.py
git commit -m "feat(phase-2): write history + backup in map_raw_to_db"
```

---

## Task 7: Persist `validation.json` next to the database

**File:** `/root/Company-Dashboard/map_raw_to_db.py`

**Step 1:** In `load()`, after `_validate_loaded_data` succeeds, write
`stats["validation"]` to `<run_dir>/validation.json` with `indent=2`.

**Step 2:** In the failure branch, write a partial `validation.json` with
`status=failed` and the error message.

**Step 3:** Run a fresh load with the example mapping to verify the file is
written.

**Step 4:** Commit:

```bash
git add map_raw_to_db.py
git commit -m "feat(phase-2): persist validation.json per run"
```

---

## Task 8: Add `rollback` subcommand

**File:** `/root/Company-Dashboard/import_workspace.py`

**Step 1:** Add `latest_good_run(client_id) -> dict | None` that scans history
in reverse and returns the most recent `status=success` entry, or `None`.

**Step 2:** Add `rollback(client_id, live_db) -> str` that:
- Loads the latest good run.
- Returns its `db-before.db` path if present.
- Raises `FileNotFoundError` if no good run is found.
- (The actual `os.replace` happens in the CLI handler, not here, so the
  workspace module stays UI-agnostic.)

**Step 3:** Add a `main()` CLI with `subcommands`: `history`, `rollback`. Wire
them in `if __name__ == "__main__"`.

**Step 4:** Add a tiny `__main__` block.

**Step 5:** Test:

```bash
python3 -m import_workspace history --client test 2>&1 | tail -5
```

Expected: prints empty history (since `test` is not a real client) without
crashing.

**Step 6:** Commit:

```bash
git add import_workspace.py
git commit -m "feat(phase-2): history and rollback CLI"
```

---

## Task 9: Add a unit test for the workspace module

**File:** `/root/Company-Dashboard/test_import_workspace.py`

**Step 1:** Create the file with three tests:
- `test_run_workspace_creates_dirs`
- `test_history_cap`
- `test_backup_and_promote`

**Step 2:** Run:

```bash
cd /root/Company-Dashboard
python3 test_import_workspace.py
```

Expected: 3 passed.

**Step 3:** Add the test to the README's "Run & test it" section (or
`AGENTS.md` journal).

**Step 4:** Commit:

```bash
git add test_import_workspace.py
git commit -m "test(phase-2): workspace, history, backup tests"
```

---

## Task 10: Update `AGENTS.md` journal and README

**File:** `/root/Company-Dashboard/AGENTS.md` (Work Journal at the top) and
`/root/Company-Dashboard/README.md`.

**Step 1:** Add a journal entry at the top of the journal:

```markdown
### 2026-06-15 — mohamed (minimax-m3) — `mohamed/phase-2-import-workspace`
**Did:** Phase 2 import-run workspace scaffolding: per-client runs, raw copies,
db backups, import_history with cap, validation.json, rollback subcommand.
**Why:** Make the first real client import repeatable and recoverable.
**Status:** tests passing (existing map_raw_to_db tests + new workspace tests).
**Next:** Source drill-back from dashboard numbers to source rows.
**Watch out:** server.js and the raw-JSON envelope are untouched; this phase
is CLI-only.
```

**Step 2:** Add a "Workspaces" section to `README.md` describing the layout.

**Step 3:** Commit:

```bash
git add AGENTS.md README.md
git commit -m "docs(phase-2): journal entry and workspace docs"
```

---

## Task 11: Final verification and PR

**Step 1:** Run the full verification gate from `AGENTS.md`:

```bash
npm test
python3 test_map_raw_to_db.py
python3 -m reports.test_reports
python3 -m reports.test_render
python3 -m extractor.test_arabic
python3 -m extractor.test_extractor
python3 test_import_workspace.py
git diff --check
git status --short --branch
```

**Step 2:** Push:

```bash
git push origin mohamed/phase-2-import-workspace
```

**Step 3:** Report to Mohamed:
- Branch name and PR URL.
- Test results.
- List of new files.
- The exact rollback command.
