# Knowledge Base — the "second brain" (Stage 4)

An **Obsidian-style company wiki** of linked Markdown notes — definitions,
conventions, processes, and decisions — *connected to the data*. The
[ROADMAP.md](../ROADMAP.md) calls this the "second brain".

The notes live in [`../knowledge/`](../knowledge). They are plain Markdown with
`[[wiki-links]]`, `#tags`, and YAML frontmatter, so you can **open the
`knowledge/` folder directly in [Obsidian](https://obsidian.md)** and get the
graph view, backlinks, and search for free. This `brain/` engine adds
validation, an index, and data-driven notes that work without any app.

## Commands

```bash
python3 -m brain.cli --check        # validate links; list orphans + broken links
python3 -m brain.cli --index        # (re)write knowledge/index.md (the map)
python3 -m brain.cli --graph        # write output/knowledge-graph.json
python3 -m brain.cli --data-notes   # generate a note per region FROM the database
python3 -m brain.cli --search margin # full-text search notes; returns ranked JSON
python3 -m brain.test_brain         # run the tests
```

`--check` exits non-zero if any `[[link]]` points nowhere, so CI keeps the wiki
free of dangling links.

## What it does

- **Parse** each note: title, frontmatter, `#tags`, and `[[links]]`
  (`parse.py`).
- **Graph** the notes (`graph.py`): resolve links, compute **backlinks**, find
  **orphans** (linked to nothing) and **broken links** (point nowhere), and a
  **tag index**.
- **Connect to data** (`data_notes.py`): generate a note per region straight
  from `pl_detail.db`, carrying the latest figures in frontmatter and linking
  into the curated wiki (`[[glossary]]`, `[[reports]]`, `[[index]]`). This is
  what makes curated knowledge and live numbers share one linked space.
- **Search** (`search.py`): dependency-free full-text scan across titles, tags,
  and bodies with weighted scoring and snippets. This gives agents and operators
  a practical search surface before a heavier indexed service is justified.

## Layout

```
knowledge/                 curated, committed notes
  index.md                 auto-generated map (brain.cli --index)
  glossary.md              definitions
  conventions.md           period/version encoding
  reports.md               what the reports are
  processes/data-pipeline.md
  decisions/0001-synthetic-seed.md   an ADR (architecture decision record)
  data/                    notes generated FROM the database (git-ignored)
```

Curated notes are committed; `knowledge/data/` is generated and git-ignored
because it can contain real client figures.
