"""AI Statement of Purpose (SOP) generation, editing, PDF/DOCX export, and applicant attachment."""

from datetime import datetime, timezone
import hashlib
import io
import re
from xml.sax.saxutils import escape

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
import httpx
from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
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
from app.models.entities import (
    Applicant,
    DocumentClassification,
    ExtractedDocumentData,
    StatementOfPurpose,
    SystemSetting,
    UploadBatch,
    UploadedDocument,
    User,
)
from app.schemas.common import BatchDeleteRequest, BatchDeleteResponse, MessageResponse
from app.services.audit_service import record_audit_event
from app.services.checklist_service import sync_applicant_checklist_and_naming
from app.services.requirements_engine import resolve_canonical_document_type
from app.storage.service import get_storage_backend

router = APIRouter(prefix="/sop", tags=["Statement of Purpose AI"])


class SopGenerateRequest(BaseModel):
    applicant_id: str | None = None
    candidate_name: str = Field(min_length=2, max_length=200)
    university_name: str = Field(min_length=2, max_length=255)
    course_or_program: str = Field(min_length=2, max_length=255)
    degree_level: str = Field(default="Master's", max_length=100)
    entry_term: str = Field(min_length=2, max_length=100)
    destination_country: str = Field(min_length=2, max_length=120)
    academic_background: str | None = None
    work_experience: str | None = None
    career_goals: str | None = None
    why_university: str | None = None
    funding_and_ties: str | None = None
    tone: str = Field(default="ACADEMIC_PROFESSIONAL", max_length=60)
    word_count_target: int = Field(default=750, ge=300, le=2000)


class SopUpdateRequest(BaseModel):
    candidate_name: str | None = Field(default=None, min_length=2, max_length=200)
    university_name: str | None = Field(default=None, min_length=2, max_length=255)
    course_or_program: str | None = Field(default=None, min_length=2, max_length=255)
    degree_level: str | None = None
    entry_term: str | None = None
    destination_country: str | None = None
    academic_background: str | None = None
    work_experience: str | None = None
    career_goals: str | None = None
    why_university: str | None = None
    funding_and_ties: str | None = None
    tone: str | None = None
    word_count_target: int | None = Field(default=None, ge=300, le=2000)
    generated_content: str | None = None
    regenerate: bool = False


class SopRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    applicant_id: str | None = None
    created_by_id: str | None = None
    candidate_name: str
    university_name: str
    course_or_program: str
    degree_level: str
    entry_term: str
    destination_country: str
    academic_background: str | None = None
    work_experience: str | None = None
    career_goals: str | None = None
    why_university: str | None = None
    funding_and_ties: str | None = None
    tone: str
    word_count_target: int
    generated_content: str
    ai_provider: str
    ai_model: str
    created_at: datetime
    updated_at: datetime


def _build_sop_prompt(data: dict) -> str:
    return f"""Write a compelling, authentic, admission-ready and visa-officer-ready Statement of Purpose (SOP) in cohesive paragraphs (no markdown bullet lists, no placeholders).
Target word count: approximately {data.get('word_count_target', 750)} words.
Tone: {data.get('tone', 'ACADEMIC_PROFESSIONAL')}.

Candidate Details:
- Full Name: {data['candidate_name']}
- Target University / Institution: {data['university_name']}
- Course / Program: {data['course_or_program']} ({data['degree_level']})
- Entry Term / Intake: {data['entry_term']}
- Destination Country: {data['destination_country']}
- Academic Background: {data.get('academic_background') or 'Strong relevant prior academic foundation'}
- Work & Practical Experience: {data.get('work_experience') or 'Hands-on professional and project exposure'}
- Why This University & Country: {data.get('why_university') or f'Academic rigor, faculty mentorship, and global perspective in {data["destination_country"]}'}
- Post-Study Career Goals: {data.get('career_goals') or 'Advancing leadership and specialist impact upon returning home'}
- Funding & Home Country Ties: {data.get('funding_and_ties') or 'Full financial backing arranged with clear family and career anchors in home country'}

Structure cleanly with:
1. Header lines: "STATEMENT OF PURPOSE", "Applicant: ...", "Program: ... — ..., Entry: ...".
2. Opening hook connecting personal motivation to {data['course_or_program']}.
3. Academic foundation & key coursework/projects.
4. Professional / practical experience & technical competencies gained.
5. Specific academic fit for {data['university_name']} and studying in {data['destination_country']} for the {data['entry_term']} intake.
6. Clear post-study career plan, financial readiness, and commitment to contributing back home.
"""


def _build_deterministic_sop(data: dict) -> str:
    name = data["candidate_name"].strip()
    uni = data["university_name"].strip()
    course = data["course_or_program"].strip()
    degree = (data.get("degree_level") or "Master's").strip()
    term = data["entry_term"].strip()
    country = data["destination_country"].strip()
    acad = (data.get("academic_background") or "").strip()
    work = (data.get("work_experience") or "").strip()
    why_uni = (data.get("why_university") or "").strip()
    goals = (data.get("career_goals") or "").strip()
    funding = (data.get("funding_and_ties") or "").strip()
    tone = (data.get("tone") or "ACADEMIC_PROFESSIONAL").upper()

    opening = (
        f"Applying for admission to the {degree} program in {course} at {uni} for the {term} intake "
        f"represents a deliberate milestone in my academic and professional trajectory. Having witnessed "
        f"firsthand how rigorous training in {course} drives measurable transformation across growing economies, "
        f"I am eager to deepen my expertise within {country}'s globally respected higher education ecosystem."
        if tone != "CONCISE_VISA_FOCUSED"
        else f"I am writing to present my academic rationale and career plan in support of my application to study "
        f"{course} ({degree}) at {uni} in {country} commencing {term}. My educational foundation, professional readiness, "
        f"and post-study objectives align directly with the curriculum and outcomes of this program."
    )

    acad_para = (
        f"My academic preparation has provided me with the analytical discipline required for advanced study at {uni}. "
        + (
            f"{acad.rstrip('.')}."
            if acad
            else f"Throughout my previous studies, I developed a strong command of foundational principles relevant to {course}, "
            "combining quantitative coursework with independent research and collaborative projects."
        )
    )

    work_para = (
        "Complementing my academic credentials, my practical experience has sharpened my ability to translate theory into results. "
        + (
            f"{work.rstrip('.')}."
            if work
            else f"Through hands-on roles and applied problem-solving, I strengthened my project execution, communication, "
            f"and teamwork capabilities while identifying specialized competencies in {course} that I now wish to master."
        )
    )

    fit_para = (
        f"I selected {uni} in {country} after carefully evaluating institutions offering specialized instruction in {course}. "
        + (
            f"{why_uni.rstrip('.')}."
            if why_uni
            else f"The structure of {uni}'s curriculum for the {term} cohort stands out for integrating research-led teaching, "
            f"practical case methodology, and industry relevance. Studying in {country} also offers an international peer network "
            "and globally benchmarked standards that are unmatched locally."
        )
    )

    goals_para = (
        f"Upon completing the {degree} in {course} at {uni}, I intend to pursue a clearly defined career path. "
        + (
            f"{goals.rstrip('.')}."
            if goals
            else f"My objective is to apply the specialized methodologies acquired during my studies to lead high-impact "
            f"initiatives, drive operational excellence, and mentor emerging talent in {course}."
        )
    )

    funding_para = (
        "From a practical standpoint, my study plan is backed by thorough preparation. "
        + (
            f"{funding.rstrip('.')}."
            if funding
            else "All tuition fees and living expenses for the duration of the program have been responsibly planned and secured, "
            "allowing me to dedicate my full attention to academic excellence while honoring all institutional and immigration obligations."
        )
    )

    closing = (
        f"In conclusion, my academic background, practical experience, and clear post-graduation vision prepare me to "
        f"thrive in the {course} cohort at {uni} starting {term}. I respectfully request the Admissions Committee's "
        f"favorable consideration and look forward to contributing meaningfully to the {uni} community.\n\n"
        f"Sincerely,\n{name}"
    )

    header = (
        f"STATEMENT OF PURPOSE\n"
        f"Applicant: {name}\n"
        f"Target Institution: {uni} ({country})\n"
        f"Program: {degree} in {course} — {term} Intake\n"
    )
    return "\n\n".join([header, opening, acad_para, work_para, fit_para, goals_para, funding_para, closing])


def _generate_sop_text(db: Session, data: dict) -> tuple[str, str, str]:
    """Generate admissions-ready SOP text using configured Gemini/OpenAI or CHIDI AI built-in engine."""
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == "ai.provider"))
    cfg = row.value_json if row and isinstance(row.value_json, dict) else {}
    provider = str(cfg.get("provider") or settings.AI_PROVIDER or "LOCAL_DETERMINISTIC").upper()
    allow_external = bool(cfg.get("allow_external_ai", settings.ALLOW_EXTERNAL_AI))
    prompt = _build_sop_prompt(data)

    if allow_external and provider == "GEMINI" and settings.GEMINI_API_KEY:
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.55},
            }
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
            text = (
                body.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            if len(text) > 120:
                return text, "GEMINI", settings.GEMINI_MODEL
        except Exception:
            pass

    if allow_external and provider == "OPENAI" and settings.OPENAI_API_KEY:
        try:
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.OPENAI_MODEL,
                        "temperature": 0.55,
                        "messages": [
                            {"role": "system", "content": "You are an expert international university admissions advisor."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                body = resp.json()
            text = body["choices"][0]["message"]["content"].strip()
            if len(text) > 120:
                return text, "OPENAI", settings.OPENAI_MODEL
        except Exception:
            pass

    return _build_deterministic_sop(data), "CHIDI_AI_SOP_ENGINE", "chidi-sop-v1"


def _render_sop_pdf_bytes(sop: StatementOfPurpose) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Statement of Purpose - {sop.candidate_name}",
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0B1F3A")
    title_style = ParagraphStyle("SopTitle", parent=styles["Heading1"], textColor=navy, fontSize=15, spaceAfter=4)
    meta_style = ParagraphStyle("SopMeta", parent=styles["Normal"], textColor=colors.HexColor("#475569"), fontSize=9.5, spaceAfter=12)
    body_style = ParagraphStyle("SopBody", parent=styles["Normal"], textColor=colors.HexColor("#0F172A"), fontSize=10.5, leading=15, spaceAfter=8)

    elements = [
        Paragraph("STATEMENT OF PURPOSE", title_style),
        Paragraph(
            escape(f"{sop.candidate_name} · {sop.degree_level} in {sop.course_or_program} · {sop.university_name} ({sop.destination_country}, {sop.entry_term})"),
            meta_style,
        ),
    ]
    for para in sop.generated_content.split("\n\n"):
        clean = para.strip()
        if not clean:
            continue
        if clean.startswith("STATEMENT OF PURPOSE\n"):
            continue
        elements.append(Paragraph(escape(clean).replace("\n", "<br/>"), body_style))
    elements.append(Spacer(1, 6))
    doc.build(elements)
    return buf.getvalue()


def _render_sop_docx_bytes(sop: StatementOfPurpose) -> bytes:
    doc = DocxDocument()
    doc.add_heading("STATEMENT OF PURPOSE", level=1)
    for para in sop.generated_content.split("\n\n"):
        clean = para.strip()
        if clean:
            doc.add_paragraph(clean)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _safe_slug(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_")
    return cleaned or "Candidate"


@router.get("", response_model=list[SopRead])
def list_sops(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> list[SopRead]:
    stmt = select(StatementOfPurpose).order_by(desc(StatementOfPurpose.created_at))
    if not is_super_privileged(current_user):
        stmt = stmt.where(StatementOfPurpose.created_by_id == current_user.id)
    rows = db.scalars(stmt).all()
    return [SopRead.model_validate(r) for r in rows]


@router.post("/generate", response_model=SopRead, status_code=status.HTTP_201_CREATED)
def generate_sop(
    payload: SopGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> SopRead:
    if payload.applicant_id:
        app = db.scalar(select(Applicant).where(Applicant.id == payload.applicant_id))
        if not app:
            raise HTTPException(status_code=404, detail="Applicant not found.")
        ensure_applicant_access(app, current_user)

    data = payload.model_dump()
    content, provider, model_name = _generate_sop_text(db, data)
    sop = StatementOfPurpose(
        applicant_id=payload.applicant_id,
        created_by_id=current_user.id,
        candidate_name=payload.candidate_name.strip(),
        university_name=payload.university_name.strip(),
        course_or_program=payload.course_or_program.strip(),
        degree_level=payload.degree_level.strip(),
        entry_term=payload.entry_term.strip(),
        destination_country=payload.destination_country.strip(),
        academic_background=payload.academic_background,
        work_experience=payload.work_experience,
        career_goals=payload.career_goals,
        why_university=payload.why_university,
        funding_and_ties=payload.funding_and_ties,
        tone=payload.tone,
        word_count_target=payload.word_count_target,
        generated_content=content,
        ai_provider=provider,
        ai_model=model_name,
    )
    db.add(sop)
    db.flush()
    record_audit_event(
        db,
        action="SOP_GENERATED",
        entity_type="statement_of_purpose",
        entity_id=sop.id,
        actor=current_user,
        metadata={"university": sop.university_name, "program": sop.course_or_program, "provider": provider},
        request=request,
    )
    db.commit()
    db.refresh(sop)
    return SopRead.model_validate(sop)


@router.post("/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_sops(
    payload: BatchDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> BatchDeleteResponse:
    if not payload.ids:
        return BatchDeleteResponse(message="No SOP drafts selected.", deleted_count=0, deleted_ids=[])

    rows = db.scalars(select(StatementOfPurpose).where(StatementOfPurpose.id.in_(payload.ids))).all()
    privileged = is_super_privileged(current_user)
    deleted_ids: list[str] = []
    for sop in rows:
        if sop.created_by_id != current_user.id and not privileged:
            raise HTTPException(status_code=403, detail="Access denied for SOP draft.")
        deleted_ids.append(sop.id)
        db.delete(sop)

    record_audit_event(
        db,
        action="SOP_BATCH_DELETED",
        entity_type="statement_of_purpose",
        actor=current_user,
        metadata={"deleted_count": len(deleted_ids), "sop_ids": deleted_ids},
        request=request,
    )
    db.commit()
    return BatchDeleteResponse(
        message=f"Deleted {len(deleted_ids)} Statement(s) of Purpose.",
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.patch("/{sop_id}", response_model=SopRead)
def update_sop(
    sop_id: str,
    payload: SopUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> SopRead:
    sop = db.scalar(select(StatementOfPurpose).where(StatementOfPurpose.id == sop_id))
    if not sop:
        raise HTTPException(status_code=404, detail="Statement of Purpose not found.")
    if sop.created_by_id != current_user.id and not is_super_privileged(current_user):
        raise HTTPException(status_code=403, detail="Access denied.")

    updates = payload.model_dump(exclude_unset=True, exclude={"regenerate"})
    for field, val in updates.items():
        setattr(sop, field, val)

    if payload.regenerate:
        data = {
            "candidate_name": sop.candidate_name,
            "university_name": sop.university_name,
            "course_or_program": sop.course_or_program,
            "degree_level": sop.degree_level,
            "entry_term": sop.entry_term,
            "destination_country": sop.destination_country,
            "academic_background": sop.academic_background,
            "work_experience": sop.work_experience,
            "career_goals": sop.career_goals,
            "why_university": sop.why_university,
            "funding_and_ties": sop.funding_and_ties,
            "tone": sop.tone,
            "word_count_target": sop.word_count_target,
        }
        content, provider, model_name = _generate_sop_text(db, data)
        sop.generated_content = content
        sop.ai_provider = provider
        sop.ai_model = model_name

    record_audit_event(
        db,
        action="SOP_UPDATED",
        entity_type="statement_of_purpose",
        entity_id=sop.id,
        actor=current_user,
        metadata={"regenerated": payload.regenerate},
        request=request,
    )
    db.commit()
    db.refresh(sop)
    return SopRead.model_validate(sop)


@router.get("/{sop_id}/export")
def export_sop_file(
    sop_id: str,
    format: str = Query(default="pdf", pattern="^(pdf|docx|txt)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> Response:
    sop = db.scalar(select(StatementOfPurpose).where(StatementOfPurpose.id == sop_id))
    if not sop:
        raise HTTPException(status_code=404, detail="Statement of Purpose not found.")
    if sop.created_by_id != current_user.id and not is_super_privileged(current_user):
        raise HTTPException(status_code=403, detail="Access denied.")

    slug = _safe_slug(sop.candidate_name)
    if format == "pdf":
        data = _render_sop_pdf_bytes(sop)
        media = "application/pdf"
    elif format == "docx":
        data = _render_sop_docx_bytes(sop)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        data = sop.generated_content.encode("utf-8")
        media = "text/plain; charset=utf-8"

    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{slug}_Statement_of_Purpose.{format}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/{sop_id}/attach-to-applicant")
def attach_sop_to_applicant(
    sop_id: str,
    request: Request,
    applicant_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> dict:
    """Render SOP as PDF and attach directly to the applicant's checklist as approved Statement of Purpose."""
    sop = db.scalar(select(StatementOfPurpose).where(StatementOfPurpose.id == sop_id))
    if not sop:
        raise HTTPException(status_code=404, detail="Statement of Purpose not found.")
    if sop.created_by_id != current_user.id and not is_super_privileged(current_user):
        raise HTTPException(status_code=403, detail="Access denied.")

    target_app_id = applicant_id or sop.applicant_id
    if not target_app_id:
        raise HTTPException(status_code=400, detail="Link an applicant first to attach this SOP.")

    app = db.scalar(select(Applicant).where(Applicant.id == target_app_id))
    if not app:
        raise HTTPException(status_code=404, detail="Applicant not found.")
    ensure_applicant_access(app, current_user)
    if sop.applicant_id != app.id:
        sop.applicant_id = app.id

    pdf_bytes = _render_sop_pdf_bytes(sop)
    sha256_val = hashlib.sha256(pdf_bytes).hexdigest()
    slug = _safe_slug(sop.candidate_name)
    filename = f"{slug}_Statement_of_Purpose.pdf"
    storage_key = f"applicants/{app.id}/sop/{sop.id}_{filename}"
    get_storage_backend().put_bytes(storage_key, pdf_bytes, content_type="application/pdf")

    now = datetime.now(timezone.utc)
    batch = UploadBatch(
        applicant_id=app.id,
        uploaded_by_id=current_user.id,
        requirement_version_id=app.requirement_version_id,
        status="COMPLETED",
        total_files=1,
        processed_files=1,
        failed_files=0,
        started_at=now,
        completed_at=now,
    )
    db.add(batch)
    db.flush()

    up_doc = UploadedDocument(
        batch_id=batch.id,
        applicant_id=app.id,
        original_filename=filename,
        file_extension="pdf",
        detected_mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_hash=sha256_val,
        storage_key=storage_key,
        ingestion_type="DIGITAL_PDF",
        page_count=1,
        processing_status="APPROVED",
        uploaded_by_id=current_user.id,
    )
    db.add(up_doc)
    db.flush()

    db.add(
        ExtractedDocumentData(
            uploaded_document_id=up_doc.id,
            raw_text=sop.generated_content,
            extraction_method="SOP_AI_GENERATOR",
            ocr_confidence=1.0,
            is_readable=True,
        )
    )
    dt = resolve_canonical_document_type(db, "STATEMENT_OF_PURPOSE")
    db.add(
        DocumentClassification(
            uploaded_document_id=up_doc.id,
            document_type_id=dt.id if dt else None,
            predicted_type_code="STATEMENT_OF_PURPOSE",
            confidence=1.0,
            confidence_tier="HIGH",
            extracted_applicant_name=f"{app.first_name} {app.last_name}".strip(),
            name_match_score=1.0,
            has_name_mismatch=False,
            issuing_authority="Leaders Edu Tour Ltd · CHIDI AI",
            page_count=1,
            is_readable=True,
            possible_issues=[],
            classification_reason="Generated and attached directly via LDI AI SOP Studio.",
            ai_provider=sop.ai_provider,
            ai_model=sop.ai_model,
            status="APPROVED",
            is_current=True,
        )
    )
    db.flush()

    sync_applicant_checklist_and_naming(db, app.id)
    record_audit_event(
        db,
        action="SOP_ATTACHED_TO_APPLICANT",
        entity_type="uploaded_document",
        entity_id=up_doc.id,
        actor=current_user,
        metadata={"applicant_id": app.id, "sop_id": sop.id},
        request=request,
    )
    db.commit()
    return {
        "message": f"Attached Statement of Purpose PDF to {app.application_reference} and satisfied checklist item.",
        "document_id": up_doc.id,
        "applicant_id": app.id,
    }


@router.delete("/{sop_id}", response_model=MessageResponse)
def delete_sop(
    sop_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_CEO, ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_OFFICER)),
) -> MessageResponse:
    sop = db.scalar(select(StatementOfPurpose).where(StatementOfPurpose.id == sop_id))
    if not sop:
        raise HTTPException(status_code=404, detail="Statement of Purpose not found.")
    if sop.created_by_id != current_user.id and not is_super_privileged(current_user):
        raise HTTPException(status_code=403, detail="Access denied.")

    name = sop.candidate_name
    db.delete(sop)
    record_audit_event(
        db,
        action="SOP_DELETED",
        entity_type="statement_of_purpose",
        entity_id=sop_id,
        actor=current_user,
        metadata={"candidate_name": name},
        request=request,
    )
    db.commit()
    return MessageResponse(message=f"Deleted Statement of Purpose for {name}.")
