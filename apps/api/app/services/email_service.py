"""Real-time client email notifications and stage milestone catalog (SMTP, Resend API, and audit outbox)."""

from email.message import EmailMessage
import html
import smtplib
import ssl
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import Applicant, SystemSetting

STAGE_CATALOG: dict[str, list[dict[str, str]]] = {
    "DOCUMENT_REMINDER": [
        {
            "code": "MISSING_DOCUMENTS_REMINDER",
            "label": "Missing Documents Reminder",
            "applicant_status": "DOCUMENTS_PENDING",
            "default_subject": "Action Required: Outstanding Documents for Your Application ({application_reference})",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Our team is currently processing your {destination} ({category}) application ({application_reference}). "
                "To avoid delays, please submit the outstanding documents listed below as soon as possible.\n\n"
                "Once submitted, our processing team will organize and verify your file immediately."
            ),
        },
        {
            "code": "DOCUMENTS_VERIFIED_COMPLETE",
            "label": "All Required Documents Verified",
            "applicant_status": "APPROVED",
            "default_subject": "Documents Verified Complete — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Great news! All submitted documents for your {destination} ({category}) application ({application_reference}) "
                "have been verified and organized successfully."
            ),
        },
        {
            "code": "FULL_PACKAGE_READY",
            "label": "Full Document Package Assembled & Ready",
            "applicant_status": "COMPLETED",
            "default_subject": "Your Full Application Package Is Ready — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Your complete {destination} ({category}) document package ({application_reference}) has been finalized, "
                "standardized, and packaged for the next submission milestone."
            ),
        },
    ],
    "ADMISSION": [
        {
            "code": "ADMISSION_SUBMITTED",
            "label": "Admission Application Submitted",
            "applicant_status": "ADMISSION_SUBMITTED",
            "default_subject": "Admission Application Submitted — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "We have submitted your {destination} {purpose} admission application ({application_reference}). "
                "We will notify you immediately as soon as the institution issues a decision."
            ),
        },
        {
            "code": "CONDITIONAL_OFFER_RECEIVED",
            "label": "Conditional Offer Received",
            "applicant_status": "CONDITIONAL_OFFER",
            "default_subject": "Update: Conditional Admission Offer Received — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Your institution has issued a Conditional Offer for application {application_reference}. "
                "Please review any remaining conditions or documents below so we can satisfy them promptly."
            ),
        },
        {
            "code": "UNCONDITIONAL_LOA_APPROVED",
            "label": "Unconditional Admission / LOA Approved",
            "applicant_status": "ADMISSION_APPROVED",
            "default_subject": "Congratulations! Unconditional Admission / LOA Approved — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Congratulations! Your Unconditional Offer / Letter of Acceptance (LOA) for {destination} ({application_reference}) "
                "has been approved. We are now ready to proceed with the next stage of your visa package."
            ),
        },
        {
            "code": "TUITION_DEPOSIT_REMINDER",
            "label": "Tuition Deposit & CAS/LOA Fee Reminder",
            "applicant_status": "TUITION_PENDING",
            "default_subject": "Reminder: Tuition Deposit Required to Proceed — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "This is a timely reminder to complete your tuition deposit payment so your institution can release "
                "your final visa support letter for application {application_reference}."
            ),
        },
    ],
    "VISA_PROCESSING": [
        {
            "code": "VISA_APPLICATION_SUBMITTED",
            "label": "Visa Application Submitted",
            "applicant_status": "VISA_SUBMITTED",
            "default_subject": "Visa Application Submitted — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Your {destination} ({category}) visa application ({application_reference}) has been submitted along with "
                "your verified document package. Watch your inbox for biometrics and embassy updates."
            ),
        },
        {
            "code": "BIOMETRICS_APPOINTMENT_REMINDER",
            "label": "Biometrics Appointment Scheduled / Reminder",
            "applicant_status": "BIOMETRICS_PENDING",
            "default_subject": "Reminder: Biometrics Appointment — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Please remember your upcoming biometrics appointment for your {destination} visa application ({application_reference}). "
                "Bring your original international passport and printed appointment confirmation."
            ),
        },
        {
            "code": "MEDICAL_REQUEST_REMINDER",
            "label": "Medical / Biometrics Additional Request",
            "applicant_status": "VISA_UNDER_REVIEW",
            "default_subject": "Action Required: Embassy Medical / Follow-Up Request — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "The visa office has requested a medical screening or additional clarification for application {application_reference}. "
                "Please complete this step before the deadline and upload your receipt."
            ),
        },
        {
            "code": "PASSPORT_COLLECTION_REQUEST",
            "label": "Original Passport Request / Collection Ready",
            "applicant_status": "PASSPORT_REQUESTED",
            "default_subject": "Passport Submission / Collection Update — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "There is an important passport update on your {destination} visa application ({application_reference}). "
                "Kindly contact your assigned officer immediately to coordinate passport submission or collection."
            ),
        },
        {
            "code": "VISA_APPROVED",
            "label": "Visa Approved",
            "applicant_status": "VISA_APPROVED",
            "default_subject": "Congratulations! Your {destination} Visa Is Approved — {application_reference}",
            "default_message": (
                "Hello {applicant_name},\n\n"
                "Congratulations! Your {destination} ({category}) visa application ({application_reference}) has been APPROVED. "
                "Our team will contact you shortly regarding pre-departure briefing and final handover."
            ),
        },
    ],
}


def find_stage_template(track: str, stage_code: str) -> dict[str, str] | None:
    """Look up a milestone definition from STAGE_CATALOG."""
    for item in STAGE_CATALOG.get(track, []):
        if item["code"] == stage_code:
            return item
    return None


def render_stage_message_text(
    *,
    template: str,
    applicant: Applicant,
    stage_label: str,
) -> str:
    """Format template placeholders safely using applicant metadata."""
    full_name = " ".join(p for p in [applicant.first_name, applicant.middle_name, applicant.last_name] if p)
    values = {
        "applicant_name": full_name,
        "application_reference": applicant.application_reference,
        "destination": applicant.destination.name if applicant.destination else "",
        "purpose": applicant.purpose.name if applicant.purpose else "",
        "category": applicant.category.name if applicant.category else "",
        "stage_label": stage_label,
    }
    try:
        return template.format(**values)
    except Exception:
        return template


def build_stage_email_bodies(
    *,
    applicant_name: str,
    application_reference: str,
    destination: str,
    category: str,
    stage_label: str,
    message_body: str,
    missing_items: list[str],
    officer_name: str,
    officer_email: str,
) -> tuple[str, str]:
    """Build executive HTML and plain-text email payloads with missing checklist reminders."""
    text_parts = [message_body.strip()]
    if missing_items:
        text_parts.append(
            "Outstanding Required Documents:\n" + "\n".join(f"  - {item}" for item in missing_items)
        )
    text_parts.append(
        f"Assigned Officer: {officer_name} ({officer_email})\n"
        f"Leaders Edu Tour Ltd · Built by CHIDI AI"
    )
    plain_text = "\n\n".join(text_parts)

    missing_html = ""
    if missing_items:
        bullets = "".join(f"<li style='margin:4px 0;'>{html.escape(item)}</li>" for item in missing_items)
        missing_html = (
            "<div style='margin-top:16px;padding:12px 16px;background:#fffbeb;border:1px solid #fde68a;"
            "border-radius:8px;'>"
            "<div style='font-weight:600;color:#92400e;margin-bottom:6px;font-size:13px;'>"
            "Outstanding Required Documents</div>"
            f"<ul style='margin:0;padding-left:18px;color:#78350f;font-size:13px;'>{bullets}</ul>"
            "</div>"
        )

    formatted_msg = "<br>".join(html.escape(line) for line in message_body.strip().splitlines())
    html_body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;overflow:hidden;">
    <div style="background:#0b1f3a;padding:20px 24px;color:#ffffff;">
      <div style="font-size:12px;color:#6ee7b7;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;">
        Leaders Edu Tour Ltd · Document Intelligence
      </div>
      <h2 style="margin:6px 0 0;font-size:18px;font-weight:600;">{html.escape(stage_label)}</h2>
    </div>
    <div style="padding:24px;font-size:14px;line-height:1.6;color:#1e293b;">
      <div style="margin-bottom:14px;padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;">
        <strong>Applicant:</strong> {html.escape(applicant_name)} &nbsp;|&nbsp;
        <strong>Ref:</strong> {html.escape(application_reference)} &nbsp;|&nbsp;
        <strong>Route:</strong> {html.escape(destination)} ({html.escape(category)})
      </div>
      <div>{formatted_msg}</div>
      {missing_html}
      <div style="margin-top:20px;padding-top:14px;border-top:1px solid #e2e8f0;font-size:12px;color:#475569;">
        <strong>Handled by:</strong> {html.escape(officer_name)} ({html.escape(officer_email)})
      </div>
    </div>
    <div style="background:#f8fafc;padding:12px 24px;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;display:flex;justify-content:space-between;">
      <span>Leaders Document Intelligence · Automated Client Notification</span>
      <span> &nbsp;·&nbsp; Built by <strong>CHIDI AI</strong></span>
    </div>
  </div>
</body>
</html>"""
    return html_body, plain_text


def _resolve_email_config(db: Session) -> dict[str, Any]:
    """Merge runtime DB SystemSetting ('notifications.email') with environment defaults."""
    db_row = db.scalar(select(SystemSetting).where(SystemSetting.key == "notifications.email"))
    cfg = dict(db_row.value_json) if db_row and isinstance(db_row.value_json, dict) else {}
    return {
        "provider": str(cfg.get("provider") or settings.EMAIL_PROVIDER or "AUTO").upper(),
        "smtp_host": str(cfg.get("smtp_host") or settings.SMTP_HOST or "").strip(),
        "smtp_port": int(cfg.get("smtp_port") or settings.SMTP_PORT or 587),
        "smtp_username": str(cfg.get("smtp_username") or settings.SMTP_USERNAME or "").strip(),
        "smtp_password": str(cfg.get("smtp_password") or settings.SMTP_PASSWORD or ""),
        "smtp_use_tls": bool(cfg.get("smtp_use_tls", settings.SMTP_USE_TLS)),
        "from_email": str(cfg.get("from_email") or settings.SMTP_FROM_EMAIL or "notifications@leaders.edu").strip(),
        "from_name": str(cfg.get("from_name") or settings.SMTP_FROM_NAME or "Leaders Edu Tour Ltd").strip(),
        "resend_api_key": str(cfg.get("resend_api_key") or settings.RESEND_API_KEY or "").strip(),
    }


def dispatch_client_email(
    db: Session,
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> tuple[str, str, str]:
    """Send real-time client email via Resend or SMTP, falling back cleanly to OUTBOX when unconfigured.

    Returns (delivery_status, delivery_provider, delivery_detail).
    """
    cfg = _resolve_email_config(db)
    provider = cfg["provider"]
    from_header = f"{cfg['from_name']} <{cfg['from_email']}>"

    if provider in {"AUTO", "RESEND"} and cfg["resend_api_key"]:
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {cfg['resend_api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": from_header,
                        "to": [to_email],
                        "subject": subject,
                        "html": html_body,
                        "text": text_body,
                    },
                )
                resp.raise_for_status()
                msg_id = resp.json().get("id", "queued")
            return "SENT_RESEND", "RESEND", f"Delivered via Resend (id: {msg_id})."
        except Exception as exc:
            return "FAILED", "RESEND", f"Resend delivery error: {str(exc)[:240]}"

    if provider in {"AUTO", "SMTP"} and cfg["smtp_host"]:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_header
            msg["To"] = to_email
            msg.set_content(text_body)
            msg.add_alternative(html_body, subtype="html")

            port = cfg["smtp_port"]
            if port == 465:
                with smtplib.SMTP_SSL(
                    cfg["smtp_host"],
                    port,
                    timeout=20,
                    context=ssl.create_default_context(),
                ) as server:
                    if cfg["smtp_username"]:
                        server.login(cfg["smtp_username"], cfg["smtp_password"])
                    server.send_message(msg)
            else:
                with smtplib.SMTP(cfg["smtp_host"], port, timeout=20) as server:
                    if cfg["smtp_use_tls"]:
                        server.starttls(context=ssl.create_default_context())
                    if cfg["smtp_username"]:
                        server.login(cfg["smtp_username"], cfg["smtp_password"])
                    server.send_message(msg)
            return "SENT_SMTP", "SMTP", f"Delivered live to {to_email} via {cfg['smtp_host']}."
        except Exception as exc:
            return "FAILED", "SMTP", f"SMTP delivery error: {str(exc)[:240]}"

    return (
        "LOGGED_READY",
        "OUTBOX",
        "Notification recorded in outbox; configure SMTP or Resend API key in Settings to deliver to client inboxes.",
    )
