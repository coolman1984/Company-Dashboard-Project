"""
search.py - lightweight full-text search for the Markdown knowledge base.

No external index dependency: the knowledge base is small enough for an in-memory
scan, but this still behaves like full-text search rather than a single substring
match. Queries are tokenized, matched against title/tags/body, scored, and return
snippets suitable for CLI or MCP callers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parse import parse_tree

TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


@dataclass(frozen=True)
class SearchHit:
    note_id: str
    title: str
    score: int
    snippet: str
    tags: list[str]

    def to_dict(self):
        return {
            "note": self.note_id,
            "title": self.title,
            "score": self.score,
            "snippet": self.snippet,
            "tags": self.tags,
        }


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if len(t) >= 2]


def _snippet(body: str, query_tokens: list[str], width: int = 160) -> str:
    lower = body.lower()
    positions = [lower.find(token) for token in query_tokens if lower.find(token) >= 0]
    if not positions:
        return " ".join(body.strip().split())[:width]
    center = min(positions)
    start = max(0, center - width // 3)
    end = min(len(body), start + width)
    return " ".join(body[start:end].strip().split())


def search(root: str, query: str, limit: int = 10) -> list[dict]:
    """Search all notes under root and return ranked dictionaries.

    A result must match at least one query token. Title and tag matches are
    weighted above body matches because they usually indicate stronger relevance.
    """
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    hits: list[SearchHit] = []
    for note in parse_tree(root).values():
        title_tokens = set(_tokens(note.title))
        tag_tokens = set(t.lower() for t in note.tags)
        body_text = note.body or ""
        body_lower = body_text.lower()

        score = 0
        for token in query_tokens:
            if token in title_tokens:
                score += 8
            if token in tag_tokens:
                score += 5
            body_count = body_lower.count(token)
            if body_count:
                score += min(body_count, 5)
        if score:
            hits.append(SearchHit(
                note_id=note.note_id,
                title=note.title,
                score=score,
                snippet=_snippet(body_text, query_tokens),
                tags=list(note.tags),
            ))

    hits.sort(key=lambda h: (-h.score, h.note_id))
    return [hit.to_dict() for hit in hits[:max(1, limit)]]
