"""Staff user management endpoints with strict RBAC."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.routes.auth import _to_user_summary
from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_SUPER_ADMIN, require_roles
from app.core.security import hash_password
from app.models.entities import Role, User
from app.schemas.auth import UserCreateRequest, UserSummary, UserUpdateRequest
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
    if payload.first_name is not None or payload.last_name is not None or not user.username:
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
