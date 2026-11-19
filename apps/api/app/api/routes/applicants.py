"""Applicant management & travel reference metadata endpoints."""

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_OFFICER, ROLE_SUPER_ADMIN, ROLE_VIEWER, get_current_user, require_roles
from app.core.security import decrypt_sensitive_value, encrypt_sensitive_value
from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    ApplicationCategory,
    Destination,
    DocumentRequirement,
    ExportPackage,
    TravelPurpose,
    UploadBatch,
    UploadedDocument,
    User,
)
from app.schemas.applicants import (
    ApplicantCreate,
    ApplicantDetail,
    ApplicantSummary,
    ApplicantUpdate,
    ApplicationCategoryCreate,
    ApplicationCategoryRead,
    ApplicationCategoryUpdate,
    ChecklistStatusItem,
    DestinationCreate,
    DestinationRead,
    OfficerBrief,
    TravelPurposeCreate,
    TravelPurposeRead,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.audit_service import record_audit_event
from app.services.checklist_service import sync_applicant_checklist_and_naming
from app.services.requirements_engine import find_matching_requirement_set, get_active_version

router = APIRouter(tags=["Applicants & Travel Reference"])


def _generate_app_reference(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    for _ in range(10):
        suffix = secrets.token_hex(2).upper() + str(secrets.randbelow(90) + 10)
        ref = f"LDI-{year}-{suffix}"
        if not db.scalar(select(Applicant.id).where(Applicant.application_reference == ref)):
            return ref
    return f"LDI-{year}-{secrets.token_hex(4).upper()}"


def _mask_passport(encrypted_val: str | None) -> str | None:
    if not encrypted_val:
        return None
    try:
        plain = decrypt_sensitive_value(encrypted_val)
    except Exception:
        plain = encrypted_val
    if len(plain) <= 4:
        return "****"
    return f"{plain[:2]}{'*' * (len(plain) - 4)}{plain[-2:]}"


def _serialize_applicant_summary(app: Applicant) -> ApplicantSummary:
    full_name = " ".join(p for p in [app.first_name, app.middle_name, app.last_name] if p)
    missing_req = sum(1 for c in app.checklist_statuses if c.status == "MISSING")
    pending_rev = sum(
        1
        for d in app.documents
        if not d.is_excluded
        and any(c.is_current and c.status in {"PENDING_REVIEW", "MANUAL_REQUIRED", "AUTO_PREPARED"} for c in d.classifications)
    )
    return ApplicantSummary(
        id=app.id,
        application_reference=app.application_reference,
        first_name=app.first_name,
        middle_name=app.middle_name,
        last_name=app.last_name,
        full_name=full_name,
        email=app.email,
        phone_number=app.phone_number,
        date_of_birth=app.date_of_birth,
        nationality=app.nationality,
        applicant_type=app.applicant_type,
        destination=DestinationRead.model_validate(app.destination),
        purpose=TravelPurposeRead.model_validate(app.purpose),
        category=ApplicationCategoryRead.model_validate(app.category),
        assigned_officer=OfficerBrief(
            id=app.assigned_officer.id,
            first_name=app.assigned_officer.first_name,
            last_name=app.assigned_officer.last_name,
            email=app.assigned_officer.email,
        )
        if app.assigned_officer
        else None,
        requirement_version_id=app.requirement_version_id,
        status=app.status,
        is_archived=app.is_archived,
        document_count=len(app.documents),
        missing_required_count=missing_req,
        pending_review_count=pending_rev,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


# ---------------------------------------------------------------------------
# Travel Reference Metadata (Destinations, Purposes, Application Categories)
# ---------------------------------------------------------------------------

@router.get("/reference/destinations", response_model=list[DestinationRead])
def list_destinations(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[DestinationRead]:
    rows = db.scalars(select(Destination).order_by(Destination.name.asc())).all()
    return [DestinationRead.model_validate(r) for r in rows]


@router.post("/reference/destinations", response_model=DestinationRead, status_code=201)
def create_destination(
    payload: DestinationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> DestinationRead:
    if db.scalar(select(Destination).where(Destination.code == payload.code.upper())):
        raise HTTPException(status_code=400, detail="Destination code already exists.")
    dest = Destination(name=payload.name.strip(), code=payload.code.strip().upper(), region=payload.region)
    db.add(dest)
    record_audit_event(db, action="DESTINATION_CREATED", entity_type="destination", actor=current_user, metadata={"code": dest.code}, request=request)
    db.commit()
    db.refresh(dest)
    return DestinationRead.model_validate(dest)


@router.get("/reference/purposes", response_model=list[TravelPurposeRead])
def list_purposes(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[TravelPurposeRead]:
    rows = db.scalars(select(TravelPurpose).order_by(TravelPurpose.name.asc())).all()
    return [TravelPurposeRead.model_validate(r) for r in rows]


@router.post("/reference/purposes", response_model=TravelPurposeRead, status_code=201)
def create_purpose(
    payload: TravelPurposeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> TravelPurposeRead:
    if db.scalar(select(TravelPurpose).where(TravelPurpose.code == payload.code.upper())):
        raise HTTPException(status_code=400, detail="Travel purpose code already exists.")
    purp = TravelPurpose(name=payload.name.strip(), code=payload.code.strip().upper(), description=payload.description)
    db.add(purp)
    record_audit_event(db, action="TRAVEL_PURPOSE_CREATED", entity_type="travel_purpose", actor=current_user, metadata={"code": purp.code}, request=request)
    db.commit()
    db.refresh(purp)
    return TravelPurposeRead.model_validate(purp)


@router.get("/reference/categories", response_model=list[ApplicationCategoryRead])
def list_categories(
    include_archived: bool = False,
    search: str | None = None,
    destination_id: str | None = None,
    purpose_id: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ApplicationCategoryRead]:
    stmt = select(ApplicationCategory)
    if not include_archived:
        stmt = stmt.where(ApplicationCategory.is_archived.is_(False))
    if search:
        stmt = stmt.where(ApplicationCategory.name.ilike(f"%{search}%"))
    if destination_id:
        stmt = stmt.where(
            or_(ApplicationCategory.destination_id == destination_id, ApplicationCategory.destination_id.is_(None))
        )
    if purpose_id:
        stmt = stmt.where(
            or_(ApplicationCategory.purpose_id == purpose_id, ApplicationCategory.purpose_id.is_(None))
        )
    rows = db.scalars(stmt.order_by(ApplicationCategory.name.asc())).all()
    return [ApplicationCategoryRead.model_validate(r) for r in rows]


@router.post("/reference/categories", response_model=ApplicationCategoryRead, status_code=201)
def create_category(
    payload: ApplicationCategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> ApplicationCategoryRead:
    if db.scalar(select(ApplicationCategory).where(ApplicationCategory.code == payload.code.upper())):
        raise HTTPException(status_code=400, detail="Application category code already exists.")
    cat = ApplicationCategory(
        name=payload.name.strip(),
        code=payload.code.strip().upper(),
        destination_id=payload.destination_id,
        purpose_id=payload.purpose_id,
        description=payload.description,
    )
    db.add(cat)
    record_audit_event(db, action="CATEGORY_CREATED", entity_type="application_category", actor=current_user, metadata={"code": cat.code}, request=request)
    db.commit()
    db.refresh(cat)
    return ApplicationCategoryRead.model_validate(cat)


@router.patch("/reference/categories/{category_id}", response_model=ApplicationCategoryRead)
def update_category(
    category_id: str,
    payload: ApplicationCategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> ApplicationCategoryRead:
    cat = db.scalar(select(ApplicationCategory).where(ApplicationCategory.id == category_id))
    if not cat:
        raise HTTPException(status_code=404, detail="Application category not found.")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, val)
    record_audit_event(db, action="CATEGORY_UPDATED", entity_type="application_category", entity_id=cat.id, actor=current_user, request=request)
    db.commit()
    db.refresh(cat)
    return ApplicationCategoryRead.model_validate(cat)


# ---------------------------------------------------------------------------
# Applicants CRUD
# ---------------------------------------------------------------------------

@router.get("/applicants", response_model=PaginatedResponse[ApplicantSummary])
def list_applicants(
    search: str | None = None,
    destination_id: str | None = None,
    purpose_id: str | None = None,
    category_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_officer_id: str | None = None,
    include_archived: bool = False,
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> PaginatedResponse[ApplicantSummary]:
    stmt = (
        select(Applicant)
        .options(
            joinedload(Applicant.destination),
            joinedload(Applicant.purpose),
            joinedload(Applicant.category),
            joinedload(Applicant.assigned_officer),
            joinedload(Applicant.checklist_statuses),
            joinedload(Applicant.documents).joinedload(UploadedDocument.classifications),
        )
    )
    count_stmt = select(func.count(Applicant.id))

    filters = []
    if not include_archived:
        filters.append(Applicant.is_archived.is_(False))
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Applicant.first_name.ilike(term),
                Applicant.last_name.ilike(term),
                Applicant.email.ilike(term),
                Applicant.application_reference.ilike(term),
            )
        )
    if destination_id:
        filters.append(Applicant.destination_id == destination_id)
    if purpose_id:
        filters.append(Applicant.purpose_id == purpose_id)
    if category_id:
        filters.append(Applicant.category_id == category_id)
    if status_filter:
        filters.append(Applicant.status == status_filter)
    if assigned_officer_id:
        filters.append(Applicant.assigned_officer_id == assigned_officer_id)

    for flt in filters:
        stmt = stmt.where(flt)
        count_stmt = count_stmt.where(flt)

    total = db.scalar(count_stmt) or 0
    order_col = asc(Applicant.created_at) if sort_order == "asc" else desc(Applicant.created_at)
    rows = (
        db.scalars(stmt.order_by(order_col).offset((page - 1) * page_size).limit(page_size))
        .unique()
        .all()
    )
    return PaginatedResponse(
        items=[_serialize_applicant_summary(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/applicants", response_model=ApplicantDetail, status_code=status.HTTP_201_CREATED)
def create_applicant(
    payload: ApplicantCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> ApplicantDetail:
    """Create a new applicant record, pin active checklist version, and initialize requirements status."""
    dest = db.scalar(select(Destination).where(Destination.id == payload.destination_id))
    purpose = db.scalar(select(TravelPurpose).where(TravelPurpose.id == payload.purpose_id))
    cat = db.scalar(select(ApplicationCategory).where(ApplicationCategory.id == payload.category_id))
    if not dest or not purpose or not cat:
        raise HTTPException(status_code=400, detail="Invalid destination, purpose, or category ID.")

    req_set = find_matching_requirement_set(
        db,
        destination_id=dest.id,
        purpose_id=purpose.id,
        category_id=cat.id,
        applicant_type=payload.applicant_type,
    )
    active_ver = get_active_version(req_set)

    encrypted_passport = (
        encrypt_sensitive_value(payload.passport_number.strip())
        if payload.passport_number
        else None
    )

    applicant = Applicant(
        application_reference=_generate_app_reference(db),
        first_name=payload.first_name.strip(),
        middle_name=payload.middle_name.strip() if payload.middle_name else None,
        last_name=payload.last_name.strip(),
        email=payload.email.lower().strip(),
        phone_number=payload.phone_number.strip(),
        date_of_birth=payload.date_of_birth,
        nationality=payload.nationality.strip(),
        passport_number=encrypted_passport,
        applicant_type=payload.applicant_type,
        eligibility_context=payload.eligibility_context,
        destination_id=dest.id,
        purpose_id=purpose.id,
        category_id=cat.id,
        assigned_officer_id=payload.assigned_officer_id or current_user.id,
        requirement_version_id=active_ver.id if active_ver else None,
        status="DRAFT",
    )
    db.add(applicant)
    db.flush()

    sync_applicant_checklist_and_naming(db, applicant.id)

    record_audit_event(
        db,
        action="APPLICANT_CREATED",
        entity_type="applicant",
        entity_id=applicant.id,
        actor=current_user,
        metadata={
            "application_reference": applicant.application_reference,
            "destination": dest.name,
            "purpose": purpose.name,
            "category": cat.name,
        },
        request=request,
    )
    db.commit()
    return get_applicant_detail(applicant.id, db=db, _user=current_user)


@router.get("/applicants/{applicant_id}", response_model=ApplicantDetail)
def get_applicant_detail(
    applicant_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> ApplicantDetail:
    app = db.scalar(
        select(Applicant)
        .options(
            joinedload(Applicant.destination),
            joinedload(Applicant.purpose),
            joinedload(Applicant.category),
            joinedload(Applicant.assigned_officer),
            joinedload(Applicant.checklist_statuses).joinedload(ApplicantDocumentStatus.document_type),
            joinedload(Applicant.checklist_statuses).joinedload(ApplicantDocumentStatus.document_requirement),
            joinedload(Applicant.documents).joinedload(UploadedDocument.classifications),
            joinedload(Applicant.documents).joinedload(UploadedDocument.extracted_data),
            joinedload(Applicant.documents).joinedload(UploadedDocument.processed_document),
            joinedload(Applicant.batches),
        )
        .where(Applicant.id == applicant_id)
    )
    if not app:
        raise HTTPException(status_code=404, detail="Applicant not found.")

    summary = _serialize_applicant_summary(app)
    doc_lookup = {d.id: d for d in app.documents}

    checklist_items: list[ChecklistStatusItem] = []
    for row in sorted(app.checklist_statuses, key=lambda r: r.document_requirement.display_order):
        matched = doc_lookup.get(row.matched_document_id) if row.matched_document_id else None
        checklist_items.append(
            ChecklistStatusItem(
                id=row.id,
                document_requirement_id=row.document_requirement_id,
                document_type_id=row.document_type_id,
                document_type_code=row.document_type.code,
                document_type_name=row.document_type.name,
                requirement_level=row.document_requirement.requirement_level,
                display_order=row.document_requirement.display_order,
                status=row.status,
                verification_stage=row.verification_stage,
                matched_document_id=row.matched_document_id,
                matched_filename=matched.original_filename if matched else None,
                generated_filename=(
                    matched.processed_document.generated_filename
                    if matched and matched.processed_document
                    else None
                ),
                condition_explanation=row.document_requirement.condition_explanation,
                custom_instructions=row.document_requirement.custom_instructions,
                alternative_doc_type_codes=row.document_requirement.alternative_doc_type_ids or [],
                quality_issues=row.quality_issues or [],
            )
        )

    docs_serialized = []
    for d in sorted(app.documents, key=lambda x: x.created_at):
        cls = next((c for c in d.classifications if c.is_current), None)
        docs_serialized.append(
            {
                "id": d.id,
                "batch_id": d.batch_id,
                "original_filename": d.original_filename,
                "source_archive_name": d.source_archive_name,
                "file_extension": d.file_extension,
                "detected_mime_type": d.detected_mime_type,
                "file_size_bytes": d.file_size_bytes,
                "sha256_hash": d.sha256_hash,
                "ingestion_type": d.ingestion_type,
                "page_count": d.page_count,
                "processing_status": d.processing_status,
                "is_excluded": d.is_excluded,
                "is_duplicate": d.is_duplicate,
                "duplicate_of_id": d.duplicate_of_id,
                "duplicate_reason": d.duplicate_reason,
                "error_message": d.error_message,
                "proposed_filename": d.processed_document.generated_filename if d.processed_document else None,
                "is_approved_for_export": d.processed_document.is_approved_for_export if d.processed_document else False,
                "preview_url": f"/api/documents/{d.id}/preview",
                "extracted_text_preview": (d.extracted_data.raw_text[:400] if d.extracted_data else ""),
                "extraction_method": d.extracted_data.extraction_method if d.extracted_data else None,
                "classification": {
                    "id": cls.id,
                    "predicted_type_code": cls.predicted_type_code,
                    "confidence": cls.confidence,
                    "confidence_tier": cls.confidence_tier,
                    "extracted_applicant_name": cls.extracted_applicant_name,
                    "has_name_mismatch": cls.has_name_mismatch,
                    "document_number": cls.document_number,
                    "issuing_authority": cls.issuing_authority,
                    "issue_date": cls.issue_date,
                    "expiry_date": cls.expiry_date,
                    "is_expired": cls.is_expired,
                    "is_readable": cls.is_readable,
                    "possible_issues": cls.possible_issues,
                    "classification_reason": cls.classification_reason,
                    "status": cls.status,
                }
                if cls
                else None,
            }
        )

    exports = db.scalars(
        select(ExportPackage)
        .where(ExportPackage.applicant_id == app.id)
        .order_by(ExportPackage.created_at.desc())
    ).all()

    return ApplicantDetail(
        **summary.model_dump(),
        passport_number_masked=_mask_passport(app.passport_number),
        eligibility_context=app.eligibility_context or {},
        checklist=checklist_items,
        documents=docs_serialized,
        batches=[
            {
                "id": b.id,
                "status": b.status,
                "total_files": b.total_files,
                "processed_files": b.processed_files,
                "failed_files": b.failed_files,
                "created_at": b.created_at,
                "completed_at": b.completed_at,
            }
            for b in sorted(app.batches, key=lambda x: x.created_at, reverse=True)
        ],
        exports=[
            {
                "id": e.id,
                "folder_root": e.folder_root,
                "approved_doc_count": e.approved_doc_count,
                "missing_doc_count": e.missing_doc_count,
                "download_url": f"/api/exports/{e.id}/download",
                "created_at": e.created_at,
            }
            for e in exports
        ],
    )


@router.patch("/applicants/{applicant_id}", response_model=ApplicantDetail)
def update_applicant(
    applicant_id: str,
    payload: ApplicantUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> ApplicantDetail:
    app = db.scalar(select(Applicant).where(Applicant.id == applicant_id))
    if not app:
        raise HTTPException(status_code=404, detail="Applicant not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "passport_number" in updates:
        val = updates.pop("passport_number")
        app.passport_number = encrypt_sensitive_value(val.strip()) if val else None

    for k, v in updates.items():
        setattr(app, k, v)

    sync_applicant_checklist_and_naming(db, app.id)
    record_audit_event(
        db,
        action="APPLICANT_UPDATED",
        entity_type="applicant",
        entity_id=app.id,
        actor=current_user,
        metadata={"updated_fields": list(updates.keys())},
        request=request,
    )
    db.commit()
    return get_applicant_detail(app.id, db=db, _user=current_user)


@router.delete("/applicants/{applicant_id}", response_model=MessageResponse)
def archive_applicant(
    applicant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> MessageResponse:
    """Soft-archive an applicant record without destroying audit trail."""
    app = db.scalar(select(Applicant).where(Applicant.id == applicant_id))
    if not app:
        raise HTTPException(status_code=404, detail="Applicant not found.")

    app.is_archived = True
    app.status = "ARCHIVED"
    app.archived_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        action="APPLICANT_ARCHIVED",
        entity_type="applicant",
        entity_id=app.id,
        actor=current_user,
        metadata={"application_reference": app.application_reference},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Applicant {app.application_reference} archived.")
