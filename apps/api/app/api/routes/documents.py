"""Document upload, preview, AI review/override, approval, and bulk-approval endpoints."""

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import delete, desc, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    ROLE_ADMIN,
    ROLE_OFFICER,
    ROLE_SUPER_ADMIN,
    ROLE_VIEWER,
    ensure_applicant_access,
    require_roles,
)
from app.document_processing.mime_validator import UploadValidationError, validate_and_unpack_upload
from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    DocumentClassification,
    DocumentReview,
    DocumentType,
    ProcessedDocument,
    ProcessingJob,
    UploadBatch,
    UploadedDocument,
    User,
)
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.schemas.documents import (
    BulkApproveRequest,
    ClassificationCorrectionRequest,
    ClassificationRead,
    DocumentDetailRead,
)
from app.services.audit_service import record_audit_event
from app.services.checklist_service import sync_applicant_checklist_and_naming
from app.services.intelligence_pipeline import process_single_document
from app.services.requirements_engine import resolve_canonical_document_type
from app.storage.service import get_storage_backend

router = APIRouter(prefix="/documents", tags=["Documents & Classification Review"])


def _serialize_document(doc: UploadedDocument, doc_type_names: dict[str, str] | None = None) -> DocumentDetailRead:
    cls = next((c for c in doc.classifications if c.is_current), None)
    cls_read = None
    if cls:
        cls_read = ClassificationRead(
            id=cls.id,
            predicted_type_code=cls.predicted_type_code,
            document_type_id=cls.document_type_id,
            document_type_name=(doc_type_names or {}).get(cls.predicted_type_code, cls.predicted_type_code),
            confidence=cls.confidence,
            confidence_tier=cls.confidence_tier,
            extracted_applicant_name=cls.extracted_applicant_name,
            name_match_score=cls.name_match_score,
            has_name_mismatch=cls.has_name_mismatch,
            document_number=cls.document_number,
            issuing_authority=cls.issuing_authority,
            issue_date=cls.issue_date,
            expiry_date=cls.expiry_date,
            is_expired=cls.is_expired,
            page_count=cls.page_count,
            is_readable=cls.is_readable,
            possible_issues=cls.possible_issues or [],
            classification_reason=cls.classification_reason,
            ai_provider=cls.ai_provider,
            ai_model=cls.ai_model,
            status=cls.status,
            created_at=cls.created_at,
        )

    return DocumentDetailRead(
        id=doc.id,
        batch_id=doc.batch_id,
        applicant_id=doc.applicant_id,
        original_filename=doc.original_filename,
        source_archive_name=doc.source_archive_name,
        file_extension=doc.file_extension,
        detected_mime_type=doc.detected_mime_type,
        file_size_bytes=doc.file_size_bytes,
        sha256_hash=doc.sha256_hash,
        ingestion_type=doc.ingestion_type,
        page_count=doc.page_count,
        processing_status=doc.processing_status,
        is_excluded=doc.is_excluded,
        is_duplicate=doc.is_duplicate,
        duplicate_of_id=doc.duplicate_of_id,
        duplicate_reason=doc.duplicate_reason,
        error_message=doc.error_message,
        extracted_text_preview=(doc.extracted_data.raw_text[:500] if doc.extracted_data else ""),
        extraction_method=doc.extracted_data.extraction_method if doc.extracted_data else None,
        ocr_confidence=doc.extracted_data.ocr_confidence if doc.extracted_data else None,
        is_blurry=doc.extracted_data.is_blurry if doc.extracted_data else False,
        is_incomplete=doc.extracted_data.is_incomplete if doc.extracted_data else False,
        classification=cls_read,
        proposed_filename=doc.processed_document.generated_filename if doc.processed_document else None,
        is_approved_for_export=doc.processed_document.is_approved_for_export if doc.processed_document else False,
        preview_url=f"/api/documents/{doc.id}/preview",
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/upload", status_code=201)
async def upload_documents(
    request: Request,
    applicant_id: str = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> dict:
    """Validate, unpack ZIPs safely, and persist immutable original uploads in private storage."""
    applicant = db.scalar(select(Applicant).where(Applicant.id == applicant_id))
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found.")
    ensure_applicant_access(applicant, current_user)

    if not files:
        raise HTTPException(status_code=400, detail="At least one file must be uploaded.")

    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Upload exceeds configured limit of {settings.MAX_BATCH_FILES} files per batch.",
        )

    validated_items = []
    rejected_files = []

    for f in files:
        raw_bytes = await f.read()
        try:
            items = validate_and_unpack_upload(f.filename or "upload.bin", raw_bytes)
            validated_items.extend(items)
        except UploadValidationError as exc:
            rejected_files.append({"filename": f.filename, "reason": str(exc)})

    if not validated_items:
        raise HTTPException(
            status_code=400,
            detail={"message": "No valid documents in upload.", "rejected": rejected_files},
        )

    if len(validated_items) > settings.MAX_ZIP_EXTRACT_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Total extracted files ({len(validated_items)}) exceeds limit of {settings.MAX_ZIP_EXTRACT_FILES}.",
        )

    batch = UploadBatch(
        applicant_id=applicant.id,
        uploaded_by_id=current_user.id,
        requirement_version_id=applicant.requirement_version_id,
        status="UPLOADED",
        total_files=len(validated_items),
        processed_files=0,
        failed_files=0,
    )
    db.add(batch)
    db.flush()

    storage = get_storage_backend()
    created_docs: list[UploadedDocument] = []

    for item in validated_items:
        doc_uuid = str(uuid.uuid4())
        # Immutable original key outside public paths
        storage_key = f"originals/{applicant.application_reference}/{batch.id}/{doc_uuid}_{item.original_filename}"
        storage.put_bytes(storage_key, item.content, content_type=item.detected_mime_type)

        up_doc = UploadedDocument(
            id=doc_uuid,
            batch_id=batch.id,
            applicant_id=applicant.id,
            original_filename=item.original_filename,
            source_archive_name=item.source_archive_name,
            file_extension=item.extension,
            detected_mime_type=item.detected_mime_type,
            file_size_bytes=item.size_bytes,
            sha256_hash=item.sha256_hash,
            storage_key=storage_key,
            ingestion_type="PENDING",
            processing_status="UPLOADED",
            uploaded_by_id=current_user.id,
        )
        db.add(up_doc)
        db.flush()

        db.add(
            ProcessingJob(
                batch_id=batch.id,
                uploaded_document_id=up_doc.id,
                status="UPLOADED",
                progress_percent=0,
            )
        )
        created_docs.append(up_doc)

        record_audit_event(
            db,
            action="DOCUMENT_UPLOADED",
            entity_type="uploaded_document",
            entity_id=up_doc.id,
            actor=current_user,
            metadata={
                "applicant_id": applicant.id,
                "original_filename": item.original_filename,
                "size_bytes": item.size_bytes,
                "mime_type": item.detected_mime_type,
            },
            request=request,
        )

    applicant.status = "DOCUMENTS_UPLOADED"
    db.commit()

    return {
        "batch_id": batch.id,
        "applicant_id": applicant.id,
        "total_accepted": len(created_docs),
        "rejected": rejected_files,
        "documents": [_serialize_document(d) for d in created_docs],
    }


@router.get("", response_model=list[dict])
def list_processed_documents(
    applicant_id: str | None = None,
    approved_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> list[dict]:
    """List documents with original-to-standardised filename mapping for Processed Documents workspace."""
    stmt = (
        select(UploadedDocument)
        .join(Applicant, UploadedDocument.applicant_id == Applicant.id)
        .options(
            joinedload(UploadedDocument.applicant),
            joinedload(UploadedDocument.classifications),
            joinedload(UploadedDocument.processed_document),
        )
        .order_by(desc(UploadedDocument.created_at))
        .limit(limit)
    )
    if applicant_id:
        stmt = stmt.where(UploadedDocument.applicant_id == applicant_id)
    if not (current_user.role and current_user.role.name == ROLE_SUPER_ADMIN):
        stmt = stmt.where(Applicant.assigned_officer_id == current_user.id)

    docs = db.scalars(stmt).unique().all()
    results = []
    for d in docs:
        if approved_only and not (d.processed_document and d.processed_document.is_approved_for_export):
            continue
        cls = next((c for c in d.classifications if c.is_current), None)
        results.append(
            {
                "id": d.id,
                "applicant_id": d.applicant_id,
                "applicant_name": f"{d.applicant.first_name} {d.applicant.last_name}" if d.applicant else "",
                "application_reference": d.applicant.application_reference if d.applicant else "",
                "original_filename": d.original_filename,
                "generated_filename": d.processed_document.generated_filename if d.processed_document else None,
                "relative_folder_path": d.processed_document.relative_folder_path if d.processed_document else None,
                "is_approved_for_export": d.processed_document.is_approved_for_export if d.processed_document else False,
                "predicted_type_code": cls.predicted_type_code if cls else None,
                "confidence": cls.confidence if cls else None,
                "confidence_tier": cls.confidence_tier if cls else None,
                "classification_status": cls.status if cls else None,
                "is_duplicate": d.is_duplicate,
                "is_excluded": d.is_excluded,
                "processing_status": d.processing_status,
                "preview_url": f"/api/documents/{d.id}/preview",
                "created_at": d.created_at,
            }
        )
    return results


@router.get("/{document_id}", response_model=DocumentDetailRead)
def get_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> DocumentDetailRead:
    doc = db.scalar(
        select(UploadedDocument)
        .options(
            joinedload(UploadedDocument.applicant),
            joinedload(UploadedDocument.classifications),
            joinedload(UploadedDocument.extracted_data),
            joinedload(UploadedDocument.processed_document),
        )
        .where(UploadedDocument.id == document_id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.applicant:
        ensure_applicant_access(doc.applicant, current_user)

    doc_types = {dt.code: dt.name for dt in db.scalars(select(DocumentType)).all()}
    record_audit_event(
        db,
        action="DOCUMENT_VIEWED",
        entity_type="uploaded_document",
        entity_id=doc.id,
        actor=current_user,
        request=request,
    )
    db.commit()
    return _serialize_document(doc, doc_types)


@router.get("/{document_id}/preview")
def preview_document(
    document_id: str,
    request: Request,
    download: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> Response:
    """Serve private document bytes securely to authorized staff using the standardized filename when available."""
    doc = db.scalar(
        select(UploadedDocument)
        .options(
            joinedload(UploadedDocument.applicant),
            joinedload(UploadedDocument.processed_document),
        )
        .where(UploadedDocument.id == document_id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.applicant:
        ensure_applicant_access(doc.applicant, current_user)

    storage = get_storage_backend()
    try:
        content = storage.get_bytes(doc.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Stored document object not found.") from exc

    resolved_filename = (
        doc.processed_document.generated_filename
        if doc.processed_document and doc.processed_document.generated_filename
        else doc.original_filename
    )
    disposition = "attachment" if download else "inline"

    record_audit_event(
        db,
        action="DOCUMENT_DOWNLOADED" if download else "DOCUMENT_VIEWED",
        entity_type="uploaded_document",
        entity_id=doc.id,
        actor=current_user,
        metadata={"preview": not download, "download": download, "filename": resolved_filename},
        request=request,
    )
    db.commit()
    return Response(
        content=content,
        media_type=doc.detected_mime_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{resolved_filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/{document_id}/classify", response_model=DocumentDetailRead)
def classify_document_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> DocumentDetailRead:
    existing = db.scalar(
        select(UploadedDocument)
        .options(joinedload(UploadedDocument.applicant))
        .where(UploadedDocument.id == document_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found.")
    if existing.applicant:
        ensure_applicant_access(existing.applicant, current_user)

    doc = process_single_document(db, document_id)
    sync_applicant_checklist_and_naming(db, doc.applicant_id)
    db.commit()
    return get_document_for_response(db, doc.id)


@router.post("/{document_id}/reprocess", response_model=DocumentDetailRead)
def reprocess_document_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> DocumentDetailRead:
    existing = db.scalar(
        select(UploadedDocument)
        .options(joinedload(UploadedDocument.applicant))
        .where(UploadedDocument.id == document_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found.")
    if existing.applicant:
        ensure_applicant_access(existing.applicant, current_user)

    doc = process_single_document(db, document_id)
    sync_applicant_checklist_and_naming(db, doc.applicant_id)
    db.commit()
    return get_document_for_response(db, doc.id)


def get_document_for_response(db: Session, document_id: str) -> DocumentDetailRead:
    doc = db.scalar(
        select(UploadedDocument)
        .options(
            joinedload(UploadedDocument.classifications),
            joinedload(UploadedDocument.extracted_data),
            joinedload(UploadedDocument.processed_document),
        )
        .where(UploadedDocument.id == document_id)
    )
    doc_types = {dt.code: dt.name for dt in db.scalars(select(DocumentType)).all()}
    return _serialize_document(doc, doc_types)


@router.patch("/{document_id}/classification", response_model=DocumentDetailRead)
def review_or_correct_classification(
    document_id: str,
    payload: ClassificationCorrectionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> DocumentDetailRead:
    """Allow an officer to confirm, override document type, correct metadata, flag duplicate, or exclude."""
    doc = db.scalar(
        select(UploadedDocument)
        .options(
            joinedload(UploadedDocument.applicant),
            joinedload(UploadedDocument.classifications),
            joinedload(UploadedDocument.extracted_data),
            joinedload(UploadedDocument.processed_document),
        )
        .where(UploadedDocument.id == document_id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.applicant:
        ensure_applicant_access(doc.applicant, current_user)

    cls = next((c for c in doc.classifications if c.is_current), None)
    if not cls:
        raise HTTPException(status_code=400, detail="Document has not been classified yet.")

    prev_code = cls.predicted_type_code
    new_code = prev_code

    if payload.action == "MARK_UNKNOWN":
        new_code = "UNKNOWN"
    elif payload.action == "MARK_ADDITIONAL":
        new_code = "ADDITIONAL_DOCUMENT"
    elif payload.document_type_code:
        dt = resolve_canonical_document_type(db, payload.document_type_code)
        if not dt:
            raise HTTPException(status_code=400, detail="Unknown document type code.")
        new_code = dt.code
        cls.document_type_id = dt.id

    if new_code != prev_code:
        dt_new = resolve_canonical_document_type(db, new_code)
        cls.predicted_type_code = new_code
        cls.document_type_id = dt_new.id if dt_new else None

    if payload.extracted_applicant_name is not None:
        cls.extracted_applicant_name = payload.extracted_applicant_name
        cls.has_name_mismatch = False
    if payload.document_number is not None:
        cls.document_number = payload.document_number
    if payload.issuing_authority is not None:
        cls.issuing_authority = payload.issuing_authority
    if payload.issue_date is not None:
        cls.issue_date = payload.issue_date
    if payload.expiry_date is not None:
        cls.expiry_date = payload.expiry_date
        cls.is_expired = False

    if payload.action == "FLAG_DUPLICATE" or payload.is_duplicate is True:
        doc.is_duplicate = True
        doc.duplicate_reason = payload.notes or "Manually flagged as possible duplicate by officer."
    elif payload.is_duplicate is False:
        doc.is_duplicate = False
        doc.duplicate_reason = None

    if payload.action == "EXCLUDE" or payload.is_excluded is True:
        doc.is_excluded = True
        cls.status = "EXCLUDED"
    elif payload.action == "INCLUDE" or payload.is_excluded is False:
        doc.is_excluded = False
        cls.status = "CORRECTED"
    elif payload.action == "CONFIRM":
        cls.status = "APPROVED"
        doc.processing_status = "APPROVED"
    else:
        cls.status = "CORRECTED"

    db.add(
        DocumentReview(
            uploaded_document_id=doc.id,
            classification_id=cls.id,
            reviewed_by_id=current_user.id,
            previous_type_code=prev_code,
            new_type_code=new_code,
            action=payload.action,
            corrected_metadata=payload.model_dump(exclude_none=True),
            notes=payload.notes,
        )
    )

    sync_applicant_checklist_and_naming(db, doc.applicant_id)

    record_audit_event(
        db,
        action="CLASSIFICATION_CORRECTED" if new_code != prev_code else "CLASSIFICATION_REVIEWED",
        entity_type="uploaded_document",
        entity_id=doc.id,
        actor=current_user,
        metadata={
            "action": payload.action,
            "previous_type_code": prev_code,
            "new_type_code": new_code,
            "is_excluded": doc.is_excluded,
        },
        request=request,
    )
    db.commit()
    return get_document_for_response(db, doc.id)


@router.post("/{document_id}/approve", response_model=DocumentDetailRead)
def approve_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> DocumentDetailRead:
    """Approve an individual document classification for inclusion in the final organised package."""
    doc = db.scalar(
        select(UploadedDocument)
        .options(
            joinedload(UploadedDocument.applicant),
            joinedload(UploadedDocument.classifications),
        )
        .where(UploadedDocument.id == document_id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.applicant:
        ensure_applicant_access(doc.applicant, current_user)

    cls = next((c for c in doc.classifications if c.is_current), None)
    if not cls:
        raise HTTPException(status_code=400, detail="Document has not been classified yet.")

    if doc.is_excluded:
        raise HTTPException(status_code=400, detail="Excluded documents cannot be approved for export.")

    cls.status = "APPROVED"
    doc.processing_status = "APPROVED"
    db.add(
        DocumentReview(
            uploaded_document_id=doc.id,
            classification_id=cls.id,
            reviewed_by_id=current_user.id,
            previous_type_code=cls.predicted_type_code,
            new_type_code=cls.predicted_type_code,
            action="CONFIRM",
            notes="Officer approved document for final folder export.",
        )
    )
    sync_applicant_checklist_and_naming(db, doc.applicant_id)
    record_audit_event(
        db,
        action="DOCUMENT_APPROVED",
        entity_type="uploaded_document",
        entity_id=doc.id,
        actor=current_user,
        metadata={"type_code": cls.predicted_type_code},
        request=request,
    )
    db.commit()
    return get_document_for_response(db, doc.id)


@router.post("/bulk-approve")
def bulk_approve_high_confidence(
    payload: BulkApproveRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> dict:
    """Bulk approve high-confidence non-duplicate, non-excluded classifications for an applicant."""
    applicant = db.scalar(select(Applicant).where(Applicant.id == payload.applicant_id))
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found.")
    ensure_applicant_access(applicant, current_user)

    stmt = (
        select(UploadedDocument)
        .options(joinedload(UploadedDocument.classifications))
        .where(
            UploadedDocument.applicant_id == payload.applicant_id,
            UploadedDocument.is_excluded.is_(False),
            UploadedDocument.is_duplicate.is_(False),
        )
    )
    if payload.document_ids:
        stmt = stmt.where(UploadedDocument.id.in_(payload.document_ids))

    docs = db.scalars(stmt).unique().all()
    approved_ids: list[str] = []

    for doc in docs:
        cls = next((c for c in doc.classifications if c.is_current), None)
        if not cls:
            continue
        if cls.confidence >= payload.min_confidence and cls.predicted_type_code not in {"UNKNOWN"}:
            if not cls.has_name_mismatch and not cls.is_expired:
                cls.status = "APPROVED"
                doc.processing_status = "APPROVED"
                approved_ids.append(doc.id)
                db.add(
                    DocumentReview(
                        uploaded_document_id=doc.id,
                        classification_id=cls.id,
                        reviewed_by_id=current_user.id,
                        previous_type_code=cls.predicted_type_code,
                        new_type_code=cls.predicted_type_code,
                        action="BULK_APPROVE",
                        notes=f"Bulk approved (confidence {cls.confidence:.2f})",
                    )
                )

    sync_applicant_checklist_and_naming(db, applicant.id)

    # Check if applicant now has approved docs and no remaining pending review
    remaining_pending = db.scalar(
        select(UploadedDocument.id)
        .join(DocumentClassification)
        .where(
            UploadedDocument.applicant_id == applicant.id,
            UploadedDocument.is_excluded.is_(False),
            DocumentClassification.is_current.is_(True),
            DocumentClassification.status.in_(["PENDING_REVIEW", "MANUAL_REQUIRED"]),
        )
    )
    if not remaining_pending and approved_ids:
        applicant.status = "APPROVED"

    record_audit_event(
        db,
        action="FOLDER_BULK_APPROVED",
        entity_type="applicant",
        entity_id=applicant.id,
        actor=current_user,
        metadata={"approved_count": len(approved_ids)},
        request=request,
    )
    db.commit()
    return {"approved_count": len(approved_ids), "approved_document_ids": approved_ids}


def _delete_uploaded_document(db: Session, doc: UploadedDocument) -> str:
    """Remove an uploaded document, its dependent job/processed rows, and stored object."""
    applicant_id = doc.applicant_id
    db.execute(
        update(ApplicantDocumentStatus)
        .where(ApplicantDocumentStatus.matched_document_id == doc.id)
        .values(matched_document_id=None)
    )
    db.execute(
        update(UploadedDocument)
        .where(UploadedDocument.duplicate_of_id == doc.id)
        .values(duplicate_of_id=None, is_duplicate=False)
    )
    db.execute(delete(ProcessingJob).where(ProcessingJob.uploaded_document_id == doc.id))
    db.execute(delete(ProcessedDocument).where(ProcessedDocument.uploaded_document_id == doc.id))
    try:
        get_storage_backend().delete(doc.storage_key)
    except Exception:
        pass
    if doc.batch is not None:
        doc.batch.total_files = max(0, (doc.batch.total_files or 1) - 1)
    db.delete(doc)
    db.flush()
    return applicant_id


@router.post("/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_documents(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> BatchDeleteResponse:
    """Delete multiple uploaded documents and re-sync affected applicant checklists."""
    if not payload.ids:
        return BatchDeleteResponse(message="No documents selected.", deleted_count=0, deleted_ids=[])

    docs = (
        db.scalars(
            select(UploadedDocument)
            .options(joinedload(UploadedDocument.applicant), joinedload(UploadedDocument.batch))
            .where(UploadedDocument.id.in_(payload.ids))
        )
        .unique()
        .all()
    )
    for doc in docs:
        if doc.applicant:
            ensure_applicant_access(doc.applicant, current_user)

    deleted_ids: list[str] = []
    affected_applicants: set[str] = set()
    for doc in docs:
        deleted_ids.append(doc.id)
        affected_applicants.add(_delete_uploaded_document(db, doc))

    for app_id in affected_applicants:
        sync_applicant_checklist_and_naming(db, app_id)

    record_audit_event(
        db,
        action="DOCUMENTS_BATCH_DELETED",
        entity_type="uploaded_document",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "document_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} document(s).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> MessageResponse:
    """Delete a single uploaded document and re-sync the applicant's checklist."""
    doc = db.scalar(
        select(UploadedDocument)
        .options(joinedload(UploadedDocument.applicant), joinedload(UploadedDocument.batch))
        .where(UploadedDocument.id == document_id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.applicant:
        ensure_applicant_access(doc.applicant, current_user)

    filename = doc.original_filename
    applicant_id = _delete_uploaded_document(db, doc)
    sync_applicant_checklist_and_naming(db, applicant_id)
    record_audit_event(
        db,
        action="DOCUMENT_DELETED",
        entity_type="uploaded_document",
        entity_id=document_id,
        actor=current_user,
        metadata={"applicant_id": applicant_id, "filename": filename},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Deleted document {filename}.")
