"""
render.py - turn a report envelope into a management-ready Excel or PDF file.

Excel uses openpyxl (already a project dependency); PDF uses reportlab. Both are
optional and degrade gracefully: if a library is missing, the renderer reports
it clearly rather than crashing, matching the extractor's availability pattern.

Numbers are formatted for readers: financial figures get thousands separators,
years stay plain integers, periods keep their 3-decimal encoding, and percent
columns show two decimals.
"""
from __future__ import annotations

import os
import re


# --------------------------------------------------------------------------- #
# Shared number formatting
# --------------------------------------------------------------------------- #
def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def excel_number_format(column):
    col = column.lower()
    if col == "year":
        return "0"
    if col == "period":
        return "0.000"
    if "pct" in col or "percent" in col:
        return "0.00"
    return "#,##0"


def pdf_format(column, value):
    if value is None or value == "":
        return ""
    if not _is_number(value):
        return str(value)
    col = column.lower()
    if col == "year":
        return str(int(value))
    if col == "period":
        return f"{value:.3f}"
    if "pct" in col or "percent" in col:
        return f"{value:.2f}"
    return f"{value:,.0f}"


def _safe_sheet_title(name):
    return re.sub(r"[\\/?*\[\]:]", "_", name)[:31] or "Report"


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #
def excel_available():
    try:
        import openpyxl  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def render_excel(envelope, out_path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    columns = envelope["columns"]
    rows = envelope["rows"]

    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_title(envelope["report"])

    ncols = max(len(columns), 1)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    title_cell = ws.cell(row=1, column=1, value=envelope["title"])
    title_cell.font = Font(size=14, bold=True)

    ws.cell(row=2, column=1, value=envelope.get("description", ""))
    src = envelope.get("source", {})
    ws.cell(row=3, column=1, value=(
        f"Generated {envelope.get('generated_at', '')} | "
        f"Source {src.get('database', '')} | {envelope.get('row_count', len(rows))} rows"))

    header_row = 5
    header_fill = PatternFill("solid", fgColor="1F3B57")
    header_font = Font(bold=True, color="FFFFFF")
    for c, column in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=c, value=column)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for r, row in enumerate(rows, start=header_row + 1):
        for c, column in enumerate(columns, start=1):
            value = row.get(column)
            cell = ws.cell(row=r, column=c, value=value)
            if _is_number(value):
                cell.number_format = excel_number_format(column)
                cell.alignment = Alignment(horizontal="right")

    # Freeze the header and size columns to their content.
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    for c, column in enumerate(columns, start=1):
        width = len(str(column))
        for row in rows:
            width = max(width, len(str(row.get(column, ""))))
        ws.column_dimensions[get_column_letter(c)].width = min(max(width + 2, 10), 32)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def pdf_available():
    try:
        import reportlab  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def render_pdf(envelope, out_path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    columns = envelope["columns"]
    rows = envelope["rows"]
    styles = getSampleStyleSheet()

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    doc = SimpleDocTemplate(out_path, pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)

    src = envelope.get("source", {})
    story = [
        Paragraph(envelope["title"], styles["Title"]),
        Paragraph(envelope.get("description", ""), styles["Normal"]),
        Paragraph(
            f"Generated {envelope.get('generated_at', '')} &nbsp;|&nbsp; "
            f"Source {src.get('database', '')} &nbsp;|&nbsp; "
            f"{envelope.get('row_count', len(rows))} rows", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]

    # Smaller font for wider tables so columns still fit the page.
    font_size = 8 if len(columns) <= 8 else (7 if len(columns) <= 12 else 6)
    table_data = [columns]
    numeric_cols = set()
    for c, column in enumerate(columns):
        if rows and all(_is_number(row.get(column)) or row.get(column) in (None, "")
                        for row in rows):
            numeric_cols.add(c)
    for row in rows:
        table_data.append([pdf_format(col, row.get(col)) for col in columns])

    avail_width = doc.width
    col_width = avail_width / max(len(columns), 1)
    table = Table(table_data, colWidths=[col_width] * len(columns), repeatRows=1)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3B57")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for c in numeric_cols:
        style.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
    table.setStyle(TableStyle(style))

    story.append(table)
    doc.build(story)
    return out_path
