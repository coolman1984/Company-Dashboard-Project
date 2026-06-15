"""
render.py - turn report envelope(s) into management-ready Excel or PDF files.

Two modes share the same formatting helpers:
  * one report  -> one file        (render_excel / render_pdf)
  * many reports -> one "board pack" (render_excel_pack / render_pdf_pack):
    a single multi-sheet workbook, or a single PDF with a cover + a section per
    report - the artifact you hand to management.

Excel uses openpyxl (a project dependency); PDF uses reportlab. Both are optional
and degrade gracefully: a missing library is reported, never a crash.

Numbers are formatted for readers: financial figures get thousands separators,
years stay plain integers, periods keep their 3-decimal encoding, percent
columns show two decimals.
"""
from __future__ import annotations

import datetime as _dt
import os
import re

from . import safe_str as _safe


# --------------------------------------------------------------------------- #
# Shared number formatting
# --------------------------------------------------------------------------- #
def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _has_arabic(text):
    """True if the string contains any Arabic-script character (U+0600-06FF)."""
    return isinstance(text, str) and any("؀" <= ch <= "ۿ" for ch in text)


def envelope_has_arabic(envelope):
    """Detect Arabic anywhere in the headers or cells, to drive RTL layout."""
    if any(_has_arabic(col) for col in envelope.get("columns", [])):
        return True
    return any(_has_arabic(v) for row in envelope.get("rows", []) for v in row.values())


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


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #
def excel_available():
    try:
        import openpyxl  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _excel_write_sheet(ws, envelope):
    """Write one report onto an existing worksheet (titled, formatted, frozen)."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    columns = envelope["columns"]
    rows = envelope["rows"]
    ncols = max(len(columns), 1)

    # Arabic reports read right-to-left, so orient the whole sheet accordingly.
    if envelope_has_arabic(envelope):
        ws.sheet_view.rightToLeft = True

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
            cell = ws.cell(row=r, column=c, value=_safe(value) if not _is_number(value) else value)
            if _is_number(value):
                cell.number_format = excel_number_format(column)
                cell.alignment = Alignment(horizontal="right")

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    for c, column in enumerate(columns, start=1):
        width = len(str(column))
        for row in rows:
            width = max(width, len(str(row.get(column, ""))))
        ws.column_dimensions[get_column_letter(c)].width = min(max(width + 2, 10), 32)


def render_excel(envelope, out_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_title(envelope["report"])
    _excel_write_sheet(ws, envelope)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


def render_excel_pack(envelopes, out_path, title="Board Pack"):
    """One workbook: a Contents sheet + one sheet per report."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    contents = wb.active
    contents.title = "Contents"
    contents.cell(row=1, column=1, value=title).font = Font(size=16, bold=True)
    contents.cell(row=2, column=1, value=f"Generated {_now()}")
    contents.cell(row=4, column=1, value="Report").font = Font(bold=True)
    contents.cell(row=4, column=2, value="Rows").font = Font(bold=True)
    for i, env in enumerate(envelopes, start=5):
        contents.cell(row=i, column=1, value=env["title"])
        contents.cell(row=i, column=2, value=env.get("row_count", len(env["rows"])))
    contents.column_dimensions["A"].width = 40

    for env in envelopes:
        ws = wb.create_sheet(_safe_sheet_title(env["report"]))
        _excel_write_sheet(ws, env)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
_ARABIC_FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fonts", "NotoNaskhArabic.ttf",
)
_ARABIC_FONT_REGISTERED = False
_ARABIC_RESHAPER = None


def _arabic_shaper():
    """Lazy-load and return (reshape_fn, bidi_fn) or (None, None) if unavailable."""
    global _ARABIC_RESHAPER
    if _ARABIC_RESHAPER is not None:
        return _ARABIC_RESHAPER
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        config = arabic_reshaper.config_for_true_type_font(
            _ARABIC_FONT_PATH, arabic_reshaper.ENABLE_ALL_LIGATURES
        )
        reshaper = arabic_reshaper.ArabicReshaper(configuration=config)
        _ARABIC_RESHAPER = (reshaper.reshape, get_display)
        return _ARABIC_RESHAPER
    except Exception:
        _ARABIC_RESHAPER = (None, None)
        return _ARABIC_RESHAPER


def _shape_arabic(text):
    """Reshape + bidi an Arabic string for PDF rendering. Falls back to raw text."""
    reshape_fn, bidi_fn = _arabic_shaper()
    if not reshape_fn or not isinstance(text, str) or not _has_arabic(text):
        return text
    try:
        return bidi_fn(reshape_fn(text))
    except Exception:
        return text


def _register_arabic_font():
    """Register the Arabic font with ReportLab once."""
    global _ARABIC_FONT_REGISTERED
    if _ARABIC_FONT_REGISTERED:
        return
    if not os.path.exists(_ARABIC_FONT_PATH):
        return
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont("Arabic", _ARABIC_FONT_PATH))
        _ARABIC_FONT_REGISTERED = True
    except Exception:
        pass
def pdf_available():
    try:
        import reportlab  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _pdf_report_flowables(envelope, styles, doc_width):
    """Reportlab flowables for one report: title, meta, table."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    columns = envelope["columns"]
    rows = envelope["rows"]
    src = envelope.get("source", {})
    is_arabic = envelope_has_arabic(envelope)

    if is_arabic:
        _register_arabic_font()
        body_font = "Arabic"
        title_text = _shape_arabic(envelope["title"])
        desc_text = _shape_arabic(envelope.get("description", ""))
    else:
        body_font = "Helvetica"
        title_text = envelope["title"]
        desc_text = envelope.get("description", "")

    flow = [
        Paragraph(title_text, styles["Title"]),
        Paragraph(desc_text, styles["Normal"]),
        Paragraph(
            f"Generated {envelope.get('generated_at', '')} &nbsp;|&nbsp; "
            f"Source {src.get('database', '')} &nbsp;|&nbsp; "
            f"{envelope.get('row_count', len(rows))} rows", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]

    font_size = 8 if len(columns) <= 8 else (7 if len(columns) <= 12 else 6)
    numeric_cols = set()
    for c, column in enumerate(columns):
        if rows and all(_is_number(row.get(column)) or row.get(column) in (None, "")
                        for row in rows):
            numeric_cols.add(c)

    if is_arabic:
        table_data = [[_shape_arabic(c) for c in columns]]
        table_data += [[pdf_format(col, row.get(col)) if _is_number(row.get(col))
                        else _shape_arabic(pdf_format(col, row.get(col)))
                        for col in columns] for row in rows]
    else:
        table_data = [columns] + [[pdf_format(col, row.get(col)) for col in columns]
                                  for row in rows]
    col_width = doc_width / max(len(columns), 1)
    table = Table(table_data, colWidths=[col_width] * len(columns), repeatRows=1)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3B57")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), f"{body_font}-Bold" if is_arabic else "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), body_font),
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
    flow.append(table)
    return flow


def _pdf_doc(out_path):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    return SimpleDocTemplate(out_path, pagesize=landscape(A4),
                             leftMargin=12 * mm, rightMargin=12 * mm,
                             topMargin=12 * mm, bottomMargin=12 * mm)


def render_pdf(envelope, out_path):
    from reportlab.lib.styles import getSampleStyleSheet

    doc = _pdf_doc(out_path)
    doc.build(_pdf_report_flowables(envelope, getSampleStyleSheet(), doc.width))
    return out_path


def render_pdf_pack(envelopes, out_path, title="Board Pack"):
    """One PDF: a cover page + a section per report, page-broken between."""
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, Spacer

    styles = getSampleStyleSheet()
    doc = _pdf_doc(out_path)

    story = [
        Paragraph(title, styles["Title"]),
        Paragraph(f"Generated {_now()}", styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph("Contents", styles["Heading2"]),
    ]
    for env in envelopes:
        story.append(Paragraph(
            f"&bull; {env['title']} ({env.get('row_count', len(env['rows']))} rows)",
            styles["Normal"]))

    for env in envelopes:
        story.append(PageBreak())
        story.extend(_pdf_report_flowables(env, styles, doc.width))

    doc.build(story)
    return out_path
