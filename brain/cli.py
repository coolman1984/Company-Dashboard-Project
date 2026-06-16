"""
cli.py - work with the knowledge base ("second brain").

    python3 -m brain.cli --check          # validate links; list orphans/broken
    python3 -m brain.cli --index          # (re)write knowledge/index.md
    python3 -m brain.cli --graph          # write output/knowledge-graph.json
    python3 -m brain.cli --data-notes     # generate region notes from the DB

--check exits non-zero if any [[link]] is broken, so it can guard CI.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .data_notes import generate_region_notes
from .graph import build_graph
from .search import search as search_notes

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOT = os.path.join(BASE_DIR, "knowledge")
DEFAULT_GRAPH = os.path.join(BASE_DIR, "output", "knowledge-graph.json")


def cmd_check(graph):
    data = graph.to_dict()
    counts = data["counts"]
    print(f"Notes: {counts['notes']} | links: {counts['links']} | "
          f"tags: {counts['tags']} | orphans: {counts['orphans']} | "
          f"broken links: {counts['broken_links']}")
    for note_id, targets in data["broken_links"].items():
        for target in targets:
            print(f"  BROKEN  {note_id} -> [[{target}]]")
    for orphan in data["orphans"]:
        print(f"  ORPHAN  {orphan} (no links in or out)")
    return 1 if counts["broken_links"] else 0


def cmd_index(graph, root):
    data = graph.to_dict()
    back = graph.backlinks()
    lines = ["---", "title: Index", "tags: [index]", "---", "",
             "# Knowledge Base Index", "",
             "_Auto-generated map of the company knowledge base._", ""]

    lines.append("## Notes")
    for note in data["notes"]:
        if note["id"] == "index":
            continue
        n_back = len(back.get(note["id"], []))
        lines.append(f"- [[{note['id'].split('/')[-1]}]] — {note['title']} "
                     f"({n_back} backlink{'s' if n_back != 1 else ''})")
    lines.append("")

    lines.append("## Tags")
    for tag, ids in data["tags"].items():
        lines.append(f"- #{tag} ({len(ids)})")
    lines.append("")

    if data["orphans"]:
        lines.append("## Orphans (not linked yet)")
        lines += [f"- {o}" for o in data["orphans"]] + [""]

    out_path = os.path.join(root, "index.md")
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(f"Wrote {out_path}")
    return 0


def cmd_graph(graph, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(graph.to_dict(), handle, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}")
    return 0


def cmd_search(root, query, limit):
    hits = search_notes(root, query, limit=limit)
    print(json.dumps({"query": query, "match_count": len(hits), "matches": hits},
                     ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Knowledge base tools.")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Knowledge folder.")
    parser.add_argument("--check", action="store_true", help="Validate links.")
    parser.add_argument("--index", action="store_true", help="Rewrite index.md.")
    parser.add_argument("--graph", action="store_true", help="Write graph JSON.")
    parser.add_argument("--data-notes", action="store_true",
                        help="Generate region notes from the database.")
    parser.add_argument("--search", default=None,
                        help="Full-text search query for the knowledge base.")
    parser.add_argument("--limit", type=int, default=10,
                        help="Maximum search results for --search.")
    parser.add_argument("--db", default=None, help="Database for --data-notes.")
    args = parser.parse_args(argv)

    if args.data_notes:
        try:
            generate_region_notes(db_path=args.db) if args.db else generate_region_notes()
        except FileNotFoundError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

    if not os.path.isdir(args.root):
        print(f"ERROR: knowledge folder not found: {args.root}", file=sys.stderr)
        return 1
    graph = build_graph(args.root)

    if args.index:
        cmd_index(graph, args.root)
    if args.graph:
        cmd_graph(graph, DEFAULT_GRAPH)
    if args.search:
        return cmd_search(args.root, args.search, args.limit)
    if args.check or not (args.index or args.graph or args.data_notes or args.search):
        return cmd_check(graph)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
