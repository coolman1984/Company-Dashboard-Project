"""Reports engine: generate saved report files (JSON/CSV/XLSX/PDF) from pl_detail.db.

See reports/README.md and ROADMAP.md (Stage 2).
"""

import re

_SPREADSHEET_RISKY = re.compile(r'^[=+\-@\t\r]')


def safe_str(value):
    """Prefix spreadsheet-dangerous values so they are never executed as formulas."""
    text = str(value) if value is not None else ''
    if _SPREADSHEET_RISKY.match(text):
        return "'" + text
    return text
