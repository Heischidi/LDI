"""Core AI document intelligence pipeline: extraction, OCR, classification, duplicate & name checks."""

from datetime import datetime, timezone
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.providers import get_ai_classifier
from app.core.database import SessionLocal
from app.document_processing.extractor import extract_document_content
from app.models.entities import (
    Applicant,
    DocumentClassification,
    DocumentType,
    ExtractedDocumentData,
    ProcessingJob,
    SystemSetting,
    UploadBatch,
    UploadedDocument,
)
from app.services.audit_service import record_audit_event
from app.services.checklist_service import sync_applicant_checklist_and_naming
from app.services.requirements_engine import resolve_canonical_document_type
from app.storage.service import get_storage_backend


def _confidence_tier(score: float) -> tuple[str, str]:
    """Map confidence score into (tier, initial classification status)."""
    if score >= 0.90:
        return "HIGH", "AUTO_PREPARED"
    if score >= 0.70:
        return "MEDIUM", "PENDING_REVIEW"
    return "LOW", "MANUAL_REQUIRED"


def _compute_name_match_score(extracted_name: str | None, applicant: Applicant) -> tuple[float | None, bool]:
    """Compare extracted applicant name against Applicant record tokens."""
    if not extracted_name:
        return None, False

    target_tokens = {
        t.lower()
        for t in re.findall(
            r"[a-zA-Z]+",
            " ".join(p for p in [applicant.first_name, applicant.middle_name, applicant.last_name] if p),
        )
        if len(t) >= 2
    }
    found_tokens = {t.lower() for t in re.findall(r"[a-zA-Z]+", extracted_name) if len(t) >= 2}
    if not target_tokens or not found_tokens:
        return None, False

    overlap = len(target_tokens & found_tokens)
    score = round(overlap / max(len(target_tokens & {applicant.first_name.lower(), applicant.last_name.lower()}), 1), 3)
    score = min(1.0, score)

    # Check if both first and last name appear (or strong overlap)
    core_tokens = {applicant.first_name.lower(), applicant.last_name.lower()}
    has_mismatch = len(core_tokens & found_tokens) == 0 or (len(found_tokens) >= 2 and score < 0.5)
    return score, has_mismatch


def _resolve_runtime_ai_and_ocr(db: Session) -> tuple[str | None, bool, str | None]:
    ai_setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "ai.provider"))
    ocr_setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "ocr.provider"))
    ai_provider = None
    allow_external = None
    ocr_provider = None
    if ai_setting and isinstance(ai_setting.value_json, dict):
        ai_provider = ai_setting.value_json.get("provider")
        allow_external = ai_setting.value_json.get("allow_external_ai")
    if ocr_setting and isinstance(ocr_setting.value_json, dict):
        ocr_provider = ocr_setting.value_json.get("provider")
    return ai_provider, allow_external, ocr_provider


def process_single_document(db: Session, document_id: str, job_id: str | None = None) -> UploadedDocument:
    """Run extraction, OCR, AI classification, duplicate check, and applicant matching for one document."""
    doc = db.scalar(
        select(UploadedDocument)
        .options(
            joinedload(UploadedDocument.applicant).joinedload(Applicant.destination),
            joinedload(UploadedDocument.applicant).joinedload(Applicant.purpose),
            joinedload(UploadedDocument.classifications),
        )
        .where(UploadedDocument.id == document_id)
    )
    if not doc:
        raise ValueError(f"UploadedDocument {document_id} not found.")

    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id)) if job_id else None
    if not job:
        job = db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.uploaded_document_id == document_id)
            .order_by(ProcessingJob.created_at.desc())
        )

    storage = get_storage_backend()
    ai_provider_name, allow_external, ocr_provider_name = _resolve_runtime_ai_and_ocr(db)
    classifier = get_ai_classifier(provider_override=ai_provider_name, allow_external=allow_external)

    try:
        if job:
            job.attempt_count += 1
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.status = "EXTRACTING_TEXT"
            job.progress_percent = 20
        doc.processing_status = "EXTRACTING_TEXT"
        db.commit()

        raw_bytes = storage.get_bytes(doc.storage_key)

        if job:
            job.status = "PERFORMING_OCR"
            job.progress_percent = 45
        doc.processing_status = "PERFORMING_OCR"
        db.commit()

        ext_out = extract_document_content(
            raw_bytes,
            detected_mime_type=doc.detected_mime_type,
            extension=doc.file_extension,
            ocr_provider_name=ocr_provider_name,
        )

        doc.ingestion_type = ext_out.ingestion_type
        doc.page_count = max(1, ext_out.page_count)

        # Persist ExtractedDocumentData idempotently
        existing_ext = db.scalar(
            select(ExtractedDocumentData).where(
                ExtractedDocumentData.uploaded_document_id == doc.id
            )
        )
        if existing_ext:
            existing_ext.raw_text = ext_out.raw_text
            existing_ext.normalized_text_hash = ext_out.normalized_text_hash
            existing_ext.page_texts = ext_out.page_texts
            existing_ext.extraction_method = ext_out.extraction_method
            existing_ext.ocr_confidence = ext_out.ocr_confidence
            existing_ext.is_readable = ext_out.is_readable
            existing_ext.is_blurry = ext_out.is_blurry
            existing_ext.is_incomplete = ext_out.is_incomplete
            existing_ext.detected_metadata = ext_out.detected_metadata
            existing_ext.extracted_at = datetime.now(timezone.utc)
        else:
            db.add(
                ExtractedDocumentData(
                    uploaded_document_id=doc.id,
                    raw_text=ext_out.raw_text,
                    normalized_text_hash=ext_out.normalized_text_hash,
                    page_texts=ext_out.page_texts,
                    extraction_method=ext_out.extraction_method,
                    ocr_confidence=ext_out.ocr_confidence,
                    is_readable=ext_out.is_readable,
                    is_blurry=ext_out.is_blurry,
                    is_incomplete=ext_out.is_incomplete,
                    detected_metadata=ext_out.detected_metadata,
                )
            )

        if job:
            job.status = "CLASSIFYING"
            job.progress_percent = 70
        doc.processing_status = "CLASSIFYING"
        db.commit()

        all_doc_types = [
            {"code": dt.code, "name": dt.name, "description": dt.description or ""}
            for dt in db.scalars(select(DocumentType).where(DocumentType.is_active.is_(True))).all()
        ]
        applicant = doc.applicant
        ai_result = classifier.classify(
            extracted_text=ext_out.raw_text,
            page_count=ext_out.page_count,
            ingestion_type=ext_out.ingestion_type,
            is_readable=ext_out.is_readable,
            is_blurry=ext_out.is_blurry,
            detected_metadata=ext_out.detected_metadata,
            available_doc_types=all_doc_types,
            applicant_context={
                "destination": applicant.destination.name if applicant.destination else "",
                "purpose": applicant.purpose.name if applicant.purpose else "",
            },
        )

        # Resolve canonical DocumentType (supports aliases)
        canonical_dt = resolve_canonical_document_type(db, ai_result.document_type)
        resolved_code = canonical_dt.code if canonical_dt else "UNKNOWN"

        tier, cls_status = _confidence_tier(ai_result.confidence)
        name_score, has_name_mismatch = _compute_name_match_score(
            ai_result.applicant_name, applicant
        )
        issues = list(ai_result.possible_issues)
        if has_name_mismatch:
            issues.append(
                f"Name mismatch: document names '{ai_result.applicant_name}', expected '{applicant.first_name} {applicant.last_name}'."
            )
            if cls_status == "AUTO_PREPARED":
                cls_status = "PENDING_REVIEW"

        # Check exact SHA-256 duplicate or semantic content duplicate across this applicant's earlier docs
        doc.is_duplicate = False
        doc.duplicate_of_id = None
        doc.duplicate_reason = None

        earlier_docs = db.scalars(
            select(UploadedDocument)
            .options(joinedload(UploadedDocument.extracted_data))
            .where(
                UploadedDocument.applicant_id == applicant.id,
                UploadedDocument.id != doc.id,
                UploadedDocument.created_at <= doc.created_at,
            )
            .order_by(UploadedDocument.created_at.asc())
        ).all()

        for other in earlier_docs:
            if other.sha256_hash == doc.sha256_hash:
                doc.is_duplicate = True
                doc.duplicate_of_id = other.id
                doc.duplicate_reason = f"Exact file hash match (SHA-256) with '{other.original_filename}'."
                issues.append(doc.duplicate_reason)
                break
            if (
                other.extracted_data
                and ext_out.raw_text.strip()
                and len(ext_out.raw_text.strip()) > 40
                and other.extracted_data.normalized_text_hash == ext_out.normalized_text_hash
            ):
                doc.is_duplicate = True
                doc.duplicate_of_id = other.id
                doc.duplicate_reason = f"Identical extracted text content to '{other.original_filename}'."
                issues.append(doc.duplicate_reason)
                break

        if doc.is_duplicate and cls_status == "AUTO_PREPARED":
            cls_status = "PENDING_REVIEW"

        # Check expiry directly if date present
        is_expired = False
        if ai_result.expiry_date:
            try:
                exp_dt = datetime.strptime(ai_result.expiry_date[:10], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                if exp_dt < datetime.now(timezone.utc):
                    is_expired = True
                    issues.append(f"Document expired on {ai_result.expiry_date}.")
                    cls_status = "PENDING_REVIEW"
            except ValueError:
                pass

        # Mark previous classifications non-current
        for prev in doc.classifications:
            prev.is_current = False

        cls_record = DocumentClassification(
            uploaded_document_id=doc.id,
            document_type_id=canonical_dt.id if canonical_dt else None,
            predicted_type_code=resolved_code,
            confidence=ai_result.confidence,
            confidence_tier=tier,
            extracted_applicant_name=ai_result.applicant_name,
            name_match_score=name_score,
            has_name_mismatch=has_name_mismatch,
            document_number=ai_result.document_number,
            issuing_authority=ai_result.issuing_organisation,
            issue_date=ai_result.issue_date or ai_result.document_date,
            expiry_date=ai_result.expiry_date,
            is_expired=is_expired,
            page_count=ext_out.page_count,
            is_readable=ai_result.is_readable and ext_out.is_readable,
            possible_issues=issues,
            classification_reason=ai_result.classification_reason,
            ai_provider=classifier.provider_name,
            ai_model=classifier.model_name,
            raw_ai_response=ai_result.model_dump(),
            status=cls_status,
            is_current=True,
        )
        db.add(cls_record)

        doc.processing_status = "AWAITING_REVIEW"
        doc.error_message = None

        if job:
            job.status = "AWAITING_REVIEW"
            job.progress_percent = 100
            job.finished_at = datetime.now(timezone.utc)
            job.error_log = None

        record_audit_event(
            db,
            action="DOCUMENT_CLASSIFIED",
            entity_type="uploaded_document",
            entity_id=doc.id,
            metadata={
                "predicted_type_code": resolved_code,
                "confidence": ai_result.confidence,
                "confidence_tier": tier,
                "is_duplicate": doc.is_duplicate,
                "has_name_mismatch": has_name_mismatch,
            },
        )
        db.commit()
        return doc
    except Exception as exc:
        db.rollback()
        doc = db.scalar(select(UploadedDocument).where(UploadedDocument.id == document_id))
        if doc:
            doc.processing_status = "FAILED"
            doc.error_message = str(exc)[:500]
        if job_id:
            failed_job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id))
            if failed_job:
                failed_job.status = "FAILED"
                failed_job.error_log = str(exc)[:1000]
                failed_job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


def process_batch_sync(
    batch_id: str,
    naming_convention_override: str | None = None,
) -> dict:
    """Process every queued/pending document in a batch independently and reconcile checklist."""
    db = SessionLocal()
    try:
        batch = db.scalar(
            select(UploadBatch)
            .options(joinedload(UploadBatch.documents))
            .where(UploadBatch.id == batch_id)
        )
        if not batch:
            raise ValueError(f"UploadBatch {batch_id} not found.")

        batch.status = "PROCESSING"
        batch.started_at = batch.started_at or datetime.now(timezone.utc)
        batch.processed_files = 0
        batch.failed_files = 0
        db.commit()

        docs = db.scalars(
            select(UploadedDocument)
            .where(UploadedDocument.batch_id == batch_id)
            .order_by(UploadedDocument.created_at.asc())
        ).all()

        processed_count = 0
        failed_count = 0
        for doc in docs:
            job = db.scalar(
                select(ProcessingJob)
                .where(
                    ProcessingJob.batch_id == batch_id,
                    ProcessingJob.uploaded_document_id == doc.id,
                )
                .order_by(ProcessingJob.created_at.desc())
            )
            try:
                process_single_document(db, doc.id, job_id=job.id if job else None)
                processed_count += 1
            except Exception:
                failed_count += 1

        # Refresh batch & reconcile applicant checklist
        batch = db.scalar(select(UploadBatch).where(UploadBatch.id == batch_id))
        if batch:
            batch.processed_files = processed_count
            batch.failed_files = failed_count
            batch.status = (
                "FAILED"
                if (processed_count == 0 and failed_count > 0)
                else "AWAITING_REVIEW"
            )
            batch.completed_at = datetime.now(timezone.utc)

            sync_applicant_checklist_and_naming(
                db,
                batch.applicant_id,
                naming_convention_override=naming_convention_override,
            )

            applicant = db.scalar(select(Applicant).where(Applicant.id == batch.applicant_id))
            if applicant:
                applicant.status = "AWAITING_REVIEW"
            db.commit()

        return {
            "batch_id": batch_id,
            "processed_files": processed_count,
            "failed_files": failed_count,
            "status": batch.status if batch else "UNKNOWN",
        }
    finally:
        db.close()
