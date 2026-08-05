"""GET /reports, POST /reports/generate."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.api.schemas import ReportGenerateRequest, ReportSummary
from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.database.connection import get_db
from backend.reports import csv_export, pdf_generator, report_service
from backend.reports.templates.report_templates import REPORT_SECTIONS, REPORT_TITLES

router = APIRouter()

_CONTENT_TYPES = {
    "json": "application/json",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


@router.get("/reports", response_model=list[ReportSummary], summary="List available report types")
async def list_reports(user: User = Depends(require_permission("reports:read"))) -> list[ReportSummary]:
    return [ReportSummary(report_type=rt, title=REPORT_TITLES[rt]) for rt in REPORT_SECTIONS]


@router.post("/reports/generate", summary="Generate a report in JSON, CSV, or PDF format")
async def generate_report(
    payload: ReportGenerateRequest, db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:generate")),
) -> Response:
    if payload.format not in _CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown format '{payload.format}'. Valid formats: {list(_CONTENT_TYPES)}")

    try:
        report = report_service.generate(
            db, payload.report_type, start_date=payload.start_date, end_date=payload.end_date, incident_id=payload.incident_id,
        )
    except report_service.UnknownReportTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if payload.format == "json":
        body = json.dumps(report, default=str).encode("utf-8")
    elif payload.format == "csv":
        body = csv_export.to_csv(report)
    else:
        body = pdf_generator.to_pdf(report)

    filename = f"{payload.report_type}_report.{payload.format}"
    return Response(
        content=body, media_type=_CONTENT_TYPES[payload.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
