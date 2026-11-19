"""Restricted immutable audit log query endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ROLE_ADMIN, ROLE_SUPER_ADMIN, require_roles
from app.models.entities import AuditLog, User
from app.schemas.common import PaginatedResponse
from app.schemas.reports import AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=PaginatedResponse[AuditLogRead])
def list_audit_logs(
    action: str | None = None,
    entity_type: str | None = None,
    actor_email: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
) -> PaginatedResponse[AuditLogRead]:
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
        count_stmt = count_stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)
    if actor_email:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor_email}%"))
        count_stmt = count_stmt.where(AuditLog.actor_email.ilike(f"%{actor_email}%"))

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(desc(AuditLog.created_at)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[
            AuditLogRead(
                id=r.id,
                actor_user_id=r.actor_user_id,
                actor_email=r.actor_email,
                actor_role=r.actor_role,
                action=r.action,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                ip_address=r.ip_address,
                metadata_json=r.metadata_json or {},
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
