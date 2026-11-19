"""System configuration endpoints (AI provider, OCR provider, naming convention, retention)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_SUPER_ADMIN, require_roles
from app.models.entities import SystemSetting, User
from app.schemas.reports import SystemSettingUpdate
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/settings", tags=["System Settings"])


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
        metadata={"key": setting.key, "value": payload.value_json},
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
