"""
Tests for the knowledge base engine (no pytest required).

Run:  python3 -m brain.test_brain
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

from . import data_notes
from .graph import build_graph
from .parse import parse_note
from .search import search

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_parse():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(tmp, "note.md",
                      "---\ntitle: My Note\ntags: [alpha, beta]\n---\n\n"
                      "# My Note\n\nLinks to [[other]] and [[folder/thing|alias]]. #gamma\n")
        note = parse_note(path, tmp)
        assert note.title == "My Note", note.title
        assert "alpha" in note.tags and "gamma" in note.tags, note.tags
        assert note.links == ["other", "folder/thing"], note.links


def test_graph():
    with tempfile.TemporaryDirectory() as tmp:
        _write(tmp, "a.md", "# A\n\nlink to [[b]] and a [[ghost]]. #x\n")
        _write(tmp, "sub/b.md", "# B\n\nnothing links out from here in-graph.\n")
        _write(tmp, "lonely.md", "# Lonely\n\nno links at all.\n")
        graph = build_graph(tmp)
        data = graph.to_dict()

        assert graph.edges["a"] == ["sub/b"], graph.edges
        assert graph.backlinks()["sub/b"] == ["a"]
        assert data["broken_links"]["a"] == ["ghost"], data["broken_links"]
        assert "lonely" in graph.orphans()
        assert "sub/b" not in graph.orphans()   # has a backlink
        assert data["counts"]["notes"] == 3


def test_data_notes_link_into_wiki():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "pl_detail.db")
        conn = sqlite3.connect(db)
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            conn.executescript(fh.read())
        conn.execute(
            "INSERT INTO pl_detail (year, version, period, region_desc, net_sales, "
            "gross_margin) VALUES (2025, 'Actual', 2025.001, 'Africa', 1000, 400)")
        conn.commit(); conn.close()

        out = os.path.join(tmp, "data")
        written = data_notes.generate_region_notes(db_path=db, out_dir=out, verbose=False)
        assert len(written) == 1
        text = open(written[0], encoding="utf-8").read()
        assert "net_sales: 1000" in text
        assert "[[glossary]]" in text and "[[index]]" in text

        # With the notes a region note links to present, nothing is broken.
        _write(out, "glossary.md", "# Glossary\n")
        _write(out, "index.md", "# Index\n")
        _write(out, "reports.md", "# Reports\n")
        graph = build_graph(out)
        assert not graph.broken_links(), graph.broken_links()


def test_search_ranks_title_and_returns_snippet():
    with tempfile.TemporaryDirectory() as tmp:
        _write(tmp, "reports.md", "---\ntags: [finance]\n---\n# Reports\n\nGross margin report definitions.\n")
        _write(tmp, "process.md", "# Process\n\nThis mentions margin once.\n")
        hits = search(tmp, "reports margin", limit=5)
        assert hits[0]["note"] == "reports", hits
        assert hits[0]["score"] > hits[1]["score"], hits
        assert "margin" in hits[0]["snippet"].lower(), hits[0]


def main():
    test_parse()
    test_graph()
    test_data_notes_link_into_wiki()
    test_search_ranks_title_and_returns_snippet()
    print("brain tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
