"""Background document processing batch orchestration, status polling, and retry endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, desc, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_OFFICER, ROLE_SUPER_ADMIN, ROLE_VIEWER, ensure_applicant_access, require_roles
from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    DocumentType,
    ProcessedDocument,
    ProcessingJob,
    UploadBatch,
    UploadedDocument,
    User,
)
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.schemas.documents import BatchStartRequest, BatchStatusRead, ProcessingJobRead
from app.api.routes.documents import _serialize_document
from app.services.audit_service import record_audit_event
from app.services.checklist_service import sync_applicant_checklist_and_naming
from app.storage.service import get_storage_backend
from app.workers.tasks import dispatch_batch_processing

router = APIRouter(prefix="/processing", tags=["Processing Jobs"])


@router.post("/batches")
def start_batch_processing(
    payload: BatchStartRequest,
    sync: bool = Query(default=False, description="Run synchronously when requested by automated tests"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> dict:
    """Queue a document upload batch for asynchronous AI/OCR processing."""
    batch = db.scalar(
        select(UploadBatch)
        .options(joinedload(UploadBatch.documents), joinedload(UploadBatch.applicant))
        .where(UploadBatch.id == payload.batch_id)
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    if batch.applicant:
        ensure_applicant_access(batch.applicant, current_user)

    batch.status = "QUEUED"
    jobs = db.scalars(select(ProcessingJob).where(ProcessingJob.batch_id == batch.id)).all()
    for j in jobs:
        if j.status in {"UPLOADED", "FAILED"}:
            j.status = "QUEUED"
            j.progress_percent = 5
            j.error_log = None
    db.commit()

    task_id = dispatch_batch_processing(
        batch.id,
        naming_convention_override=payload.naming_convention,
        sync=sync,
    )
    return {
        "batch_id": batch.id,
        "task_id": task_id,
        "status": "COMPLETED" if sync else "QUEUED",
    }


@router.get("/batches")
def list_batches(
    applicant_id: str | None = None,
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> list[dict]:
    stmt = (
        select(UploadBatch)
        .join(Applicant, UploadBatch.applicant_id == Applicant.id)
        .options(joinedload(UploadBatch.applicant))
        .order_by(desc(UploadBatch.created_at))
        .limit(limit)
    )
    if current_user.role.name != ROLE_SUPER_ADMIN:
        stmt = stmt.where(Applicant.assigned_officer_id == current_user.id)
    if applicant_id:
        stmt = stmt.where(UploadBatch.applicant_id == applicant_id)
    batches = db.scalars(stmt).unique().all()
    return [
        {
            "id": b.id,
            "applicant_id": b.applicant_id,
            "applicant_name": f"{b.applicant.first_name} {b.applicant.last_name}" if b.applicant else "",
            "application_reference": b.applicant.application_reference if b.applicant else "",
            "status": b.status,
            "total_files": b.total_files,
            "processed_files": b.processed_files,
            "failed_files": b.failed_files,
            "started_at": b.started_at,
            "completed_at": b.completed_at,
            "created_at": b.created_at,
        }
        for b in batches
    ]


@router.get("/batches/{batch_id}", response_model=BatchStatusRead)
@router.get("/batches/{batch_id}/status", response_model=BatchStatusRead)
def get_batch_status(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> BatchStatusRead:
    batch = db.scalar(
        select(UploadBatch)
        .options(
            joinedload(UploadBatch.applicant),
            joinedload(UploadBatch.documents).joinedload(UploadedDocument.classifications),
            joinedload(UploadBatch.documents).joinedload(UploadedDocument.extracted_data),
            joinedload(UploadBatch.documents).joinedload(UploadedDocument.processed_document),
        )
        .where(UploadBatch.id == batch_id)
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    if batch.applicant:
        ensure_applicant_access(batch.applicant, current_user)

    jobs = db.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.batch_id == batch_id)
        .order_by(ProcessingJob.created_at.asc())
    ).all()
    doc_lookup = {d.id: d for d in batch.documents}
    doc_types = {dt.code: dt.name for dt in db.scalars(select(DocumentType)).all()}

    return BatchStatusRead(
        id=batch.id,
        applicant_id=batch.applicant_id,
        status=batch.status,
        total_files=batch.total_files,
        processed_files=batch.processed_files,
        failed_files=batch.failed_files,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        created_at=batch.created_at,
        jobs=[
            ProcessingJobRead(
                id=j.id,
                batch_id=j.batch_id,
                uploaded_document_id=j.uploaded_document_id,
                original_filename=(
                    doc_lookup[j.uploaded_document_id].original_filename
                    if j.uploaded_document_id and j.uploaded_document_id in doc_lookup
                    else None
                ),
                status=j.status,
                progress_percent=j.progress_percent,
                attempt_count=j.attempt_count,
                error_log=j.error_log,
                started_at=j.started_at,
                finished_at=j.finished_at,
            )
            for j in jobs
        ],
        documents=[
            _serialize_document(d, doc_types)
            for d in sorted(batch.documents, key=lambda x: x.created_at)
        ],
    )


@router.post("/batches/{batch_id}/retry")
def retry_failed_in_batch(
    batch_id: str,
    sync: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> dict:
    """Retry processing for failed or incomplete documents in a batch without re-uploading."""
    batch = db.scalar(
        select(UploadBatch)
        .options(joinedload(UploadBatch.applicant))
        .where(UploadBatch.id == batch_id)
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    if batch.applicant:
        ensure_applicant_access(batch.applicant, current_user)

    jobs = db.scalars(
        select(ProcessingJob).where(
            ProcessingJob.batch_id == batch_id,
            ProcessingJob.status.in_(["FAILED", "UPLOADED"]),
        )
    ).all()
    for j in jobs:
        j.status = "QUEUED"
        j.error_log = None
    batch.status = "QUEUED"
    db.commit()

    task_id = dispatch_batch_processing(batch.id, sync=sync)
    return {"batch_id": batch.id, "task_id": task_id, "retried_jobs": len(jobs)}


def _delete_upload_batch(db: Session, batch: UploadBatch) -> str:
    """Delete a processing batch, its documents, jobs, and stored objects."""
    applicant_id = batch.applicant_id
    doc_ids = [d.id for d in batch.documents]
    if doc_ids:
        db.execute(
            update(ApplicantDocumentStatus)
            .where(ApplicantDocumentStatus.matched_document_id.in_(doc_ids))
            .values(matched_document_id=None)
        )
        db.execute(
            update(UploadedDocument)
            .where(UploadedDocument.duplicate_of_id.in_(doc_ids))
            .values(duplicate_of_id=None, is_duplicate=False)
        )
    storage = get_storage_backend()
    for d in batch.documents:
        try:
            storage.delete(d.storage_key)
        except Exception:
            pass
    db.execute(delete(ProcessingJob).where(ProcessingJob.batch_id == batch.id))
    db.execute(delete(ProcessedDocument).where(ProcessedDocument.batch_id == batch.id))
    db.delete(batch)
    db.flush()
    return applicant_id


@router.post("/batches/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_batches(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> BatchDeleteResponse:
    """Delete multiple processing batches and re-sync affected applicant checklists."""
    if not payload.ids:
        return BatchDeleteResponse(message="No batches selected.", deleted_count=0, deleted_ids=[])

    batches = (
        db.scalars(
            select(UploadBatch)
            .options(joinedload(UploadBatch.applicant), joinedload(UploadBatch.documents))
            .where(UploadBatch.id.in_(payload.ids))
        )
        .unique()
        .all()
    )
    for b in batches:
        if b.applicant:
            ensure_applicant_access(b.applicant, current_user)

    deleted_ids: list[str] = []
    affected_applicants: set[str] = set()
    for b in batches:
        deleted_ids.append(b.id)
        affected_applicants.add(_delete_upload_batch(db, b))

    for app_id in affected_applicants:
        sync_applicant_checklist_and_naming(db, app_id)

    record_audit_event(
        db,
        action="BATCHES_DELETED",
        entity_type="upload_batch",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "batch_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} batch(es).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.delete("/batches/{batch_id}", response_model=MessageResponse)
def delete_batch(
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> MessageResponse:
    """Delete a single processing batch and all its uploaded documents."""
    batch = db.scalar(
        select(UploadBatch)
        .options(joinedload(UploadBatch.applicant), joinedload(UploadBatch.documents))
        .where(UploadBatch.id == batch_id)
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    if batch.applicant:
        ensure_applicant_access(batch.applicant, current_user)

    applicant_id = _delete_upload_batch(db, batch)
    sync_applicant_checklist_and_naming(db, applicant_id)
    record_audit_event(
        db,
        action="BATCH_DELETED",
        entity_type="upload_batch",
        entity_id=batch_id,
        actor=current_user,
        metadata={"applicant_id": applicant_id},
        request=request,
    )
    db.commit()
    return MessageResponse(message="Deleted processing batch.")
