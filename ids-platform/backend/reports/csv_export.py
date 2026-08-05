"""CSV export - flattens a report's tabular sections into CSV bytes."""

from __future__ import annotations

import csv
import io


def to_csv(report: dict) -> bytes:
    """
    Renders every dict-of-dicts or list-of-dicts section in `report["sections"]`
    as its own CSV block (separated by a blank line and a section header) -
    a single CSV file with multiple tables, which is what a report with
    several breakdowns (by type, by severity, by source IP, ...) actually is.
    """
    buffer = io.StringIO()

    buffer.write(f"# {report['title']}\n")
    buffer.write(f"# Generated: {report['generated_at']}\n")
    buffer.write(f"# Period: {report['period_start']} to {report['period_end']}\n\n")

    for section_name, section_data in report["sections"].items():
        buffer.write(f"## {section_name}\n")
        rows = _normalize_to_rows(section_data)
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        buffer.write("\n")

    return buffer.getvalue().encode("utf-8")


def _normalize_to_rows(section_data) -> list[dict]:
    """Turns whatever shape a section is in (dict of counts, list of dicts, scalar) into rows a CSV writer can handle."""
    if isinstance(section_data, list) and section_data and isinstance(section_data[0], dict):
        return section_data
    if isinstance(section_data, dict):
        return [{"key": k, "value": v} for k, v in section_data.items()]
    if section_data is None:
        return []
    return [{"value": section_data}]
