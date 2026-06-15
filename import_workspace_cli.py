"""
CLI for import_workspace: view per-client history and roll back to the
last good database.

Usage:
    python3 -m import_workspace history --client acme
    python3 -m import_workspace rollback --client acme --db pl_detail.db
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import import_workspace as iw


def cmd_history(args):
    data = iw.load_history(args.client)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    runs = data.get("runs", [])
    if not runs:
        print(f"no runs for client={args.client!r}")
        return 0
    print(f"client: {data.get('client_id', args.client)}")
    for run in runs:
        backup = run.get("backup_path", "")
        line = (
            f"  {run.get('timestamp', '?'):26s}  "
            f"{run.get('run_id', '?'):30s}  "
            f"{run.get('status', '?'):8s}  "
            f"rows={run.get('row_count', 0):,d}"
        )
        if backup:
            line += f"  backup={backup}"
        if run.get("error"):
            line += f"\n    error: {run['error']}"
        print(line)
    return 0


def cmd_rollback(args):
    data = iw.load_history(args.client)
    good = None
    for run in data.get("runs", []):
        if run.get("status") == "success" and run.get("backup_path"):
            good = run
            break
    if not good:
        print(f"ERROR: no successful run with a backup for client={args.client!r}",
              file=sys.stderr)
        return 1
    backup = Path(good["backup_path"])
    if not backup.exists():
        print(f"ERROR: backup missing on disk: {backup}", file=sys.stderr)
        return 1
    # The backup is a copy of the live DB BEFORE that successful run; it
    # is the safe state to roll back to.
    target = Path(args.db)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Copy the backup over the live DB — never move/replace the backup itself
    # so that repeated rollbacks are safe.
    import shutil
    shutil.copy2(str(backup), str(target))
    iw.update_run(args.client, good["run_id"],
                  rolled_back_at=iw.make_run_id(),
                  rolled_back_from_backup=good["backup_path"])
    print(f"rolled back {target} to {backup}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Phase 2 import workspace: history and rollback."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hist = sub.add_parser("history", help="Show per-client import history.")
    p_hist.add_argument("--client", required=True, help="Client id.")
    p_hist.add_argument("--json", action="store_true", help="Dump raw JSON.")
    p_hist.set_defaults(func=cmd_history)

    p_rb = sub.add_parser("rollback", help="Restore the last good database.")
    p_rb.add_argument("--client", required=True, help="Client id.")
    p_rb.add_argument("--db", default="pl_detail.db", help="Live database path.")
    p_rb.set_defaults(func=cmd_rollback)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
