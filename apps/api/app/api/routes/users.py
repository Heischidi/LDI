"""Staff user management endpoints with strict RBAC."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, joinedload

from app.api.routes.auth import _to_user_summary
from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_SUPER_ADMIN, require_roles
from app.core.security import hash_password
from app.models.entities import (
    Applicant,
    AuditLog,
    ClientStageUpdate,
    DocumentReview,
    ExportPackage,
    PersonalReminder,
    RequirementVersion,
    Role,
    StatementOfPurpose,
    SystemSetting,
    UploadBatch,
    UploadedDocument,
    User,
)
from app.schemas.auth import UserCreateRequest, UserSummary, UserUpdateRequest
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.services.audit_service import record_audit_event
from app.services.seed_service import generate_unique_username

router = APIRouter(prefix="/users", tags=["Staff Management"])


@router.get("", response_model=list[UserSummary])
def list_users(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> list[UserSummary]:
    rows = (
        db.scalars(
            select(User)
            .options(joinedload(User.role).joinedload(Role.permissions))
            .order_by(User.created_at.desc())
        )
        .unique()
        .all()
    )
    return [_to_user_summary(u) for u in rows]


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_staff_user(
    payload: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN)),
) -> UserSummary:
    username = (
        payload.username.strip().lower()
        if payload.username and payload.username.strip()
        else generate_unique_username(db, payload.first_name, payload.last_name)
    )
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=400, detail="Username is already taken.")

    email_val = (
        payload.email.lower().strip()
        if payload.email and payload.email.strip()
        else f"{username}@leaders.edu"
    )
    if db.scalar(select(User).where(User.email == email_val)):
        raise HTTPException(status_code=400, detail="Email address is already registered.")
    role = db.scalar(
        select(Role)
        .options(joinedload(Role.permissions))
        .where(Role.name == payload.role_name)
    )
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role specified.")

    user = User(
        username=username,
        email=email_val,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone_number=payload.phone_number,
        role_id=role.id,
        is_active=payload.is_active,
    )
    db.add(user)
    db.flush()
    record_audit_event(
        db,
        action="STAFF_ACCOUNT_CREATED",
        entity_type="user",
        entity_id=user.id,
        actor=current_user,
        metadata={"username": user.username, "email": user.email, "role": role.name},
        request=request,
    )
    db.commit()
    loaded = db.scalar(
        select(User)
        .options(joinedload(User.role).joinedload(Role.permissions))
        .where(User.id == user.id)
    )
    return _to_user_summary(loaded)


@router.patch("/{user_id}", response_model=UserSummary)
def update_staff_user(
    user_id: str,
    payload: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN)),
) -> UserSummary:
    user = db.scalar(
        select(User)
        .options(joinedload(User.role).joinedload(Role.permissions))
        .where(User.id == user_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="Staff account not found.")

    if payload.first_name is not None:
        user.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        user.last_name = payload.last_name.strip()
    if payload.email is not None:
        new_email = payload.email.strip().lower()
        if new_email != user.email:
            if db.scalar(select(User).where(User.email == new_email, User.id != user.id)):
                raise HTTPException(status_code=400, detail="Email address is already registered.")
            user.email = new_email
    if payload.username is not None and payload.username.strip():
        new_uname = payload.username.strip().lower()
        if db.scalar(select(User).where(User.username == new_uname, User.id != user.id)):
            raise HTTPException(status_code=400, detail="Username is already taken.")
        user.username = new_uname
    elif payload.first_name is not None or payload.last_name is not None or not user.username:
        user.username = generate_unique_username(
            db, user.first_name, user.last_name, exclude_user_id=user.id
        )
    if payload.phone_number is not None:
        user.phone_number = payload.phone_number
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.role_name:
        role = db.scalar(select(Role).where(Role.name == payload.role_name))
        if not role:
            raise HTTPException(status_code=400, detail="Invalid role specified.")
        user.role_id = role.id

    record_audit_event(
        db,
        action="STAFF_PERMISSIONS_CHANGED",
        entity_type="user",
        entity_id=user.id,
        actor=current_user,
        metadata={"updated": list(payload.model_dump(exclude_unset=True, exclude={"password"}).keys())},
        request=request,
    )
    db.commit()
    db.expire_all()
    loaded = db.scalar(
        select(User)
        .options(joinedload(User.role).joinedload(Role.permissions))
        .where(User.id == user.id)
    )
    return _to_user_summary(loaded)


def _unlink_user_references(db: Session, user_ids: list[str]) -> None:
    if not user_ids:
        return
    db.execute(
        update(Applicant)
        .where(Applicant.assigned_officer_id.in_(user_ids))
        .values(assigned_officer_id=None)
    )
    db.execute(
        update(UploadBatch)
        .where(UploadBatch.uploaded_by_id.in_(user_ids))
        .values(uploaded_by_id=None)
    )
    db.execute(
        update(UploadedDocument)
        .where(UploadedDocument.uploaded_by_id.in_(user_ids))
        .values(uploaded_by_id=None)
    )
    db.execute(
        update(ExportPackage)
        .where(ExportPackage.generated_by_id.in_(user_ids))
        .values(generated_by_id=None)
    )
    db.execute(
        update(AuditLog)
        .where(AuditLog.actor_user_id.in_(user_ids))
        .values(actor_user_id=None)
    )
    db.execute(
        update(ClientStageUpdate)
        .where(ClientStageUpdate.sent_by_id.in_(user_ids))
        .values(sent_by_id=None)
    )
    db.execute(
        update(DocumentReview)
        .where(DocumentReview.reviewed_by_id.in_(user_ids))
        .values(reviewed_by_id=None)
    )
    db.execute(
        update(RequirementVersion)
        .where(RequirementVersion.created_by_id.in_(user_ids))
        .values(created_by_id=None)
    )
    db.execute(
        update(SystemSetting)
        .where(SystemSetting.updated_by_id.in_(user_ids))
        .values(updated_by_id=None)
    )
    db.execute(
        update(StatementOfPurpose)
        .where(StatementOfPurpose.created_by_id.in_(user_ids))
        .values(created_by_id=None)
    )
    db.execute(delete(PersonalReminder).where(PersonalReminder.user_id.in_(user_ids)))
    db.flush()


@router.post("/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_staff_users(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN)),
) -> BatchDeleteResponse:
    """Delete multiple staff accounts at once (Super Admin cannot delete themselves)."""
    if not payload.ids:
        return BatchDeleteResponse(message="No staff accounts selected.", deleted_count=0, deleted_ids=[])
    if current_user.id in payload.ids:
        raise HTTPException(
            status_code=400, detail="Cannot delete your own active Super Admin account."
        )

    users = db.scalars(select(User).where(User.id.in_(payload.ids))).all()
    deleted_ids = [u.id for u in users]
    _unlink_user_references(db, deleted_ids)
    for u in users:
        db.delete(u)

    record_audit_event(
        db,
        action="STAFF_ACCOUNTS_BATCH_DELETED",
        entity_type="user",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "user_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} staff account(s).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_staff_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN)),
) -> MessageResponse:
    """Delete a staff user account while preserving applicants and audit trails."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Cannot delete your own active Super Admin account."
        )

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="Staff account not found.")

    label = user.username or user.email
    _unlink_user_references(db, [user.id])
    db.delete(user)
    record_audit_event(
        db,
        action="STAFF_ACCOUNT_DELETED",
        entity_type="user",
        entity_id=user_id,
        actor=current_user,
        metadata={"username": user.username, "email": user.email},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Deleted staff account {label}.")
