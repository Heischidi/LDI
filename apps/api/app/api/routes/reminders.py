"""Personal & CEO twice-daily email reminder endpoints and scheduler."""

from datetime import datetime, time, timedelta, timezone
import html

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, is_super_privileged
from app.models.entities import PersonalReminder, User
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.services.audit_service import record_audit_event
from app.services.email_service import dispatch_client_email

router = APIRouter(prefix="/reminders", tags=["Personal & CEO Reminders"])


class PersonalReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    recipient_email: EmailStr | None = None
    morning_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    evening_time: str = Field(default="17:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    send_immediately: bool = True


class PersonalReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    recipient_email: EmailStr | None = None
    morning_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    evening_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    is_completed: bool | None = None


class PersonalReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    notes: str | None = None
    recipient_email: str
    times_per_day: int
    morning_time: str
    evening_time: str
    is_completed: bool
    completed_at: datetime | None = None
    send_count: int
    last_sent_at: datetime | None = None
    next_send_at: datetime | None = None
    last_delivery_status: str | None = None
    last_delivery_provider: str | None = None
    last_delivery_detail: str | None = None
    created_at: datetime
    updated_at: datetime


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _parse_hhmm(value: str, fallback: str) -> time:
    raw = (value or fallback).strip()
    try:
        hh, mm = raw.split(":", 1)
        return time(hour=int(hh), minute=int(mm))
    except Exception:
        fh, fm = fallback.split(":", 1)
        return time(hour=int(fh), minute=int(fm))


def compute_next_twice_daily_slot(
    now: datetime,
    morning_time: str = "09:00",
    evening_time: str = "17:00",
) -> datetime:
    """Return the next UTC timestamp among twice-daily slots strictly after now + 5 minutes."""
    utc_now = _as_utc(now) or datetime.now(timezone.utc)
    t_morning = _parse_hhmm(morning_time, "09:00")
    t_evening = _parse_hhmm(evening_time, "17:00")
    threshold = utc_now + timedelta(minutes=5)

    slots: list[datetime] = []
    for day_offset in (0, 1):
        d = (utc_now + timedelta(days=day_offset)).date()
        for t_val in (t_morning, t_evening):
            slots.append(datetime.combine(d, t_val, tzinfo=timezone.utc))
    slots.sort()

    for slot in slots:
        if slot > threshold:
            return slot
    return utc_now + timedelta(hours=12)


def _build_reminder_email_bodies(reminder: PersonalReminder, user_name: str) -> tuple[str, str]:
    notes_text = (reminder.notes or "").strip()
    schedule_str = f"Twice daily at {reminder.morning_time} & {reminder.evening_time} UTC until marked done"
    attempt_num = reminder.send_count + 1

    plain_parts = [
        f"Hello {user_name or 'CEO'},",
        f"This is reminder #{attempt_num} for your pending action item:\n\n  Task: {reminder.title}",
    ]
    if notes_text:
        plain_parts.append(f"Notes: {notes_text}")
    plain_parts.append(f"Schedule: {schedule_str}\nLog in to Leaders Document Intelligence to mark this reminder as done once completed.")
    plain_text = "\n\n".join(plain_parts)

    notes_html = (
        f"<p style='margin:10px 0 0;color:#334155;'><strong>Notes:</strong> {html.escape(notes_text)}</p>"
        if notes_text
        else ""
    )
    html_body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;overflow:hidden;">
    <div style="background:#0b1f3a;padding:18px 24px;color:#ffffff;">
      <div style="font-size:11px;color:#6ee7b7;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;">
        Leaders Document Intelligence · CEO Action Reminder #{attempt_num}
      </div>
      <h2 style="margin:6px 0 0;font-size:18px;font-weight:600;">{html.escape(reminder.title)}</h2>
    </div>
    <div style="padding:22px 24px;font-size:14px;line-height:1.6;">
      <p style="margin:0;">Hello {html.escape(user_name or 'CEO')},</p>
      <p style="margin:10px 0 0;">You set an executive reminder so this task is not forgotten:</p>
      <div style="margin:14px 0;padding:12px 16px;background:#f8fafc;border-left:4px solid #059669;border-radius:6px;">
        <div style="font-weight:700;color:#0b1f3a;">{html.escape(reminder.title)}</div>
        {notes_html}
      </div>
      <p style="margin:0;font-size:12px;color:#475569;">
        <strong>Cadence:</strong> {html.escape(schedule_str)}
      </p>
      <p style="margin:8px 0 0;font-size:12px;color:#64748b;">
        Open <strong>CEO Reminders</strong> in Leaders Document Intelligence and click <strong>Mark Done</strong> to stop these twice-daily alerts.
      </p>
    </div>
    <div style="background:#f8fafc;padding:10px 24px;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;">
      Leaders Edu Tour Ltd · Built by <strong>CHIDI AI</strong>
    </div>
  </div>
</body>
</html>"""
    return html_body, plain_text


def dispatch_personal_reminder(db: Session, reminder: PersonalReminder, user_name: str) -> None:
    """Send reminder email immediately and schedule the next twice-daily slot."""
    now = datetime.now(timezone.utc)
    subject = f"Action Reminder: {reminder.title}"
    html_body, plain_text = _build_reminder_email_bodies(reminder, user_name)
    delivery_status, delivery_provider, delivery_detail = dispatch_client_email(
        db,
        to_email=reminder.recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=plain_text,
    )
    reminder.send_count += 1
    reminder.last_sent_at = now
    reminder.last_delivery_status = delivery_status
    reminder.last_delivery_provider = delivery_provider
    reminder.last_delivery_detail = delivery_detail
    if not reminder.is_completed:
        reminder.next_send_at = compute_next_twice_daily_slot(
            now, reminder.morning_time, reminder.evening_time
        )


def process_due_personal_reminders(db: Session) -> int:
    """Dispatch all uncompleted personal reminders whose next_send_at timestamp is due."""
    now = datetime.now(timezone.utc)
    pending = (
        db.scalars(
            select(PersonalReminder)
            .options(joinedload(PersonalReminder.user))
            .where(
                PersonalReminder.is_completed.is_(False),
                PersonalReminder.next_send_at.is_not(None),
            )
        )
        .unique()
        .all()
    )
    sent = 0
    for rem in pending:
        due_at = _as_utc(rem.next_send_at)
        if due_at and due_at <= now:
            uname = (
                f"{rem.user.first_name} {rem.user.last_name}".strip()
                if rem.user
                else "Executive"
            )
            dispatch_personal_reminder(db, rem, uname)
            sent += 1
    if sent > 0:
        db.commit()
    return sent


@router.post("/process-due")
def process_due_reminders_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Trigger immediate dispatch for any due twice-daily personal reminders."""
    processed = process_due_personal_reminders(db)
    return {"processed_count": processed}


@router.post("/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_reminders(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchDeleteResponse:
    """Delete multiple personal reminders owned by the caller (or any if CEO/Super Admin)."""
    if not payload.ids:
        return BatchDeleteResponse(message="No reminders selected.", deleted_count=0, deleted_ids=[])

    rows = db.scalars(select(PersonalReminder).where(PersonalReminder.id.in_(payload.ids))).all()
    privileged = is_super_privileged(current_user)
    deleted_ids: list[str] = []
    for rem in rows:
        if rem.user_id != current_user.id and not privileged:
            raise HTTPException(status_code=403, detail="Cannot delete another user's reminder.")
        deleted_ids.append(rem.id)
        db.delete(rem)

    record_audit_event(
        db,
        action="PERSONAL_REMINDERS_BATCH_DELETED",
        entity_type="personal_reminder",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "reminder_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} reminder(s).",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.get("", response_model=list[PersonalReminderRead])
def list_my_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PersonalReminderRead]:
    """List personal twice-daily reminders for the logged-in user (dispatching any due alerts first)."""
    process_due_personal_reminders(db)
    rows = db.scalars(
        select(PersonalReminder)
        .where(PersonalReminder.user_id == current_user.id)
        .order_by(PersonalReminder.is_completed.asc(), desc(PersonalReminder.created_at))
    ).all()
    return [PersonalReminderRead.model_validate(r) for r in rows]


@router.post("", response_model=PersonalReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: PersonalReminderCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonalReminderRead:
    """Create a twice-daily personal reminder sent until marked completed."""
    now = datetime.now(timezone.utc)
    recipient = (
        str(payload.recipient_email).strip().lower()
        if payload.recipient_email
        else current_user.email
    )
    rem = PersonalReminder(
        user_id=current_user.id,
        title=payload.title.strip(),
        notes=payload.notes.strip() if payload.notes else None,
        recipient_email=recipient,
        times_per_day=2,
        morning_time=payload.morning_time,
        evening_time=payload.evening_time,
        is_completed=False,
        send_count=0,
        next_send_at=compute_next_twice_daily_slot(now, payload.morning_time, payload.evening_time),
    )
    db.add(rem)
    db.flush()

    if payload.send_immediately:
        user_name = f"{current_user.first_name} {current_user.last_name}".strip()
        dispatch_personal_reminder(db, rem, user_name)

    record_audit_event(
        db,
        action="PERSONAL_REMINDER_CREATED",
        entity_type="personal_reminder",
        entity_id=rem.id,
        actor=current_user,
        metadata={"title": rem.title, "recipient_email": recipient, "send_count": rem.send_count},
        request=request,
    )
    db.commit()
    db.refresh(rem)
    return PersonalReminderRead.model_validate(rem)


@router.patch("/{reminder_id}", response_model=PersonalReminderRead)
def update_reminder(
    reminder_id: str,
    payload: PersonalReminderUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonalReminderRead:
    """Update reminder text/schedule or toggle completion to pause/resume twice-daily alerts."""
    rem = db.scalar(select(PersonalReminder).where(PersonalReminder.id == reminder_id))
    if not rem:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    if rem.user_id != current_user.id and not is_super_privileged(current_user):
        raise HTTPException(status_code=403, detail="Access denied.")

    now = datetime.now(timezone.utc)
    if payload.title is not None:
        rem.title = payload.title.strip()
    if payload.notes is not None:
        rem.notes = payload.notes.strip() or None
    if payload.recipient_email is not None:
        rem.recipient_email = str(payload.recipient_email).strip().lower()
    if payload.morning_time is not None:
        rem.morning_time = payload.morning_time
    if payload.evening_time is not None:
        rem.evening_time = payload.evening_time

    if payload.is_completed is not None:
        rem.is_completed = payload.is_completed
        if payload.is_completed:
            rem.completed_at = now
            rem.next_send_at = None
        else:
            rem.completed_at = None
            rem.next_send_at = compute_next_twice_daily_slot(now, rem.morning_time, rem.evening_time)
    elif not rem.is_completed and (payload.morning_time is not None or payload.evening_time is not None):
        rem.next_send_at = compute_next_twice_daily_slot(now, rem.morning_time, rem.evening_time)

    record_audit_event(
        db,
        action="PERSONAL_REMINDER_UPDATED",
        entity_type="personal_reminder",
        entity_id=rem.id,
        actor=current_user,
        metadata={"is_completed": rem.is_completed},
        request=request,
    )
    db.commit()
    db.refresh(rem)
    return PersonalReminderRead.model_validate(rem)


@router.post("/{reminder_id}/send-now", response_model=PersonalReminderRead)
def send_reminder_now(
    reminder_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonalReminderRead:
    """Manually trigger an immediate reminder email send for a pending reminder."""
    rem = db.scalar(select(PersonalReminder).where(PersonalReminder.id == reminder_id))
    if not rem:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    if rem.user_id != current_user.id and not is_super_privileged(current_user):
        raise HTTPException(status_code=403, detail="Access denied.")
    if rem.is_completed:
        raise HTTPException(status_code=400, detail="Completed reminders cannot be sent; reopen first.")

    user_name = f"{current_user.first_name} {current_user.last_name}".strip()
    dispatch_personal_reminder(db, rem, user_name)
    record_audit_event(
        db,
        action="PERSONAL_REMINDER_SENT",
        entity_type="personal_reminder",
        entity_id=rem.id,
        actor=current_user,
        metadata={"recipient_email": rem.recipient_email, "send_count": rem.send_count},
        request=request,
    )
    db.commit()
    db.refresh(rem)
    return PersonalReminderRead.model_validate(rem)


@router.delete("/{reminder_id}", response_model=MessageResponse)
def delete_reminder(
    reminder_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Delete a single personal reminder."""
    rem = db.scalar(select(PersonalReminder).where(PersonalReminder.id == reminder_id))
    if not rem:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    if rem.user_id != current_user.id and not is_super_privileged(current_user):
        raise HTTPException(status_code=403, detail="Access denied.")

    title = rem.title
    db.delete(rem)
    record_audit_event(
        db,
        action="PERSONAL_REMINDER_DELETED",
        entity_type="personal_reminder",
        entity_id=reminder_id,
        actor=current_user,
        metadata={"title": title},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Deleted reminder '{title}'.")
