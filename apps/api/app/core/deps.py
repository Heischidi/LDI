"""Role-based access control (RBAC) constants and FastAPI authentication dependencies."""

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.entities import Role, User

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_CEO = "CEO"
ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_ADMIN = "ADMIN"
ROLE_OFFICER = "OFFICER"
ROLE_VIEWER = "VIEWER"

PRIVILEGED_ADMIN_ROLES = {ROLE_SUPER_ADMIN, ROLE_CEO}
ALL_ROLES = [ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER]


def is_super_privileged(user: User | None) -> bool:
    """Return True when the user holds Super Admin or CEO full platform privileges."""
    return bool(user and user.role and user.role.name in PRIVILEGED_ADMIN_ROLES)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate current user from Bearer JWT header (or query token for preview/download streams)."""
    token = credentials.credentials if credentials else request.query_params.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.scalar(
        select(User)
        .options(joinedload(User.role).joinedload(Role.permissions))
        .where(User.id == user_id)
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )
    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """Enforce that the authenticated user holds one of the allowed roles."""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        role_name = current_user.role.name if current_user.role else ""
        if role_name in PRIVILEGED_ADMIN_ROLES:
            return current_user
        if role_name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role_name}' is not authorized for this action.",
            )
        return current_user

    return _dependency


def require_permission(permission_code: str) -> Callable[[User], User]:
    """Enforce fine-grained permission checking with SUPER_ADMIN/CEO bypass."""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if is_super_privileged(current_user):
            return current_user
        user_perms = {
            p.code for p in (current_user.role.permissions if current_user.role else [])
        }
        if permission_code not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission_code}",
            )
        return current_user

    return _dependency


def ensure_applicant_access(applicant, current_user: User) -> None:
    """Restrict client records to the assigned officer, Super Administrator, and CEO."""
    if is_super_privileged(current_user):
        return
    if getattr(applicant, "assigned_officer_id", None) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: client details are restricted to the assigned processing officer and Super Administrator.",
        )
