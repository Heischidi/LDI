"""Immutable audit logging service with PII sanitization."""

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import sanitize_log_metadata
from app.models.entities import AuditLog, User


def record_audit_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    actor: User | None = None,
    actor_email: str | None = None,
    actor_role: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Persist an immutable audit log record with sensitive fields masked."""
    ip_address = None
    user_agent = None
    if request is not None:
        ip_address = request.client.host if request.client else None
        user_agent = (request.headers.get("user-agent") or "")[:255]

    resolved_email = actor.email if actor else actor_email
    resolved_role = (
        actor.role.name if (actor and actor.role) else actor_role
    )

    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_email=resolved_email,
        actor_role=resolved_role,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=sanitize_log_metadata(metadata or {}),
    )
    db.add(entry)
    db.flush()
    return entry
