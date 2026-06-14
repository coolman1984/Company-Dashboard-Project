"""
cli.py - generate saved report files from the dashboard database.

Usage:
    python3 -m reports.cli --list                 # show available reports
    python3 -m reports.cli                         # generate all as JSON
    python3 -m reports.cli --report yearly_pl      # one report
    python3 -m reports.cli --format json csv       # JSON and CSV
    python3 -m reports.cli --db pl_detail.db --out output/reports
"""
from __future__ import annotations

import argparse
import os
import sys

from .definitions import REPORTS, REPORTS_BY_NAME
from .generate import generate, generate_board_pack

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")
DEFAULT_OUT = os.path.join(BASE_DIR, "output", "reports")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate saved reports from pl_detail.db.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Source database.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output folder.")
    parser.add_argument("--report", action="append", dest="reports",
                        help="Report name (repeatable). Default: all.")
    parser.add_argument("--format", nargs="+", default=["json"],
                        choices=["json", "csv", "xlsx", "pdf"],
                        help="Output format(s): json, csv, xlsx, pdf.")
    parser.add_argument("--list", action="store_true", help="List reports and exit.")
    parser.add_argument("--pack", action="store_true",
                        help="Bundle all reports into a single board-pack file per format.")
    parser.add_argument("--title", default="Board Pack",
                        help="Title for the board pack cover.")
    args = parser.parse_args(argv)

    if args.list:
        print("Available reports:")
        for report in REPORTS:
            print(f"  {report.name:<18} {report.title} - {report.description}")
        return 0

    unknown = [n for n in (args.reports or []) if n not in REPORTS_BY_NAME]
    if unknown:
        print(f"ERROR: unknown report(s): {', '.join(unknown)}. "
              f"Use --list to see options.", file=sys.stderr)
        return 1

    print(f"Generating reports from {os.path.basename(args.db)} -> {args.out}")
    try:
        if args.pack:
            # Default a pack to both office formats unless the user narrowed it.
            formats = tuple(args.format) if args.format != ["json"] else ("xlsx", "pdf")
            generate_board_pack(args.db, args.out, names=args.reports,
                                formats=formats, title=args.title)
        else:
            generate(args.db, args.out, names=args.reports, formats=tuple(args.format))
    except (FileNotFoundError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
