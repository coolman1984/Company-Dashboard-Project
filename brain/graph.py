"""
graph.py - build the knowledge graph from parsed notes.

Resolves `[[wiki-links]]` to note ids and derives the things that keep a wiki
healthy: backlinks (who points here), broken links (point nowhere), orphans
(connected to nothing), and a tag index.
"""
from __future__ import annotations

import re

from .parse import parse_tree


def _norm(text):
    return re.sub(r"[\s_]+", "-", text.strip().lower()).strip("/")


# Typed links connect a note to a live dashboard object (Obsidian-style wiki-links
# that point outside the wiki). e.g. [[report:regional_pl]], [[region:Africa]],
# [[tab:guardian]], [[customer:Acme]]. These are NOT broken links.
OBJECT_TYPES = ("report", "tab", "region", "country", "product", "customer", "metric")
OBJECT_REF_RE = re.compile(r"^(%s):(.+)$" % "|".join(OBJECT_TYPES), re.IGNORECASE)


def parse_object_ref(target):
    """('report', 'regional_pl') for a typed link, else None."""
    m = OBJECT_REF_RE.match(target.strip())
    return (m.group(1).lower(), m.group(2).strip()) if m else None


class KnowledgeGraph:
    def __init__(self, notes):
        self.notes = notes                      # {note_id: Note}
        self._by_key = {}                       # normalized key -> note_id
        for note in notes.values():
            self._by_key[_norm(note.note_id)] = note.note_id
            self._by_key[_norm(note.note_id.split("/")[-1])] = note.note_id  # stem
            self._by_key.setdefault(_norm(note.title), note.note_id)

        # Resolve links.
        self.edges = {}            # note_id -> [resolved target ids]
        self.broken = {}           # note_id -> [unresolved raw targets]
        self.object_edges = {}     # note_id -> ["report:regional_pl", ...] typed refs
        for note_id, note in notes.items():
            resolved, broken, objects = [], [], []
            for target in note.links:
                ref = parse_object_ref(target)
                if ref:
                    canon = f"{ref[0]}:{ref[1]}"
                    if canon not in objects:
                        objects.append(canon)
                    continue
                hit = self._by_key.get(_norm(target))
                if hit:
                    if hit not in resolved:
                        resolved.append(hit)
                else:
                    broken.append(target)
            self.edges[note_id] = resolved
            self.object_edges[note_id] = objects
            if broken:
                self.broken[note_id] = broken

    def notes_for_object(self, ref):
        """note_ids that reference a dashboard object (e.g. 'report:regional_pl').
        Matching is case-insensitive on the id part."""
        want = parse_object_ref(ref)
        if not want:
            return []
        target = f"{want[0]}:{want[1]}".lower()
        return sorted(nid for nid, refs in self.object_edges.items()
                      if any(r.lower() == target for r in refs))

    def backlinks(self):
        back = {note_id: [] for note_id in self.notes}
        for source, targets in self.edges.items():
            for target in targets:
                back[target].append(source)
        return back

    def orphans(self):
        back = self.backlinks()
        return sorted(note_id for note_id in self.notes
                      if not self.edges[note_id] and not back[note_id])

    def tags(self):
        index = {}
        for note_id, note in self.notes.items():
            for tag in note.tags:
                index.setdefault(tag, []).append(note_id)
        return {tag: sorted(ids) for tag, ids in sorted(index.items())}

    def broken_links(self):
        return {nid: list(targets) for nid, targets in sorted(self.broken.items())}

    def to_dict(self):
        back = self.backlinks()
        return {
            "notes": [
                {
                    "id": nid,
                    "title": note.title,
                    "tags": note.tags,
                    "links": self.edges[nid],
                    "backlinks": sorted(back[nid]),
                    "object_refs": self.object_edges[nid],
                }
                for nid, note in sorted(self.notes.items())
            ],
            "tags": self.tags(),
            "orphans": self.orphans(),
            "broken_links": self.broken_links(),
            "counts": {
                "notes": len(self.notes),
                "links": sum(len(v) for v in self.edges.values()),
                "tags": len(self.tags()),
                "orphans": len(self.orphans()),
                "broken_links": sum(len(v) for v in self.broken.values()),
            },
        }


def build_graph(root):
    return KnowledgeGraph(parse_tree(root))
