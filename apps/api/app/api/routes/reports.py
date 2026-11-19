"""Analytics reports with date filtering and CSV / PDF exports."""

import csv
from datetime import date, datetime, time, timezone
import io

from fastapi import APIRouter, Depends, Query, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_OFFICER, ROLE_SUPER_ADMIN, ROLE_VIEWER, require_roles
from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    ApplicationCategory,
    Destination,
    DocumentClassification,
    DocumentReview,
    DocumentType,
    ProcessingJob,
    UploadedDocument,
    User,
)

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


def _compute_report_data(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    app_stmt = select(Applicant).where(Applicant.is_archived.is_(False))
    doc_stmt = select(UploadedDocument)
    job_stmt = select(ProcessingJob)

    if start_date:
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        app_stmt = app_stmt.where(Applicant.created_at >= start_dt)
        doc_stmt = doc_stmt.where(UploadedDocument.created_at >= start_dt)
        job_stmt = job_stmt.where(ProcessingJob.created_at >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        app_stmt = app_stmt.where(Applicant.created_at <= end_dt)
        doc_stmt = doc_stmt.where(UploadedDocument.created_at <= end_dt)
        job_stmt = job_stmt.where(ProcessingJob.created_at <= end_dt)

    applicants = db.scalars(app_stmt).all()
    docs = db.scalars(doc_stmt).all()
    jobs = db.scalars(job_stmt).all()

    durations = [
        (j.finished_at - j.started_at).total_seconds()
        for j in jobs
        if j.started_at and j.finished_at
    ]
    avg_seconds = round(sum(durations) / len(durations), 2) if durations else 0.0
    failed_jobs = sum(1 for j in jobs if j.status == "FAILED")
    failure_rate = round((failed_jobs / len(jobs)) * 100.0, 2) if jobs else 0.0

    total_classified = db.scalar(select(func.count(DocumentClassification.id))) or 0
    corrections = db.scalar(
        select(func.count(DocumentReview.id)).where(
            DocumentReview.previous_type_code != DocumentReview.new_type_code
        )
    ) or 0
    correction_rate = round((corrections / total_classified) * 100.0, 2) if total_classified else 0.0

    common_destinations = [
        {"name": name, "count": cnt}
        for name, cnt in db.execute(
            select(Destination.name, func.count(Applicant.id))
            .join(Applicant, Applicant.destination_id == Destination.id)
            .group_by(Destination.name)
            .order_by(desc(func.count(Applicant.id)))
        ).all()
    ]

    common_categories = [
        {"name": name, "count": cnt}
        for name, cnt in db.execute(
            select(ApplicationCategory.name, func.count(Applicant.id))
            .join(Applicant, Applicant.category_id == ApplicationCategory.id)
            .group_by(ApplicationCategory.name)
            .order_by(desc(func.count(Applicant.id)))
        ).all()
    ]

    missing_docs = [
        {"document_type": name, "count": cnt}
        for name, cnt in db.execute(
            select(DocumentType.name, func.count(ApplicantDocumentStatus.id))
            .join(ApplicantDocumentStatus, ApplicantDocumentStatus.document_type_id == DocumentType.id)
            .where(ApplicantDocumentStatus.status == "MISSING")
            .group_by(DocumentType.name)
            .order_by(desc(func.count(ApplicantDocumentStatus.id)))
        ).all()
    ]

    officer_stats = [
        {
            "officer_name": f"{fn} {ln}",
            "email": email,
            "uploads_count": cnt,
        }
        for fn, ln, email, cnt in db.execute(
            select(User.first_name, User.last_name, User.email, func.count(UploadedDocument.id))
            .join(UploadedDocument, UploadedDocument.uploaded_by_id == User.id)
            .group_by(User.id, User.first_name, User.last_name, User.email)
            .order_by(desc(func.count(UploadedDocument.id)))
        ).all()
    ]

    return {
        "total_applicants_processed": len(applicants),
        "total_documents_classified": len(docs),
        "average_processing_seconds": avg_seconds,
        "ai_correction_rate_percent": correction_rate,
        "processing_failure_rate_percent": failure_rate,
        "common_destinations": common_destinations,
        "common_application_types": common_categories,
        "most_frequently_missing_documents": missing_docs,
        "officer_processing_statistics": officer_stats,
    }


@router.get("/summary")
def get_report_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> dict:
    return _compute_report_data(db, start_date=start_date, end_date=end_date)


@router.get("/export/csv")
def export_report_csv(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> Response:
    data = _compute_report_data(db, start_date=start_date, end_date=end_date)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Applicants Processed", data["total_applicants_processed"]])
    writer.writerow(["Total Documents Classified", data["total_documents_classified"]])
    writer.writerow(["Average Processing Time (s)", data["average_processing_seconds"]])
    writer.writerow(["AI Correction Rate (%)", data["ai_correction_rate_percent"]])
    writer.writerow(["Processing Failure Rate (%)", data["processing_failure_rate_percent"]])
    writer.writerow([])
    writer.writerow(["Most Frequently Missing Document", "Missing Count"])
    for item in data["most_frequently_missing_documents"]:
        writer.writerow([item["document_type"], item["count"]])
    writer.writerow([])
    writer.writerow(["Destination", "Applicant Count"])
    for item in data["common_destinations"]:
        writer.writerow([item["name"], item["count"]])

    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ldi_analytics_report.csv"'},
    )


@router.get("/export/pdf")
def export_report_pdf(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> Response:
    data = _compute_report_data(db, start_date=start_date, end_date=end_date)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Leaders Document Intelligence — Executive Analytics Report", styles["Title"]),
        Spacer(1, 10),
    ]
    summary_rows = [
        ["Metric", "Value"],
        ["Total Applicants Processed", str(data["total_applicants_processed"])],
        ["Total Documents Classified", str(data["total_documents_classified"])],
        ["Average Processing Time (sec)", str(data["average_processing_seconds"])],
        ["AI Classification Correction Rate", f"{data['ai_correction_rate_percent']}%"],
        ["Processing Failure Rate", f"{data['processing_failure_rate_percent']}%"],
    ]
    tbl = Table(summary_rows, colWidths=[240, 160])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1F3A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(tbl)
    doc.build(elements)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ldi_analytics_report.pdf"'},
    )
