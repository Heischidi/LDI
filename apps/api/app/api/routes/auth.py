"""Authentication, token refresh, logout, and password reset endpoints."""

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import bearer_scheme, get_current_user
from app.core.security import (
    compute_base_username,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    revoke_token,
    verify_password,
)
from app.models.entities import Role, User
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserSummary,
)
from app.schemas.common import MessageResponse
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _to_user_summary(user: User) -> UserSummary:
    role_name = user.role.name if user.role else "VIEWER"
    perms = [p.code for p in user.role.permissions] if user.role else []
    return UserSummary(
        id=user.id,
        username=user.username or compute_base_username(user.first_name, user.last_name),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number,
        role=role_name,
        permissions=perms,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate staff account via username or email with lockout protection."""
    identifier = (payload.username or payload.email).strip().lower()
    user = db.scalar(
        select(User)
        .options(joinedload(User.role).joinedload(Role.permissions))
        .where(
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier,
            )
        )
    )
    now = datetime.now(timezone.utc)

    if not user:
        record_audit_event(
            db,
            action="LOGIN_FAILED",
            entity_type="auth",
            actor_email=payload.email,
            metadata={"reason": "user_not_found"},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact a Super Administrator.",
        )

    if user.locked_until:
        locked_until = (
            user.locked_until.replace(tzinfo=timezone.utc)
            if user.locked_until.tzinfo is None
            else user.locked_until
        )
        if locked_until > now:
            remaining = int((locked_until - now).total_seconds() // 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked due to repeated failed attempts. Try again in {remaining} minute(s).",
            )

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
        record_audit_event(
            db,
            action="LOGIN_FAILED",
            entity_type="user",
            entity_id=user.id,
            actor=user,
            metadata={"failed_attempts": user.failed_login_attempts},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Reset failed counter on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    role_name = user.role.name if user.role else "VIEWER"
    access_token = create_access_token(subject=user.id, role=role_name)
    refresh_token = create_refresh_token(subject=user.id, role=role_name)

    record_audit_event(
        db,
        action="USER_LOGIN",
        entity_type="user",
        entity_id=user.id,
        actor=user,
        request=request,
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_to_user_summary(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Issue a new access & refresh token pair from a valid refresh token."""
    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
            )
        user_id = claims.get("sub")
        old_jti = claims.get("jti")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token."
        ) from exc

    user = db.scalar(
        select(User)
        .options(joinedload(User.role).joinedload(Role.permissions))
        .where(User.id == user_id)
    )
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable."
        )

    if old_jti:
        revoke_token(old_jti)

    role_name = user.role.name if user.role else "VIEWER"
    return TokenResponse(
        access_token=create_access_token(subject=user.id, role=role_name),
        refresh_token=create_refresh_token(subject=user.id, role=role_name),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_to_user_summary(user),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Revoke current access token and record logout audit event."""
    if credentials:
        try:
            claims = decode_token(credentials.credentials)
            if claims.get("jti"):
                revoke_token(claims["jti"])
        except JWTError:
            pass
    record_audit_event(
        db,
        action="USER_LOGOUT",
        entity_type="user",
        entity_id=current_user.id,
        actor=current_user,
        request=request,
    )
    db.commit()
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserSummary)
def get_me(current_user: User = Depends(get_current_user)) -> UserSummary:
    """Return authenticated staff user profile and permissions."""
    return _to_user_summary(current_user)


@router.post("/password-reset/request", response_model=MessageResponse)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Generate a time-limited password reset token (delivery via configured mail provider)."""
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        record_audit_event(
            db,
            action="PASSWORD_RESET_REQUESTED",
            entity_type="user",
            entity_id=user.id,
            actor=user,
            request=request,
        )
        db.commit()
    return MessageResponse(
        message="If the account exists and is active, a password reset instruction has been generated."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Verify reset token and update user password."""
    user = db.scalar(select(User).where(User.password_reset_token == payload.token))
    now = datetime.now(timezone.utc)
    if not user or not user.password_reset_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")

    exp = (
        user.password_reset_expires.replace(tzinfo=timezone.utc)
        if user.password_reset_expires.tzinfo is None
        else user.password_reset_expires
    )
    if exp < now:
        raise HTTPException(status_code=400, detail="Password reset token has expired.")

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    record_audit_event(
        db,
        action="PASSWORD_RESET_COMPLETED",
        entity_type="user",
        entity_id=user.id,
        actor=user,
        request=request,
    )
    db.commit()
    return MessageResponse(message="Password updated successfully.")
