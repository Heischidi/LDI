"""Real-time database-backed dashboard metrics and chart aggregations."""

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_OFFICER, ROLE_SUPER_ADMIN, ROLE_VIEWER, require_roles
from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    AuditLog,
    Destination,
    DocumentClassification,
    DocumentType,
    ProcessingJob,
    TravelPurpose,
    UploadBatch,
    UploadedDocument,
    User,
)
from app.schemas.reports import DashboardMetrics

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> DashboardMetrics:
    is_super_admin = bool(current_user.role and current_user.role.name == ROLE_SUPER_ADMIN)

    def _scope_app(stmt):
        return stmt if is_super_admin else stmt.where(Applicant.assigned_officer_id == current_user.id)

    total_applicants = db.scalar(
        _scope_app(select(func.count(Applicant.id)).where(Applicant.is_archived.is_(False)))
    ) or 0

    total_documents_processed = db.scalar(
        _scope_app(
            select(func.count(UploadedDocument.id))
            .join(Applicant, UploadedDocument.applicant_id == Applicant.id)
            .where(UploadedDocument.processing_status.in_(["AWAITING_REVIEW", "APPROVED", "COMPLETED"]))
        )
    ) or 0

    applications_processing = db.scalar(
        _scope_app(
            select(func.count(UploadBatch.id))
            .join(Applicant, UploadBatch.applicant_id == Applicant.id)
            .where(UploadBatch.status.in_(["UPLOADED", "QUEUED", "PROCESSING"]))
        )
    ) or 0

    completed_batches = db.scalar(
        _scope_app(
            select(func.count(UploadBatch.id))
            .join(Applicant, UploadBatch.applicant_id == Applicant.id)
            .where(UploadBatch.status.in_(["AWAITING_REVIEW", "APPROVED", "COMPLETED"]))
        )
    ) or 0

    apps_with_missing_sub = _scope_app(
        select(ApplicantDocumentStatus.applicant_id)
        .join(Applicant, ApplicantDocumentStatus.applicant_id == Applicant.id)
        .where(ApplicantDocumentStatus.status == "MISSING")
        .distinct()
    )
    applications_with_missing_docs = len(db.scalars(apps_with_missing_sub).all())

    documents_awaiting_review = db.scalar(
        _scope_app(
            select(func.count(DocumentClassification.id))
            .join(UploadedDocument, DocumentClassification.uploaded_document_id == UploadedDocument.id)
            .join(Applicant, UploadedDocument.applicant_id == Applicant.id)
            .where(
                DocumentClassification.is_current.is_(True),
                DocumentClassification.status.in_(["PENDING_REVIEW", "MANUAL_REQUIRED", "AUTO_PREPARED"]),
            )
        )
    ) or 0

    failed_processing_jobs = db.scalar(
        _scope_app(
            select(func.count(ProcessingJob.id))
            .join(UploadBatch, ProcessingJob.batch_id == UploadBatch.id)
            .join(Applicant, UploadBatch.applicant_id == Applicant.id)
            .where(ProcessingJob.status == "FAILED")
        )
    ) or 0

    total_batches = db.scalar(
        _scope_app(select(func.count(UploadBatch.id)).join(Applicant, UploadBatch.applicant_id == Applicant.id))
    ) or 0
    completion_rate = round((completed_batches / total_batches) * 100.0, 1) if total_batches else 0.0

    # Documents over time (grouped by date string)
    docs_dates = db.scalars(
        _scope_app(
            select(UploadedDocument.created_at).join(Applicant, UploadedDocument.applicant_id == Applicant.id)
        )
    ).all()
    date_buckets: dict[str, int] = defaultdict(int)
    for dt in docs_dates:
        date_buckets[dt.strftime("%Y-%m-%d")] += 1
    documents_over_time = [
        {"date": k, "count": v} for k, v in sorted(date_buckets.items())[-14:]
    ]

    # Applicants by destination
    dest_rows = db.execute(
        _scope_app(
            select(Destination.name, func.count(Applicant.id))
            .join(Applicant, Applicant.destination_id == Destination.id)
            .where(Applicant.is_archived.is_(False))
        )
        .group_by(Destination.name)
        .order_by(desc(func.count(Applicant.id)))
    ).all()
    applicants_by_destination = [{"name": name, "count": cnt} for name, cnt in dest_rows]

    # Applicants by travel purpose
    purp_rows = db.execute(
        _scope_app(
            select(TravelPurpose.name, func.count(Applicant.id))
            .join(Applicant, Applicant.purpose_id == TravelPurpose.id)
            .where(Applicant.is_archived.is_(False))
        )
        .group_by(TravelPurpose.name)
        .order_by(desc(func.count(Applicant.id)))
    ).all()
    applicants_by_purpose = [{"name": name, "count": cnt} for name, cnt in purp_rows]

    # Missing document statistics
    missing_rows = db.execute(
        _scope_app(
            select(DocumentType.name, func.count(ApplicantDocumentStatus.id))
            .join(ApplicantDocumentStatus, ApplicantDocumentStatus.document_type_id == DocumentType.id)
            .join(Applicant, ApplicantDocumentStatus.applicant_id == Applicant.id)
            .where(ApplicantDocumentStatus.status == "MISSING")
        )
        .group_by(DocumentType.name)
        .order_by(desc(func.count(ApplicantDocumentStatus.id)))
        .limit(8)
    ).all()
    missing_document_stats = [{"document_type": name, "missing_count": cnt} for name, cnt in missing_rows]

    # Recent applicants
    recent_apps = (
        db.scalars(
            _scope_app(
                select(Applicant)
                .options(joinedload(Applicant.destination), joinedload(Applicant.purpose))
                .where(Applicant.is_archived.is_(False))
            )
            .order_by(desc(Applicant.created_at))
            .limit(6)
        )
        .unique()
        .all()
    )
    recent_applicants = [
        {
            "id": a.id,
            "application_reference": a.application_reference,
            "full_name": f"{a.first_name} {a.last_name}",
            "destination": a.destination.name if a.destination else "",
            "purpose": a.purpose.name if a.purpose else "",
            "status": a.status,
            "created_at": a.created_at,
        }
        for a in recent_apps
    ]

    # Recent processing / audit activity
    audit_stmt = select(AuditLog)
    if not is_super_admin:
        audit_stmt = audit_stmt.where(AuditLog.actor_user_id == current_user.id)
    recent_logs = db.scalars(audit_stmt.order_by(desc(AuditLog.created_at)).limit(10)).all()
    recent_activity = [
        {
            "id": log.id,
            "action": log.action,
            "entity_type": log.entity_type,
            "actor_email": log.actor_email or "System Pipeline",
            "created_at": log.created_at,
        }
        for log in recent_logs
    ]

    # Officer activity stats
    officer_stmt = (
        select(User.first_name, User.last_name, User.email, func.count(Applicant.id))
        .join(Applicant, Applicant.assigned_officer_id == User.id)
    )
    if not is_super_admin:
        officer_stmt = officer_stmt.where(User.id == current_user.id)
    officer_rows = db.execute(
        officer_stmt.group_by(User.id, User.first_name, User.last_name, User.email).order_by(
            desc(func.count(Applicant.id))
        )
    ).all()
    officer_activity = [
        {"name": f"{fn} {ln}", "email": em, "assigned_applicants": cnt}
        for fn, ln, em, cnt in officer_rows
    ]

    return DashboardMetrics(
        total_applicants=total_applicants,
        total_documents_processed=total_documents_processed,
        applications_processing=applications_processing,
        completed_batches=completed_batches,
        applications_with_missing_docs=applications_with_missing_docs,
        documents_awaiting_review=documents_awaiting_review,
        failed_processing_jobs=failed_processing_jobs,
        completion_rate_percent=completion_rate,
        documents_over_time=documents_over_time,
        applicants_by_destination=applicants_by_destination,
        applicants_by_purpose=applicants_by_purpose,
        missing_document_stats=missing_document_stats,
        recent_applicants=recent_applicants,
        recent_activity=recent_activity,
        officer_activity=officer_activity,
    )
