"""Tests for pdf_generator.py and csv_export.py."""

from backend.reports import csv_export, pdf_generator

SAMPLE_REPORT = {
    "title": "Test Report",
    "report_type": "daily",
    "period_start": "2026-07-01T00:00:00+00:00",
    "period_end": "2026-07-02T00:00:00+00:00",
    "generated_at": "2026-07-02T00:00:00+00:00",
    "sections": {
        "top_attacks": [
            {"attack_type": "DoS", "total_count": 5, "avg_confidence": 91.2},
            {"attack_type": "PortScan", "total_count": 3, "avg_confidence": 70.5},
        ],
        "severity_distribution": {"High": 5, "Low": 3},
        "empty_section": None,
    },
}


class TestPdfGenerator:
    def test_produces_valid_pdf_bytes(self):
        pdf_bytes = pdf_generator.to_pdf(SAMPLE_REPORT)
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 500

    def test_handles_an_empty_section_without_raising(self):
        pdf_bytes = pdf_generator.to_pdf(SAMPLE_REPORT)
        assert pdf_bytes  # didn't raise on the None section


class TestCsvExport:
    def test_includes_the_title_and_period_as_a_header_comment(self):
        csv_bytes = csv_export.to_csv(SAMPLE_REPORT)
        text = csv_bytes.decode()
        assert "Test Report" in text
        assert "2026-07-01" in text

    def test_list_of_dicts_section_becomes_a_proper_table(self):
        text = csv_export.to_csv(SAMPLE_REPORT).decode()
        assert "attack_type" in text
        assert "DoS" in text
        assert "PortScan" in text

    def test_dict_section_becomes_key_value_rows(self):
        text = csv_export.to_csv(SAMPLE_REPORT).decode()
        assert "key,value" in text
        assert "High,5" in text

    def test_empty_section_produces_no_rows_without_raising(self):
        csv_bytes = csv_export.to_csv(SAMPLE_REPORT)
        assert csv_bytes  # didn't raise on the None section
