"""
PDF rendering via reportlab (pure Python, no system-level binary dependency
like wkhtmltopdf/weasyprint's cairo+pango - a meaningful advantage for a
backend that has to run in arbitrary deployment environments). Builds the
PDF programmatically from the report dict rather than rendering an HTML
template - report_service.py's structure (title, sections of tables/counts)
maps directly onto reportlab's flowables without needing a templating layer.
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def to_pdf(report: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(report["title"], styles["Title"]))
    story.append(Paragraph(f"Period: {report['period_start']} &ndash; {report['period_end']}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {report['generated_at']}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    for section_name, section_data in report["sections"].items():
        story.append(Paragraph(section_name.replace("_", " ").title(), styles["Heading2"]))
        story.append(_render_section(section_data, styles))
        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    return buffer.getvalue()


def _render_section(section_data, styles):
    rows = _normalize_to_rows(section_data)
    if not rows:
        return Paragraph("No data for this section.", styles["Normal"])

    headers = list(rows[0].keys())
    table_data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]

    table = Table(table_data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#182238")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    return table


def _normalize_to_rows(section_data) -> list[dict]:
    if isinstance(section_data, list) and section_data and isinstance(section_data[0], dict):
        return section_data
    if isinstance(section_data, dict):
        return [{"key": k, "value": v} for k, v in section_data.items()]
    if section_data is None:
        return []
    return [{"value": section_data}]
