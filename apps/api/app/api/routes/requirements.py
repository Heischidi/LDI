"""Configurable Document Requirements Engine & Document Types/Aliases API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_OFFICER, ROLE_SUPER_ADMIN, ROLE_VIEWER, get_current_user, require_roles
from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    DocumentAlias,
    DocumentClassification,
    DocumentRequirement,
    DocumentType,
    ProcessedDocument,
    RequirementSet,
    RequirementVersion,
    UploadBatch,
    User,
)
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.schemas.requirements import (
    DocumentAliasRead,
    DocumentRequirementItemRead,
    DocumentTypeCreate,
    DocumentTypeRead,
    RequirementSetCreate,
    RequirementSetRead,
    RequirementSetUpdate,
    RequirementVersionRead,
)
from app.services.audit_service import record_audit_event
from app.services.requirements_engine import (
    create_new_requirement_version,
    find_matching_requirement_set,
    get_active_version,
)

router = APIRouter(prefix="/requirements", tags=["Requirements Engine"])


def _serialize_req_set(rs: RequirementSet) -> RequirementSetRead:
    active_ver = get_active_version(rs)
    active_ver_read = None
    if active_ver:
        active_ver_read = RequirementVersionRead(
            id=active_ver.id,
            version_number=active_ver.version_number,
            effective_from=active_ver.effective_from,
            effective_to=active_ver.effective_to,
            change_notes=active_ver.change_notes,
            created_at=active_ver.created_at,
            items=[
                DocumentRequirementItemRead(
                    id=item.id,
                    document_type_id=item.document_type_id,
                    document_type_code=item.document_type.code,
                    document_type_name=item.document_type.name,
                    requirement_level=item.requirement_level,
                    display_order=item.display_order,
                    condition_expression=item.condition_expression,
                    condition_explanation=item.condition_explanation,
                    alternative_doc_type_ids=item.alternative_doc_type_ids or [],
                    allow_multiple_versions=item.allow_multiple_versions,
                    expiry_rule_days=item.expiry_rule_days,
                    min_validity_days=item.min_validity_days,
                    custom_instructions=item.custom_instructions,
                    naming_prefix_override=item.naming_prefix_override,
                )
                for item in sorted(active_ver.items, key=lambda x: x.display_order)
            ],
        )

    return RequirementSetRead(
        id=rs.id,
        name=rs.name,
        destination_id=rs.destination_id,
        destination_name=rs.destination.name if rs.destination else "",
        purpose_id=rs.purpose_id,
        purpose_name=rs.purpose.name if rs.purpose else "",
        category_id=rs.category_id,
        category_name=rs.category.name if rs.category else "",
        applicant_type=rs.applicant_type,
        naming_convention=rs.naming_convention,
        folder_template=rs.folder_template,
        is_active=rs.is_active,
        active_version_id=rs.active_version_id,
        active_version=active_ver_read,
        versions_summary=[
            {
                "id": v.id,
                "version_number": v.version_number,
                "effective_from": v.effective_from,
                "effective_to": v.effective_to,
                "change_notes": v.change_notes,
                "item_count": len(v.items),
            }
            for v in rs.versions
        ],
        created_at=rs.created_at,
        updated_at=rs.updated_at,
    )


@router.get("/document-types", response_model=list[DocumentTypeRead])
def list_document_types(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[DocumentTypeRead]:
    rows = (
        db.scalars(
            select(DocumentType)
            .options(joinedload(DocumentType.aliases))
            .order_by(DocumentType.default_order.asc(), DocumentType.name.asc())
        )
        .unique()
        .all()
    )
    return [DocumentTypeRead.model_validate(r) for r in rows]


@router.post("/document-types", response_model=DocumentTypeRead, status_code=201)
def create_document_type(
    payload: DocumentTypeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> DocumentTypeRead:
    code = payload.code.strip().upper().replace(" ", "_")
    if db.scalar(select(DocumentType).where(DocumentType.code == code)):
        raise HTTPException(status_code=400, detail="Document type code already exists.")

    dt = DocumentType(
        code=code,
        name=payload.name.strip(),
        category=payload.category.strip().upper(),
        default_order=payload.default_order,
        has_expiry=payload.has_expiry,
        min_validity_days=payload.min_validity_days,
        naming_prefix=payload.naming_prefix or payload.name.strip().replace(" ", "_"),
        description=payload.description,
    )
    db.add(dt)
    db.flush()
    for alias in payload.aliases:
        if alias.strip():
            db.add(DocumentAlias(document_type_id=dt.id, alias_name=alias.strip()))

    record_audit_event(
        db,
        action="DOCUMENT_TYPE_CREATED",
        entity_type="document_type",
        entity_id=dt.id,
        actor=current_user,
        metadata={"code": code},
        request=request,
    )
    db.commit()
    db.refresh(dt)
    return DocumentTypeRead.model_validate(dt)


@router.post("/document-types/{document_type_id}/aliases", response_model=DocumentAliasRead, status_code=201)
def add_document_alias(
    document_type_id: str,
    alias_name: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> DocumentAliasRead:
    dt = db.scalar(select(DocumentType).where(DocumentType.id == document_type_id))
    if not dt:
        raise HTTPException(status_code=404, detail="Document type not found.")
    existing = db.scalar(
        select(DocumentAlias).where(
            DocumentAlias.document_type_id == document_type_id,
            DocumentAlias.alias_name.ilike(alias_name.strip()),
        )
    )
    if existing:
        return DocumentAliasRead.model_validate(existing)

    alias = DocumentAlias(document_type_id=document_type_id, alias_name=alias_name.strip())
    db.add(alias)
    record_audit_event(
        db,
        action="DOCUMENT_ALIAS_ADDED",
        entity_type="document_type",
        entity_id=document_type_id,
        actor=current_user,
        metadata={"alias_name": alias_name.strip()},
        request=request,
    )
    db.commit()
    db.refresh(alias)
    return DocumentAliasRead.model_validate(alias)


@router.get("", response_model=list[RequirementSetRead])
def list_requirement_sets(
    destination_id: str | None = None,
    purpose_id: str | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER)),
) -> list[RequirementSetRead]:
    stmt = select(RequirementSet).options(
        joinedload(RequirementSet.destination),
        joinedload(RequirementSet.purpose),
        joinedload(RequirementSet.category),
        joinedload(RequirementSet.versions)
        .joinedload(RequirementVersion.items)
        .joinedload(DocumentRequirement.document_type),
    )
    if destination_id:
        stmt = stmt.where(RequirementSet.destination_id == destination_id)
    if purpose_id:
        stmt = stmt.where(RequirementSet.purpose_id == purpose_id)
    if category_id:
        stmt = stmt.where(RequirementSet.category_id == category_id)

    rows = db.scalars(stmt.order_by(RequirementSet.name.asc())).unique().all()
    return [_serialize_req_set(r) for r in rows]


@router.get("/match", response_model=RequirementSetRead | None)
def match_requirement_set(
    destination_id: str,
    purpose_id: str,
    category_id: str,
    applicant_type: str = "STANDARD",
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> RequirementSetRead | None:
    """Dynamically resolve the active configured checklist for destination + purpose + category."""
    rs = find_matching_requirement_set(
        db,
        destination_id=destination_id,
        purpose_id=purpose_id,
        category_id=category_id,
        applicant_type=applicant_type,
    )
    if not rs:
        return None
    return _serialize_req_set(rs)


@router.post("", response_model=RequirementSetRead, status_code=status.HTTP_201_CREATED)
def create_requirement_set(
    payload: RequirementSetCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> RequirementSetRead:
    rs = RequirementSet(
        name=payload.name.strip(),
        destination_id=payload.destination_id,
        purpose_id=payload.purpose_id,
        category_id=payload.category_id,
        applicant_type=payload.applicant_type,
        naming_convention=payload.naming_convention,
        folder_template=payload.folder_template,
        is_active=True,
    )
    db.add(rs)
    db.flush()

    create_new_requirement_version(
        db,
        req_set=rs,
        items=[item.model_dump() for item in payload.items],
        change_notes=payload.change_notes,
        created_by_id=current_user.id,
    )

    record_audit_event(
        db,
        action="REQUIREMENTS_CREATED",
        entity_type="requirement_set",
        entity_id=rs.id,
        actor=current_user,
        metadata={"name": rs.name, "item_count": len(payload.items)},
        request=request,
    )
    db.commit()

    loaded = db.scalar(
        select(RequirementSet)
        .options(
            joinedload(RequirementSet.destination),
            joinedload(RequirementSet.purpose),
            joinedload(RequirementSet.category),
            joinedload(RequirementSet.versions)
            .joinedload(RequirementVersion.items)
            .joinedload(DocumentRequirement.document_type),
        )
        .where(RequirementSet.id == rs.id)
    )
    return _serialize_req_set(loaded)


def _delete_requirement_set_row(db: Session, rs: RequirementSet) -> None:
    rs.active_version_id = None
    db.flush()
    ver_ids = db.scalars(
        select(RequirementVersion.id).where(RequirementVersion.requirement_set_id == rs.id)
    ).all()
    if ver_ids:
        db.execute(
            update(Applicant)
            .where(Applicant.requirement_version_id.in_(ver_ids))
            .values(requirement_version_id=None)
        )
        db.execute(
            update(UploadBatch)
            .where(UploadBatch.requirement_version_id.in_(ver_ids))
            .values(requirement_version_id=None)
        )
        db.execute(
            delete(ApplicantDocumentStatus).where(
                ApplicantDocumentStatus.requirement_version_id.in_(ver_ids)
            )
        )
        db.execute(
            delete(DocumentRequirement).where(
                DocumentRequirement.requirement_version_id.in_(ver_ids)
            )
        )
        db.execute(delete(RequirementVersion).where(RequirementVersion.id.in_(ver_ids)))
        db.flush()
    db.execute(delete(RequirementSet).where(RequirementSet.id == rs.id))


def _delete_document_type_row(db: Session, dt_id: str) -> None:
    db.execute(
        delete(ApplicantDocumentStatus).where(ApplicantDocumentStatus.document_type_id == dt_id)
    )
    db.execute(delete(DocumentRequirement).where(DocumentRequirement.document_type_id == dt_id))
    db.execute(delete(DocumentAlias).where(DocumentAlias.document_type_id == dt_id))
    db.execute(
        update(DocumentClassification)
        .where(DocumentClassification.document_type_id == dt_id)
        .values(document_type_id=None)
    )
    db.execute(
        update(ProcessedDocument)
        .where(ProcessedDocument.document_type_id == dt_id)
        .values(document_type_id=None)
    )
    db.execute(delete(DocumentType).where(DocumentType.id == dt_id))


@router.post("/document-types/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_document_types(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> BatchDeleteResponse:
    """Delete multiple canonical document types and clean up dependent checklist/alias links."""
    if not payload.ids:
        return BatchDeleteResponse(message="No document types selected.", deleted_count=0, deleted_ids=[])

    rows = db.scalars(select(DocumentType).where(DocumentType.id.in_(payload.ids))).all()
    deleted_ids = [r.id for r in rows]
    for dt_id in deleted_ids:
        _delete_document_type_row(db, dt_id)

    record_audit_event(
        db,
        action="DOCUMENT_TYPES_BATCH_DELETED",
        entity_type="document_type",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "document_type_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} document type(s).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.delete("/document-types/{document_type_id}", response_model=MessageResponse)
def delete_document_type(
    document_type_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> MessageResponse:
    """Delete a single canonical document type."""
    dt = db.scalar(select(DocumentType).where(DocumentType.id == document_type_id))
    if not dt:
        raise HTTPException(status_code=404, detail="Document type not found.")

    name = dt.name
    _delete_document_type_row(db, dt.id)
    record_audit_event(
        db,
        action="DOCUMENT_TYPE_DELETED",
        entity_type="document_type",
        entity_id=document_type_id,
        actor=current_user,
        metadata={"name": name},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Deleted document type {name}.")


@router.post("/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_requirement_sets(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> BatchDeleteResponse:
    """Delete multiple requirement sets and their versions."""
    if not payload.ids:
        return BatchDeleteResponse(message="No requirement sets selected.", deleted_count=0, deleted_ids=[])

    rows = db.scalars(select(RequirementSet).where(RequirementSet.id.in_(payload.ids))).all()
    deleted_ids = [rs.id for rs in rows]
    for rs in rows:
        _delete_requirement_set_row(db, rs)

    record_audit_event(
        db,
        action="REQUIREMENTS_BATCH_DELETED",
        entity_type="requirement_set",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "requirement_set_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} checklist(s).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.delete("/{requirement_set_id}", response_model=MessageResponse)
def delete_requirement_set(
    requirement_set_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> MessageResponse:
    """Delete a single requirement set and its version snapshots."""
    rs = db.scalar(select(RequirementSet).where(RequirementSet.id == requirement_set_id))
    if not rs:
        raise HTTPException(status_code=404, detail="Requirement set not found.")

    name = rs.name
    _delete_requirement_set_row(db, rs)
    record_audit_event(
        db,
        action="REQUIREMENTS_DELETED",
        entity_type="requirement_set",
        entity_id=requirement_set_id,
        actor=current_user,
        metadata={"name": name},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Deleted checklist {name}.")


@router.patch("/{requirement_set_id}", response_model=RequirementSetRead)
def update_requirement_set(
    requirement_set_id: str,
    payload: RequirementSetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> RequirementSetRead:
    """Update a RequirementSet by creating a new RequirementVersion so prior applicants retain their checklist version."""
    rs = db.scalar(
        select(RequirementSet)
        .options(
            joinedload(RequirementSet.destination),
            joinedload(RequirementSet.purpose),
            joinedload(RequirementSet.category),
            joinedload(RequirementSet.versions)
            .joinedload(RequirementVersion.items)
            .joinedload(DocumentRequirement.document_type),
        )
        .where(RequirementSet.id == requirement_set_id)
    )
    if not rs:
        raise HTTPException(status_code=404, detail="Requirement set not found.")

    if payload.name is not None:
        rs.name = payload.name.strip()
    if payload.applicant_type is not None:
        rs.applicant_type = payload.applicant_type
    if payload.naming_convention is not None:
        rs.naming_convention = payload.naming_convention
    if payload.folder_template is not None:
        rs.folder_template = payload.folder_template
    if payload.is_active is not None:
        rs.is_active = payload.is_active

    if payload.items is not None:
        create_new_requirement_version(
            db,
            req_set=rs,
            items=[item.model_dump() for item in payload.items],
            change_notes=payload.change_notes,
            created_by_id=current_user.id,
        )

    record_audit_event(
        db,
        action="REQUIREMENTS_MODIFIED",
        entity_type="requirement_set",
        entity_id=rs.id,
        actor=current_user,
        metadata={"change_notes": payload.change_notes},
        request=request,
    )
    db.commit()

    db.expire_all()
    loaded = db.scalar(
        select(RequirementSet)
        .options(
            joinedload(RequirementSet.destination),
            joinedload(RequirementSet.purpose),
            joinedload(RequirementSet.category),
            joinedload(RequirementSet.versions)
            .joinedload(RequirementVersion.items)
            .joinedload(DocumentRequirement.document_type),
        )
        .where(RequirementSet.id == rs.id)
    )
    return _serialize_req_set(loaded)
