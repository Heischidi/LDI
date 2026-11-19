"""Organized applicant folder builder, ReportLab PDF processing report, and ZIP package generator."""

import io
import json
import zipfile
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    DocumentRequirement,
    ExportPackage,
    ProcessedDocument,
    RequirementVersion,
    UploadedDocument,
    User,
)
from app.services.audit_service import record_audit_event
from app.services.checklist_service import sync_applicant_checklist_and_naming
from app.services.naming_engine import format_applicant_folder_path
from app.storage.service import get_storage_backend


def generate_processing_report_pdf(
    *,
    applicant: Applicant,
    checklist_rows: list[ApplicantDocumentStatus],
    approved_docs: list[ProcessedDocument],
    all_docs: list[UploadedDocument],
    generated_at: datetime,
) -> bytes:
    """Render a clean, executive PDF processing report for the applicant's organized folder."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"LDI Processing Report - {applicant.application_reference}",
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0B1F3A")
    emerald = colors.HexColor("#0F5132")
    slate = colors.HexColor("#475569")
    light_bg = colors.HexColor("#F8FAFC")

    title_style = ParagraphStyle("LdiTitle", parent=styles["Heading1"], textColor=navy, fontSize=18, spaceAfter=4)
    subtitle_style = ParagraphStyle("LdiSub", parent=styles["Normal"], textColor=emerald, fontSize=10, spaceAfter=12)
    h2_style = ParagraphStyle("LdiH2", parent=styles["Heading2"], textColor=navy, fontSize=12, spaceBefore=10, spaceAfter=6)
    normal_style = ParagraphStyle("LdiBody", parent=styles["Normal"], textColor=colors.HexColor("#1E293B"), fontSize=9, leading=13)
    disclaimer_style = ParagraphStyle("LdiDisc", parent=styles["Normal"], textColor=slate, fontSize=8, leading=11)

    full_name = " ".join(p for p in [applicant.first_name, applicant.middle_name, applicant.last_name] if p)
    elements = [
        Paragraph("LEADERS EDU TOUR LTD — DOCUMENT INTELLIGENCE REPORT", title_style),
        Paragraph(
            f"Application Reference: <b>{applicant.application_reference}</b> &nbsp;|&nbsp; Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            subtitle_style,
        ),
    ]

    # Applicant Profile Table
    info_data = [
        ["Applicant Name", full_name, "Nationality", applicant.nationality],
        ["Email Address", applicant.email, "Destination", applicant.destination.name],
        ["Travel Purpose", applicant.purpose.name, "Category", applicant.category.name],
        ["Application Status", applicant.status, "Approved Files", str(len(approved_docs))],
    ]
    info_table = Table(info_data, colWidths=[34 * mm, 55 * mm, 32 * mm, 55 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), light_bg),
                ("BACKGROUND", (2, 0), (2, -1), light_bg),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.extend([info_table, Spacer(1, 8)])

    # Checklist Summary Table
    elements.append(Paragraph("1. Configured Requirements Checklist Summary", h2_style))
    checklist_table_data = [["#", "Document Requirement", "Level", "Status", "Verification Stage", "Notes / Issues"]]
    for row in sorted(checklist_rows, key=lambda r: r.document_requirement.display_order):
        issues_str = "; ".join(row.quality_issues) if row.quality_issues else "No quality warnings"
        checklist_table_data.append(
            [
                str(row.document_requirement.display_order),
                Paragraph(row.document_type.name, normal_style),
                row.document_requirement.requirement_level,
                row.status,
                row.verification_stage,
                Paragraph(issues_str[:160], normal_style),
            ]
        )

    chk_table = Table(
        checklist_table_data,
        colWidths=[8 * mm, 42 * mm, 24 * mm, 28 * mm, 30 * mm, 44 * mm],
        repeatRows=1,
    )
    chk_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.extend([chk_table, Spacer(1, 8)])

    # Processed & Approved Documents Mapping Table
    elements.append(Paragraph("2. Organised Package & Original Filename Mapping", h2_style))
    doc_rows = [["Order", "Standardised Filename (Approved)", "Original Filename", "AI Conf.", "Review Status"]]
    for proc in sorted(approved_docs, key=lambda p: (p.document_order, p.version_index)):
        up = proc.uploaded_document
        cls = next((c for c in up.classifications if c.is_current), None)
        conf_txt = f"{int(cls.confidence * 100)}%" if cls else "-"
        cls_status = cls.status if cls else "-"
        doc_rows.append(
            [
                f"{proc.document_order:02d}",
                Paragraph(proc.generated_filename, normal_style),
                Paragraph(up.original_filename, normal_style),
                conf_txt,
                cls_status,
            ]
        )

    if len(doc_rows) == 1:
        doc_rows.append(["-", "No approved documents included in export yet.", "-", "-", "-"])

    mapping_table = Table(doc_rows, colWidths=[12 * mm, 58 * mm, 54 * mm, 18 * mm, 34 * mm], repeatRows=1)
    mapping_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), emerald),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.extend([mapping_table, Spacer(1, 8)])

    # Warnings: Duplicates, Uncertain Classifications, Excluded Files
    warnings_lines: list[str] = []
    for d in all_docs:
        cls = next((c for c in d.classifications if c.is_current), None)
        if d.is_duplicate:
            warnings_lines.append(f"• Duplicate Flagged: {d.original_filename} — {d.duplicate_reason}")
        if d.is_excluded:
            warnings_lines.append(f"• Excluded from Final Package: {d.original_filename} (original preserved in ORIGINAL_DOCUMENTS/)")
        if cls and cls.confidence_tier != "HIGH" and cls.status not in {"APPROVED", "CORRECTED"}:
            warnings_lines.append(f"• Uncertain Classification ({int(cls.confidence * 100)}%): {d.original_filename} predicted as {cls.predicted_type_code}")

    if warnings_lines:
        elements.append(Paragraph("3. Duplicate, Exclusion & Quality Warnings", h2_style))
        for wl in warnings_lines:
            elements.append(Paragraph(wl, normal_style))
        elements.append(Spacer(1, 8))

    elements.append(
        Paragraph(
            "<b>Compliance Notice:</b> Leaders Document Intelligence is an internal administrative document organization tool for Leaders Edu Tour Ltd. "
            "Document identification, classification confidence, and checklist completeness do not certify document authenticity or guarantee visa approval by any immigration authority.",
            disclaimer_style,
        )
    )

    doc.build(elements)
    return buf.getvalue()


def create_applicant_export_package(
    db: Session,
    *,
    applicant_id: str,
    actor: User | None = None,
) -> ExportPackage:
    """Assemble structured folder ZIP (approved renamed files + ORIGINAL_DOCUMENTS + PROCESSING_REPORT.pdf + manifest)."""
    sync_applicant_checklist_and_naming(db, applicant_id)

    applicant = db.scalar(
        select(Applicant)
        .options(
            joinedload(Applicant.destination),
            joinedload(Applicant.purpose),
            joinedload(Applicant.category),
            joinedload(Applicant.requirement_version).joinedload(
                RequirementVersion.requirement_set
            ),
            joinedload(Applicant.checklist_statuses).joinedload(ApplicantDocumentStatus.document_type),
            joinedload(Applicant.checklist_statuses).joinedload(
                ApplicantDocumentStatus.document_requirement
            ),
            joinedload(Applicant.documents).joinedload(UploadedDocument.classifications),
            joinedload(Applicant.documents).joinedload(UploadedDocument.processed_document),
        )
        .where(Applicant.id == applicant_id)
    )
    if not applicant:
        raise ValueError(f"Applicant {applicant_id} not found.")

    now = datetime.now(timezone.utc)
    full_name = " ".join(p for p in [applicant.first_name, applicant.middle_name, applicant.last_name] if p)
    folder_template = (
        applicant.requirement_version.requirement_set.folder_template
        if applicant.requirement_version and applicant.requirement_version.requirement_set
        else "LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}"
    )
    folder_root = format_applicant_folder_path(
        folder_template=folder_template,
        destination_name=applicant.destination.name,
        purpose_name=applicant.purpose.name,
        applicant_full_name=full_name,
        application_reference=applicant.application_reference,
    )

    approved_procs: list[ProcessedDocument] = [
        d.processed_document
        for d in applicant.documents
        if d.processed_document
        and d.processed_document.is_approved_for_export
        and not d.is_excluded
    ]

    report_pdf_bytes = generate_processing_report_pdf(
        applicant=applicant,
        checklist_rows=applicant.checklist_statuses,
        approved_docs=approved_procs,
        all_docs=applicant.documents,
        generated_at=now,
    )

    missing_items = [
        {
            "document_type": r.document_type.name,
            "code": r.document_type.code,
            "level": r.document_requirement.requirement_level,
            "status": r.status,
        }
        for r in applicant.checklist_statuses
        if r.status in {"MISSING", "UNREADABLE", "POTENTIALLY_INVALID"}
    ]

    manifest = {
        "application_reference": applicant.application_reference,
        "applicant_name": full_name,
        "destination": applicant.destination.name,
        "purpose": applicant.purpose.name,
        "category": applicant.category.name,
        "folder_root": folder_root,
        "generated_at": now.isoformat(),
        "approved_documents": [
            {
                "generated_filename": p.generated_filename,
                "original_filename": p.uploaded_document.original_filename,
                "sha256_hash": p.uploaded_document.sha256_hash,
                "document_type": next(
                    (c.predicted_type_code for c in p.uploaded_document.classifications if c.is_current),
                    "UNKNOWN",
                ),
                "confidence": next(
                    (c.confidence for c in p.uploaded_document.classifications if c.is_current),
                    None,
                ),
            }
            for p in sorted(approved_procs, key=lambda x: (x.document_order, x.version_index))
        ],
        "missing_requirements": missing_items,
        "excluded_or_duplicate_originals": [
            {
                "original_filename": d.original_filename,
                "is_excluded": d.is_excluded,
                "is_duplicate": d.is_duplicate,
                "duplicate_reason": d.duplicate_reason,
            }
            for d in applicant.documents
            if d.is_excluded or d.is_duplicate
        ],
    }

    storage = get_storage_backend()
    zip_buf = io.BytesIO()
    seen_original_names: dict[str, int] = {}

    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Only approved, non-excluded renamed documents at the structured folder root
        used_export_names: set[str] = set()
        for proc in sorted(approved_procs, key=lambda x: (x.document_order, x.version_index)):
            file_bytes = storage.get_bytes(proc.uploaded_document.storage_key)
            filename = proc.generated_filename
            if filename in used_export_names:
                stem, dot, ext = filename.rpartition(".")
                counter = 2
                while f"{stem}_{counter}.{ext}" in used_export_names:
                    counter += 1
                filename = f"{stem}_{counter}.{ext}"
            used_export_names.add(filename)
            zf.writestr(f"{folder_root}/{filename}", file_bytes)

        # 2. Preserve all immutable originals in ORIGINAL_DOCUMENTS/
        for orig_doc in applicant.documents:
            orig_bytes = storage.get_bytes(orig_doc.storage_key)
            orig_name = orig_doc.original_filename
            count = seen_original_names.get(orig_name, 0) + 1
            seen_original_names[orig_name] = count
            if count > 1:
                stem, dot, ext = orig_name.rpartition(".")
                orig_name = f"{stem}_copy{count}.{ext}" if dot else f"{orig_name}_copy{count}"
            zf.writestr(f"{folder_root}/ORIGINAL_DOCUMENTS/{orig_name}", orig_bytes)

        # 3. Processing Report PDF & Manifest JSON
        zf.writestr(f"{folder_root}/PROCESSING_REPORT.pdf", report_pdf_bytes)
        zf.writestr(
            f"{folder_root}/processing_manifest.json",
            json.dumps(manifest, indent=2).encode("utf-8"),
        )

    zip_bytes = zip_buf.getvalue()
    timestamp_slug = now.strftime("%Y%m%d_%H%M%S")
    zip_key = f"exports/{applicant.application_reference}/{timestamp_slug}_{applicant.application_reference}.zip"
    report_key = f"exports/{applicant.application_reference}/{timestamp_slug}_PROCESSING_REPORT.pdf"

    storage.put_bytes(zip_key, zip_bytes, content_type="application/zip")
    storage.put_bytes(report_key, report_pdf_bytes, content_type="application/pdf")

    pkg = ExportPackage(
        applicant_id=applicant.id,
        generated_by_id=actor.id if actor else None,
        folder_root=folder_root,
        zip_storage_key=zip_key,
        report_storage_key=report_key,
        approved_doc_count=len(approved_procs),
        missing_doc_count=len(missing_items),
        manifest_json=manifest,
    )
    db.add(pkg)

    record_audit_event(
        db,
        action="FOLDER_EXPORTED",
        entity_type="applicant",
        entity_id=applicant.id,
        actor=actor,
        metadata={
            "application_reference": applicant.application_reference,
            "approved_doc_count": len(approved_procs),
            "missing_doc_count": len(missing_items),
        },
    )
    db.commit()
    db.refresh(pkg)
    return pkg
