"""Folder organization ZIP exports, PDF processing reports, and signed private downloads."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_OFFICER, ROLE_SUPER_ADMIN, ROLE_VIEWER, ensure_applicant_access, require_roles
from app.core.security import verify_signed_token
from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    ExportPackage,
    UploadedDocument,
    User,
)
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.services.audit_service import record_audit_event
from app.services.checklist_service import sync_applicant_checklist_and_naming
from app.services.export_service import (
    create_applicant_export_package,
    generate_processing_report_pdf,
)
from app.storage.service import get_storage_backend

router = APIRouter(tags=["Exports & Reports"])


@router.post("/applicants/{applicant_id}/export")
def generate_applicant_export(
    applicant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> dict:
    """Build organized folder ZIP (approved documents + ORIGINAL_DOCUMENTS + PROCESSING_REPORT.pdf)."""
    applicant = db.scalar(select(Applicant).where(Applicant.id == applicant_id))
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found.")
    ensure_applicant_access(applicant, current_user)
    try:
        pkg = create_applicant_export_package(db, applicant_id=applicant_id, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    storage = get_storage_backend()
    signed_url = storage.generate_download_url(pkg.zip_storage_key)
    return {
        "export_id": pkg.id,
        "applicant_id": pkg.applicant_id,
        "folder_root": pkg.folder_root,
        "approved_doc_count": pkg.approved_doc_count,
        "missing_doc_count": pkg.missing_doc_count,
        "download_url": f"/api/exports/{pkg.id}/download",
        "signed_download_url": signed_url,
        "manifest": pkg.manifest_json,
        "created_at": pkg.created_at,
    }


@router.get("/applicants/{applicant_id}/report")
def get_applicant_processing_report(
    applicant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> Response:
    """Return live PDF processing report for an applicant."""
    applicant_check = db.scalar(select(Applicant).where(Applicant.id == applicant_id))
    if not applicant_check:
        raise HTTPException(status_code=404, detail="Applicant not found.")
    ensure_applicant_access(applicant_check, current_user)

    sync_applicant_checklist_and_naming(db, applicant_id)
    applicant = db.scalar(
        select(Applicant)
        .options(
            joinedload(Applicant.destination),
            joinedload(Applicant.purpose),
            joinedload(Applicant.category),
            joinedload(Applicant.checklist_statuses).joinedload(ApplicantDocumentStatus.document_type),
            joinedload(Applicant.checklist_statuses).joinedload(ApplicantDocumentStatus.document_requirement),
            joinedload(Applicant.documents).joinedload(UploadedDocument.classifications),
            joinedload(Applicant.documents).joinedload(UploadedDocument.processed_document),
        )
        .where(Applicant.id == applicant_id)
    )
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found.")

    approved_procs = [
        d.processed_document
        for d in applicant.documents
        if d.processed_document and d.processed_document.is_approved_for_export and not d.is_excluded
    ]
    pdf_bytes = generate_processing_report_pdf(
        applicant=applicant,
        checklist_rows=applicant.checklist_statuses,
        approved_docs=approved_procs,
        all_docs=applicant.documents,
        generated_at=datetime.now(timezone.utc),
    )
    db.commit()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="PROCESSING_REPORT_{applicant.application_reference}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/exports/{export_id}/download")
def download_export_zip(
    export_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> Response:
    """Stream organized applicant ZIP package and record FOLDER_DOWNLOADED audit event."""
    pkg = db.scalar(select(ExportPackage).where(ExportPackage.id == export_id))
    if not pkg:
        raise HTTPException(status_code=404, detail="Export package not found.")

    applicant = db.scalar(select(Applicant).where(Applicant.id == pkg.applicant_id))
    if applicant:
        ensure_applicant_access(applicant, current_user)
    storage = get_storage_backend()
    try:
        zip_bytes = storage.get_bytes(pkg.zip_storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Export archive missing from storage.") from exc

    record_audit_event(
        db,
        action="FOLDER_DOWNLOADED",
        entity_type="export_package",
        entity_id=pkg.id,
        actor=current_user,
        metadata={"applicant_id": pkg.applicant_id},
        request=request,
    )
    if applicant and applicant.status == "APPROVED":
        applicant.status = "COMPLETED"
    db.commit()

    ref = applicant.application_reference if applicant else export_id
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{ref}_ORGANISED_DOCUMENTS.zip"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/exports/signed-object")
def download_signed_private_object(
    key: str = Query(...),
    sig: str = Query(...),
    exp: int = Query(...),
) -> Response:
    """Serve private object via short-lived HMAC-signed URL without exposing public bucket paths."""
    if not verify_signed_token(key, sig, exp):
        raise HTTPException(status_code=403, detail="Signed URL is invalid or has expired.")

    storage = get_storage_backend()
    try:
        content = storage.get_bytes(key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Object not found.") from exc

    media_type = "application/zip" if key.endswith(".zip") else "application/pdf"
    filename = key.rsplit("/", 1)[-1]
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/exports/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_exports(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> BatchDeleteResponse:
    """Delete multiple generated export packages and their archive objects."""
    if not payload.ids:
        return BatchDeleteResponse(message="No exports selected.", deleted_count=0, deleted_ids=[])

    pkgs = db.scalars(select(ExportPackage).where(ExportPackage.id.in_(payload.ids))).all()
    storage = get_storage_backend()
    deleted_ids: list[str] = []
    for pkg in pkgs:
        applicant = db.scalar(select(Applicant).where(Applicant.id == pkg.applicant_id))
        if applicant:
            ensure_applicant_access(applicant, current_user)

    for pkg in pkgs:
        for key in (pkg.zip_storage_key, pkg.report_storage_key):
            if key:
                try:
                    storage.delete(key)
                except Exception:
                    pass
        deleted_ids.append(pkg.id)
        db.delete(pkg)

    record_audit_event(
        db,
        action="EXPORTS_BATCH_DELETED",
        entity_type="export_package",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "export_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} export package(s).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.delete("/exports/{export_id}", response_model=MessageResponse)
def delete_export_package(
    export_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> MessageResponse:
    """Delete a single generated export package."""
    pkg = db.scalar(select(ExportPackage).where(ExportPackage.id == export_id))
    if not pkg:
        raise HTTPException(status_code=404, detail="Export package not found.")

    applicant = db.scalar(select(Applicant).where(Applicant.id == pkg.applicant_id))
    if applicant:
        ensure_applicant_access(applicant, current_user)

    storage = get_storage_backend()
    for key in (pkg.zip_storage_key, pkg.report_storage_key):
        if key:
            try:
                storage.delete(key)
            except Exception:
                pass
    db.delete(pkg)
    record_audit_event(
        db,
        action="EXPORT_DELETED",
        entity_type="export_package",
        entity_id=export_id,
        actor=current_user,
        metadata={"applicant_id": pkg.applicant_id},
        request=request,
    )
    db.commit()
    return MessageResponse(message="Deleted export package.")
