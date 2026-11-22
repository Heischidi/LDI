"""System configuration endpoints (AI provider, OCR provider, naming convention, retention)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_SUPER_ADMIN, require_roles
from app.models.entities import SystemSetting, User
from app.schemas.reports import SystemSettingUpdate
from app.services.audit_service import record_audit_event
from app.services.email_service import dispatch_client_email

router = APIRouter(prefix="/settings", tags=["System Settings"])


class TestEmailRequest(BaseModel):
    to_email: EmailStr


def _redact_sensitive(value: dict) -> dict:
    redacted: dict = {}
    for k, v in value.items():
        lk = str(k).lower()
        if any(word in lk for word in ("pass", "key", "secret", "token")) and v:
            redacted[k] = "***REDACTED***"
        else:
            redacted[k] = v
    return redacted


@router.get("")
def list_settings(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> list[dict]:
    rows = db.scalars(select(SystemSetting).order_by(SystemSetting.category, SystemSetting.key)).all()
    return [
        {
            "id": r.id,
            "key": r.key,
            "value_json": r.value_json,
            "category": r.category,
            "description": r.description,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


@router.post("/test-email")
def send_test_email(
    payload: TestEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN)),
) -> dict:
    """Dispatch a single test email using the active Settings -> notifications.email config."""
    status_val, provider_val, detail_val = dispatch_client_email(
        db,
        to_email=str(payload.to_email),
        subject="Leaders Edu Tour LDI — Email Delivery Test",
        html_body=(
            "<div style='font-family:Arial,sans-serif;padding:20px;background:#f8fafc;'>"
            "<div style='max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;"
            "border-radius:10px;padding:20px;'>"
            "<h2 style='margin:0 0 8px;color:#0b1f3a;'>Leaders Edu Tour Ltd — LDI</h2>"
            "<p style='margin:0;color:#334155;font-size:14px;'>"
            "Your live email delivery configuration is working! Both <strong>CEO twice-daily reminders</strong> "
            "and <strong>client live status update emails</strong> will use this provider.</p>"
            "</div></div>"
        ),
        text_body=(
            "Leaders Edu Tour Ltd — LDI Email Delivery Test\n\n"
            "Your live email delivery configuration is working! Both CEO twice-daily reminders "
            "and client live status update emails will use this provider."
        ),
    )
    record_audit_event(
        db,
        action="EMAIL_DELIVERY_TESTED",
        entity_type="system_setting",
        entity_id="notifications.email",
        actor=current_user,
        metadata={
            "to_email": str(payload.to_email),
            "delivery_status": status_val,
            "delivery_provider": provider_val,
        },
        request=request,
    )
    db.commit()
    return {
        "recipient_email": str(payload.to_email),
        "delivery_status": status_val,
        "delivery_provider": provider_val,
        "delivery_detail": detail_val,
    }


@router.patch("/{setting_key}")
def update_setting(
    setting_key: str,
    payload: SystemSettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_SUPER_ADMIN)),
) -> dict:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == setting_key))
    if not setting:
        setting = SystemSetting(
            key=setting_key,
            value_json=payload.value_json,
            category="GENERAL",
            description=payload.description,
            updated_by_id=current_user.id,
        )
        db.add(setting)
    else:
        setting.value_json = payload.value_json
        if payload.description is not None:
            setting.description = payload.description
        setting.updated_by_id = current_user.id

    record_audit_event(
        db,
        action="SYSTEM_SETTING_UPDATED",
        entity_type="system_setting",
        entity_id=setting.key,
        actor=current_user,
        metadata={"key": setting.key, "value": _redact_sensitive(payload.value_json)},
        request=request,
    )
    db.commit()
    db.refresh(setting)
    return {
        "id": setting.id,
        "key": setting.key,
        "value_json": setting.value_json,
        "category": setting.category,
        "description": setting.description,
        "updated_at": setting.updated_at,
    }
