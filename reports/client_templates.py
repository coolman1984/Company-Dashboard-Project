"""
client_templates.py — per-client report template loading.

Each client under workspaces/<client>/ can have a `templates.json` that
defines client-specific reports and label overrides. When no template is
present, the built-in default catalogue (`definitions.py`) is used unchanged.

Template format (workspaces/<client>/templates.json):

    {
        "client_name": "Acme Corp",
        "labels": {
            "net_sales": "Total Revenue",
            "cogs": "Cost of Delivery"
        },
        "reports": [
            {
                "name": "acme_quarterly_summary",
                "title": "Acme Quarterly Summary",
                "description": "Quarterly breakdown for Acme Corp",
                "sql": "SELECT ... FROM pl_detail WHERE customer_name = 'Acme'"
            }
        ]
    }

- `labels`: optional mapping of built-in metric/column names to
  client-friendly display labels. These override the defaults in the UI
  and in report headers.
- `reports`: optional list of client-specific reports. Each entry has the
  same shape as `Report` in definitions.py except `sql` is always a string
  (no builder support for client templates — builders stay in code).
  Client reports are appended to the built-in catalogue; duplicates by
  `name` are rejected (built-in wins).

When a client has a templates.json, it is loaded and cached on first request.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = Path(BASE_DIR) / "workspaces"


@dataclass(frozen=True)
class ClientTemplate:
    client_name: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    client_report_defs: List[dict] = field(default_factory=list)
    source_path: str = ""


# In-memory cache: client_slug -> ClientTemplate
_cache: Dict[str, ClientTemplate] = {}


def _load_raw(client_slug: str) -> Optional[dict]:
    """Load raw JSON from a client's templates.json, or None."""
    tpl_path = WORKSPACE_ROOT / client_slug / "templates.json"
    if not tpl_path.exists():
        return None
    try:
        with open(tpl_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_template(client_slug: str, force: bool = False) -> Optional[ClientTemplate]:
    """Return the client template (cached), or None if no template file exists."""
    if not force and client_slug in _cache:
        return _cache[client_slug]

    raw = _load_raw(client_slug)
    if raw is None:
        _cache.pop(client_slug, None)
        return None

    reports = raw.get("reports", [])
    # Validate client reports: must have name, title, and sql
    valid_reports: List[dict] = []
    for r in reports:
        if not isinstance(r, dict):
            continue
        name = r.get("name", "").strip()
        title = r.get("title", "").strip()
        sql = r.get("sql", "").strip()
        if not name or not title or not sql:
            continue
        # Ensure name doesn't collide with built-in reports
        from .definitions import REPORTS_BY_NAME
        if name not in REPORTS_BY_NAME:
            valid_reports.append({
                "name": name,
                "title": title,
                "description": r.get("description", ""),
                "sql": sql,
            })

    template = ClientTemplate(
        client_name=raw.get("client_name", client_slug),
        labels=raw.get("labels") or {},
        client_report_defs=valid_reports,
        source_path=str(WORKSPACE_ROOT / client_slug / "templates.json"),
    )
    _cache[client_slug] = template
    return template


def list_client_report_names(client_slug: str, conn) -> List[dict]:
    """
    Return [{name, title, description, is_builtin}, ...] for the given client.
    Built-in reports always included; client-specific reports appended.
    """
    from .definitions import REPORTS

    result: List[dict] = []
    for r in REPORTS:
        result.append({
            "name": r.name,
            "title": r.title,
            "description": r.description,
            "is_builtin": True,
        })

    tpl = load_template(client_slug)
    if tpl:
        for cr in tpl.client_report_defs:
            result.append({
                "name": cr["name"],
                "title": cr["title"],
                "description": cr.get("description", ""),
                "is_builtin": False,
            })

    return result


def get_client_label(client_slug: str, key: str) -> str:
    """Return the client-specific label for a metric key, or key itself."""
    tpl = load_template(client_slug)
    if tpl and key in tpl.labels:
        return tpl.labels[key]
    return key


def get_client_labels(client_slug: str) -> Dict[str, str]:
    """Return all client-specific labels (can be empty)."""
    tpl = load_template(client_slug)
    if tpl:
        return dict(tpl.labels)
    return {}


def get_client_sql(client_slug: str, report_name: str) -> Optional[str]:
    """Return client-specific SQL for a report name, or None if built-in."""
    tpl = load_template(client_slug)
    if tpl:
        for cr in tpl.client_report_defs:
            if cr["name"] == report_name:
                return cr["sql"]
    return None


def invalidate_cache(client_slug: str) -> None:
    """Clear cached template for a client (used after template update)."""
    _cache.pop(client_slug, None)


def default_template(client_slug: str, client_name: str) -> ClientTemplate:
    """Create a sensible default template payload for a new client."""
    return ClientTemplate(
        client_name=client_name,
        labels={},
        client_report_defs=[],
        source_path="",
    )
