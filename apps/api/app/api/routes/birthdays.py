"""Automated yearly client birthday email endpoints and scheduler."""

import calendar
from datetime import date, datetime, timezone
import html

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import (
    ROLE_ADMIN,
    ROLE_CEO,
    ROLE_OFFICER,
    ROLE_SUPER_ADMIN,
    ensure_applicant_access,
    is_super_privileged,
    require_roles,
)
from app.models.entities import Applicant, ClientBirthday, User
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.services.audit_service import record_audit_event
from app.services.email_service import dispatch_client_email

router = APIRouter(prefix="/birthdays", tags=["Client Birthdays"])


class ClientBirthdayCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    client_email: EmailStr
    birth_date: date
    custom_message: str | None = None
    applicant_id: str | None = None
    is_active: bool = True
    send_if_today: bool = True


class ClientBirthdayUpdate(BaseModel):
    client_name: str | None = Field(default=None, min_length=1, max_length=200)
    client_email: EmailStr | None = None
    birth_date: date | None = None
    custom_message: str | None = None
    is_active: bool | None = None


class ClientBirthdayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    applicant_id: str | None = None
    created_by_id: str | None = None
    client_name: str
    client_email: str
    birth_date: date
    custom_message: str | None = None
    is_active: bool
    last_sent_year: int | None = None
    send_count: int
    last_sent_at: datetime | None = None
    last_delivery_status: str | None = None
    last_delivery_provider: str | None = None
    last_delivery_detail: str | None = None
    next_birthday_date: date
    days_until_birthday: int
    is_birthday_today: bool
    created_at: datetime
    updated_at: datetime


def _today_utc(today_override: date | None = None) -> date:
    return today_override or datetime.now(timezone.utc).date()


def is_birthday_on_date(birth_date: date, today: date) -> bool:
    """Return True if birth_date matches today's month/day (including Feb 29 on Feb 28 in non-leap years)."""
    if (birth_date.month, birth_date.day) == (today.month, today.day):
        return True
    if birth_date.month == 2 and birth_date.day == 29 and not calendar.isleap(today.year):
        return (today.month, today.day) == (2, 28)
    return False


def compute_next_birthday(
    birth_date: date,
    today: date,
    already_sent_this_year: bool,
) -> tuple[date, int]:
    """Compute next upcoming birthday occurrence and days remaining."""

    def _date_for_year(year: int) -> date:
        last_day = calendar.monthrange(year, birth_date.month)[1]
        return date(year, birth_date.month, min(birth_date.day, last_day))

    candidate = _date_for_year(today.year)
    if candidate < today or (candidate == today and already_sent_this_year):
        candidate = _date_for_year(today.year + 1)
    return candidate, (candidate - today).days


def _to_birthday_read(bday: ClientBirthday, today: date) -> ClientBirthdayRead:
    is_today = is_birthday_on_date(bday.birth_date, today)
    already_sent = bday.last_sent_year is not None and bday.last_sent_year >= today.year
    next_bday, days_until = compute_next_birthday(bday.birth_date, today, already_sent)
    return ClientBirthdayRead(
        id=bday.id,
        applicant_id=bday.applicant_id,
        created_by_id=bday.created_by_id,
        client_name=bday.client_name,
        client_email=bday.client_email,
        birth_date=bday.birth_date,
        custom_message=bday.custom_message,
        is_active=bday.is_active,
        last_sent_year=bday.last_sent_year,
        send_count=bday.send_count,
        last_sent_at=bday.last_sent_at,
        last_delivery_status=bday.last_delivery_status,
        last_delivery_provider=bday.last_delivery_provider,
        last_delivery_detail=bday.last_delivery_detail,
        next_birthday_date=next_bday,
        days_until_birthday=days_until,
        is_birthday_today=is_today,
        created_at=bday.created_at,
        updated_at=bday.updated_at,
    )


def _build_birthday_email_bodies(bday: ClientBirthday) -> tuple[str, str]:
    custom = (bday.custom_message or "").strip()
    body_message = (
        custom
        if custom
        else (
            f"Dear {bday.client_name},\n\n"
            "Warmest wishes from everyone at Leaders Edu Tour Ltd on your birthday!\n\n"
            "Thank you for trusting us with your international study and travel journey. "
            "We wish you good health, success, and joy in the year ahead.\n\n"
            "Warm regards,\nThe Leaders Edu Tour Ltd Team"
        )
    )
    formatted_html = "<br>".join(html.escape(line) for line in body_message.splitlines())
    html_body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
  <div style="max-width:580px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:14px;overflow:hidden;">
    <div style="background:#0b1f3a;padding:24px;color:#ffffff;text-align:center;">
      <div style="font-size:11px;color:#6ee7b7;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;">
        Leaders Edu Tour Ltd
      </div>
      <h1 style="margin:8px 0 0;font-size:22px;font-weight:700;">
        Happy Birthday, {html.escape(bday.client_name)}!
      </h1>
    </div>
    <div style="padding:26px 24px;font-size:14px;line-height:1.7;color:#1e293b;">
      <div>{formatted_html}</div>
    </div>
    <div style="background:#f8fafc;padding:12px 24px;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;text-align:center;">
      Leaders Edu Tour Ltd · Automated Annual Client Celebration · Built by <strong>CHIDI AI</strong>
    </div>
  </div>
</body>
</html>"""
    return html_body, body_message


def dispatch_birthday_wish(
    db: Session,
    bday: ClientBirthday,
    *,
    mark_year: bool,
    today_date: date | None = None,
) -> None:
    """Send a client's Happy Birthday email and update delivery tracking."""
    now = datetime.now(timezone.utc)
    today = _today_utc(today_date)
    subject = f"Happy Birthday, {bday.client_name}! — Warm Wishes from Leaders Edu Tour Ltd"
    html_body, plain_text = _build_birthday_email_bodies(bday)
    delivery_status, delivery_provider, delivery_detail = dispatch_client_email(
        db,
        to_email=bday.client_email,
        subject=subject,
        html_body=html_body,
        text_body=plain_text,
    )
    bday.send_count += 1
    bday.last_sent_at = now
    bday.last_delivery_status = delivery_status
    bday.last_delivery_provider = delivery_provider
    bday.last_delivery_detail = delivery_detail
    if mark_year and delivery_status != "FAILED":
        bday.last_sent_year = today.year


def process_due_client_birthdays(db: Session, today_date: date | None = None) -> int:
    """Dispatch yearly birthday emails for active records whose birthday is today and not yet sent this year."""
    today = _today_utc(today_date)
    active_rows = db.scalars(
        select(ClientBirthday).where(ClientBirthday.is_active.is_(True))
    ).all()
    sent = 0
    for bday in active_rows:
        if bday.last_sent_year is not None and bday.last_sent_year >= today.year:
            continue
        if is_birthday_on_date(bday.birth_date, today):
            dispatch_birthday_wish(db, bday, mark_year=True, today_date=today)
            sent += 1
    if sent > 0:
        db.commit()
    return sent


def _ensure_birthday_access(bday: ClientBirthday, current_user: User) -> None:
    if is_super_privileged(current_user) or (current_user.role and current_user.role.name == ROLE_ADMIN):
        return
    if bday.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this birthday record.",
        )


@router.post("/process-due")
def process_due_birthdays_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> dict[str, int]:
    """Check today's date and send any due automated yearly client birthday wishes."""
    processed = process_due_client_birthdays(db)
    return {"processed_count": processed}


@router.post("/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_birthdays(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> BatchDeleteResponse:
    if not payload.ids:
        return BatchDeleteResponse(message="No client birthdays selected.", deleted_count=0, deleted_ids=[])

    rows = db.scalars(select(ClientBirthday).where(ClientBirthday.id.in_(payload.ids))).all()
    deleted_ids: list[str] = []
    for row in rows:
        _ensure_birthday_access(row, current_user)
        deleted_ids.append(row.id)
        db.delete(row)

    record_audit_event(
        db,
        action="CLIENT_BIRTHDAYS_BATCH_DELETED",
        entity_type="client_birthday",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "birthday_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} birthday record(s).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.get("", response_model=list[ClientBirthdayRead])
def list_client_birthdays(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> list[ClientBirthdayRead]:
    """Process any birthdays due today, then return enrolled client birthdays sorted by upcoming date."""
    process_due_client_birthdays(db)
    stmt = select(ClientBirthday)
    if not (is_super_privileged(current_user) or (current_user.role and current_user.role.name == ROLE_ADMIN)):
        stmt = stmt.where(ClientBirthday.created_by_id == current_user.id)
    rows = db.scalars(stmt).all()
    today = _today_utc()
    items = [_to_birthday_read(row, today) for row in rows]
    items.sort(key=lambda item: (not item.is_active, item.days_until_birthday, item.client_name.lower()))
    return items


@router.post("", response_model=ClientBirthdayRead, status_code=status.HTTP_201_CREATED)
def create_client_birthday(
    payload: ClientBirthdayCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> ClientBirthdayRead:
    if payload.applicant_id:
        app = db.scalar(select(Applicant).where(Applicant.id == payload.applicant_id))
        if not app:
            raise HTTPException(status_code=404, detail="Applicant not found.")
        ensure_applicant_access(app, current_user)

    today = _today_utc()
    bday = ClientBirthday(
        applicant_id=payload.applicant_id,
        created_by_id=current_user.id,
        client_name=payload.client_name.strip(),
        client_email=str(payload.client_email).strip().lower(),
        birth_date=payload.birth_date,
        custom_message=payload.custom_message.strip() if payload.custom_message else None,
        is_active=payload.is_active,
        send_count=0,
    )
    db.add(bday)
    db.flush()

    if bday.is_active and payload.send_if_today and is_birthday_on_date(bday.birth_date, today):
        dispatch_birthday_wish(db, bday, mark_year=True, today_date=today)

    record_audit_event(
        db,
        action="CLIENT_BIRTHDAY_CREATED",
        entity_type="client_birthday",
        entity_id=bday.id,
        actor=current_user,
        metadata={
            "client_name": bday.client_name,
            "client_email": bday.client_email,
            "birth_date": bday.birth_date.isoformat(),
        },
        request=request,
    )
    db.commit()
    db.refresh(bday)
    return _to_birthday_read(bday, today)


@router.patch("/{birthday_id}", response_model=ClientBirthdayRead)
def update_client_birthday(
    birthday_id: str,
    payload: ClientBirthdayUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> ClientBirthdayRead:
    bday = db.scalar(select(ClientBirthday).where(ClientBirthday.id == birthday_id))
    if not bday:
        raise HTTPException(status_code=404, detail="Client birthday record not found.")
    _ensure_birthday_access(bday, current_user)

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "client_name" and isinstance(value, str):
            bday.client_name = value.strip()
        elif key == "client_email" and value is not None:
            bday.client_email = str(value).strip().lower()
        elif key == "custom_message":
            bday.custom_message = value.strip() if isinstance(value, str) and value.strip() else None
        else:
            setattr(bday, key, value)

    record_audit_event(
        db,
        action="CLIENT_BIRTHDAY_UPDATED",
        entity_type="client_birthday",
        entity_id=bday.id,
        actor=current_user,
        metadata={"updated_fields": list(updates.keys())},
        request=request,
    )
    db.commit()
    db.refresh(bday)
    return _to_birthday_read(bday, _today_utc())


@router.post("/{birthday_id}/send-now", response_model=ClientBirthdayRead)
def send_birthday_now(
    birthday_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> ClientBirthdayRead:
    bday = db.scalar(select(ClientBirthday).where(ClientBirthday.id == birthday_id))
    if not bday:
        raise HTTPException(status_code=404, detail="Client birthday record not found.")
    _ensure_birthday_access(bday, current_user)

    today = _today_utc()
    dispatch_birthday_wish(
        db,
        bday,
        mark_year=is_birthday_on_date(bday.birth_date, today),
        today_date=today,
    )
    record_audit_event(
        db,
        action="CLIENT_BIRTHDAY_SENT_NOW",
        entity_type="client_birthday",
        entity_id=bday.id,
        actor=current_user,
        metadata={
            "client_email": bday.client_email,
            "delivery_status": bday.last_delivery_status,
            "send_count": bday.send_count,
        },
        request=request,
    )
    db.commit()
    db.refresh(bday)
    return _to_birthday_read(bday, today)


@router.delete("/{birthday_id}", response_model=MessageResponse)
def delete_client_birthday(
    birthday_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> MessageResponse:
    bday = db.scalar(select(ClientBirthday).where(ClientBirthday.id == birthday_id))
    if not bday:
        raise HTTPException(status_code=404, detail="Client birthday record not found.")
    _ensure_birthday_access(bday, current_user)

    name = bday.client_name
    db.delete(bday)
    record_audit_event(
        db,
        action="CLIENT_BIRTHDAY_DELETED",
        entity_type="client_birthday",
        entity_id=birthday_id,
        actor=current_user,
        metadata={"client_name": name},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Deleted birthday automation for {name}.")
