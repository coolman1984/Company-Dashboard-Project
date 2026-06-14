"""
parse.py - read one Markdown note into structured form.

Notes are plain Markdown (Obsidian-compatible): optional YAML-ish frontmatter,
`[[wiki-links]]` between notes, `#tags`, and a first `# Heading` as the title.
Dependency-light: a tiny frontmatter reader handles `key: value` and simple
`key: [a, b]` lists, so no external YAML library is needed.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9][A-Za-z0-9_/-]*)")
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


@dataclass
class Note:
    note_id: str                       # relpath without extension, posix
    path: str
    title: str
    frontmatter: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    links: list = field(default_factory=list)   # raw link targets (pre-resolution)
    body: str = ""


def _parse_frontmatter(text):
    """Return (frontmatter_dict, remaining_body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    rest = text[end + 4:].lstrip("\n")
    fm = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            fm[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            fm[key] = value
    return fm, rest


def _link_target(raw):
    # [[Note|alias]] or [[Note#heading]] -> the note part.
    return raw.split("|", 1)[0].split("#", 1)[0].strip()


def parse_note(path, root):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    frontmatter, body = _parse_frontmatter(text)

    note_id = os.path.relpath(path, root).replace(os.sep, "/")
    note_id = note_id[:-3] if note_id.lower().endswith(".md") else note_id

    heading = HEADING_RE.search(body)
    title = (frontmatter.get("title") or (heading.group(1) if heading else None)
             or os.path.splitext(os.path.basename(path))[0])

    tags = list(frontmatter.get("tags", []) if isinstance(frontmatter.get("tags"), list) else [])
    for tag in TAG_RE.findall(body):
        if tag not in tags:
            tags.append(tag)

    links = []
    for raw in LINK_RE.findall(body):
        target = _link_target(raw)
        if target and target not in links:
            links.append(target)

    return Note(note_id=note_id, path=path, title=title, frontmatter=frontmatter,
                tags=tags, links=links, body=body)


def parse_tree(root):
    """Parse every .md note under root. Returns {note_id: Note}."""
    notes = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if name.lower().endswith(".md"):
                note = parse_note(os.path.join(dirpath, name), root)
                notes[note.note_id] = note
    return notes
