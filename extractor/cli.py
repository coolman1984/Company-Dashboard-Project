"""
cli.py - the extraction orchestrator.

Walk an intake folder of messy client files, route each file to the best
available extractor, write a faithful raw-JSON capture of every original, and
record the result in the manifest. Files that are unsupported or whose extractor
is unavailable are skipped with a clear reason - the run never crashes on one
bad or unreadable file.

Usage:
    python -m extractor.cli                     # intake/ -> raw/
    python -m extractor.cli --intake some/dir --out other/dir
    python -m extractor.cli --list              # show extractor availability
    python -m extractor.cli --force             # re-capture even if unchanged
"""
from __future__ import annotations

import argparse
import json
import os
import traceback

from . import manifest, raw, registry

DEFAULT_INTAKE = "intake"
DEFAULT_OUT = "raw"


def iter_files(intake_dir: str):
    for root, _dirs, files in os.walk(intake_dir):
        for name in sorted(files):
            if name.startswith(".") or name.startswith("~$"):
                continue  # skip hidden files and Office lock files
            yield os.path.join(root, name)


def write_raw(envelope: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, raw.raw_output_name(envelope))
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(envelope, handle, ensure_ascii=False, indent=2, default=str)
    return out_path


def run(intake_dir: str, out_dir: str, force: bool) -> dict:
    seen = set() if force else manifest.load_seen_hashes(out_dir)
    summary = {"captured": 0, "skipped_unchanged": 0, "skipped_unavailable": 0,
               "unsupported": 0, "errors": 0}

    if not os.path.isdir(intake_dir):
        print(f"Intake folder not found: {intake_dir}")
        return summary

    for path in iter_files(intake_dir):
        rel = os.path.relpath(path, intake_dir)
        extractor, reason = registry.select_extractor(path)

        if extractor is None:
            kind = "unsupported" if reason == "unsupported" else "skipped_unavailable"
            summary[kind] += 1
            manifest.append(out_dir, {"filename": rel, "status": kind, "reason": reason})
            print(f"  SKIP  {rel}  ({reason})")
            continue

        try:
            file_hash = raw.sha256_of(path)
            if file_hash in seen:
                summary["skipped_unchanged"] += 1
                print(f"  SAME  {rel}  (already captured)")
                continue

            envelope = extractor.extract(path, intake_dir)
            out_path = write_raw(envelope, out_dir)
            seen.add(envelope["source"]["sha256"])
            summary["captured"] += 1
            n_warn = len(envelope["warnings"])
            warn_note = f"  [{n_warn} warning(s)]" if n_warn else ""
            print(f"  OK    {rel}  -> {os.path.basename(out_path)}  "
                  f"via {extractor.name}{warn_note}")
            manifest.append(out_dir, {
                "filename": rel,
                "sha256": envelope["source"]["sha256"],
                "extractor": extractor.name,
                "document_type": envelope["document_type"],
                "raw_output": os.path.basename(out_path),
                "warnings": envelope["warnings"],
                "status": "ok",
            })
        except Exception as error:  # noqa: BLE001 - one bad file must not stop the run
            summary["errors"] += 1
            print(f"  ERROR {rel}  ({error})")
            manifest.append(out_dir, {
                "filename": rel, "extractor": extractor.name,
                "status": "error", "reason": str(error),
                "traceback": traceback.format_exc(),
            })

    return summary


def print_availability():
    print("Extractor availability:")
    for row in registry.describe_availability():
        mark = "available" if row["available"] else "unavailable"
        exts = ", ".join(row["extensions"])
        print(f"  [{mark:>11}] {row['name']:<16} {exts:<28} {row['reason']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract messy client files into raw JSON.")
    parser.add_argument("--intake", default=DEFAULT_INTAKE, help="Folder of source files.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Folder for raw JSON + manifest.")
    parser.add_argument("--force", action="store_true", help="Re-capture unchanged files.")
    parser.add_argument("--list", action="store_true", help="Show extractor availability and exit.")
    args = parser.parse_args(argv)

    if args.list:
        print_availability()
        return 0

    print(f"Scanning '{args.intake}' -> '{args.out}'")
    summary = run(args.intake, args.out, args.force)
    print("\nSummary:")
    for key, value in summary.items():
        print(f"  {key.replace('_', ' ')}: {value}")
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
