"""Document completeness, quality, and checklist reconciliation engine."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    Applicant,
    ApplicantDocumentStatus,
    DocumentClassification,
    DocumentRequirement,
    DocumentType,
    ProcessedDocument,
    RequirementVersion,
    UploadedDocument,
)
from app.services.naming_engine import format_applicant_folder_path, format_document_filename
from app.services.requirements_engine import (
    evaluate_condition,
    find_matching_requirement_set,
    get_active_version,
)


def _parse_date_safe(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip()[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def sync_applicant_checklist_and_naming(
    db: Session,
    applicant_id: str,
    naming_convention_override: str | None = None,
) -> list[ApplicantDocumentStatus]:
    """Recompute checklist statuses, verification stages, and standardized filenames for an applicant."""
    applicant = db.scalar(
        select(Applicant)
        .options(
            joinedload(Applicant.destination),
            joinedload(Applicant.purpose),
            joinedload(Applicant.category),
            joinedload(Applicant.documents).joinedload(UploadedDocument.extracted_data),
            joinedload(Applicant.documents).joinedload(UploadedDocument.classifications),
            joinedload(Applicant.documents).joinedload(UploadedDocument.processed_document),
        )
        .where(Applicant.id == applicant_id)
    )
    if not applicant:
        raise ValueError(f"Applicant {applicant_id} not found")

    # Resolve or preserve pinned requirement_version_id
    req_set = find_matching_requirement_set(
        db,
        destination_id=applicant.destination_id,
        purpose_id=applicant.purpose_id,
        category_id=applicant.category_id,
        applicant_type=applicant.applicant_type,
    )
    req_version: RequirementVersion | None = None
    if applicant.requirement_version_id:
        req_version = db.scalar(
            select(RequirementVersion)
            .options(
                joinedload(RequirementVersion.items).joinedload(DocumentRequirement.document_type),
                joinedload(RequirementVersion.requirement_set),
            )
            .where(RequirementVersion.id == applicant.requirement_version_id)
        )
    if not req_version and req_set:
        req_version = get_active_version(req_set)
        if req_version:
            applicant.requirement_version_id = req_version.id
            db.flush()

    doc_types_by_id = {dt.id: dt for dt in db.scalars(select(DocumentType)).all()}
    doc_types_by_code = {dt.code: dt for dt in doc_types_by_id.values()}

    # Build lookup of non-excluded documents by their current effective DocumentType code
    active_docs = [d for d in applicant.documents if not d.is_excluded]
    docs_by_code: dict[str, list[UploadedDocument]] = {}
    order_map: dict[str, int] = {}
    prefix_map: dict[str, str] = {}

    if req_version:
        for req_item in req_version.items:
            code = req_item.document_type.code
            order_map[code] = req_item.display_order
            prefix_map[code] = (
                req_item.naming_prefix_override
                or req_item.document_type.naming_prefix
                or req_item.document_type.name
            )

    for doc in active_docs:
        current_cls = next((c for c in doc.classifications if c.is_current), None)
        if not current_cls:
            continue
        code = current_cls.predicted_type_code
        docs_by_code.setdefault(code, []).append(doc)

    # Refresh ProcessedDocument standardized filenames
    naming_template = (
        naming_convention_override
        or (req_version.requirement_set.naming_convention if req_version and req_version.requirement_set else None)
        or "{document_order}_{document_type}.{extension}"
    )
    folder_template = (
        req_version.requirement_set.folder_template
        if req_version and req_version.requirement_set
        else "LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}"
    )
    full_name = " ".join(p for p in [applicant.first_name, applicant.middle_name, applicant.last_name] if p)
    folder_path = format_applicant_folder_path(
        folder_template=folder_template,
        destination_name=applicant.destination.name,
        purpose_name=applicant.purpose.name,
        applicant_full_name=full_name,
        application_reference=applicant.application_reference,
    )

    # Count non-duplicate occurrences per code for deterministic _1/_2 numbering
    for code, grouped_docs in docs_by_code.items():
        dt = doc_types_by_code.get(code)
        doc_order = order_map.get(code, dt.default_order if dt else 90)
        label = prefix_map.get(code) or (dt.naming_prefix or dt.name if dt else code)
        non_dup_docs = [d for d in grouped_docs if not d.is_duplicate]
        dup_docs = [d for d in grouped_docs if d.is_duplicate]

        ordered_group = non_dup_docs + dup_docs
        total_non_dup = len(non_dup_docs)
        for idx, doc in enumerate(ordered_group, start=1):
            current_cls = next((c for c in doc.classifications if c.is_current), None)
            doc_date = current_cls.issue_date if current_cls else None
            gen_name = format_document_filename(
                template=naming_template,
                document_order=doc_order,
                document_type_label=label,
                extension=doc.file_extension,
                applicant_name=full_name,
                document_date=doc_date,
                version_index=1 if (total_non_dup <= 1 and not doc.is_duplicate) else idx,
                total_same_type=total_non_dup if not doc.is_duplicate else max(2, len(ordered_group)),
            )
            if doc.is_duplicate:
                stem, dot, ext = gen_name.rpartition(".")
                gen_name = f"{stem}_DUPLICATE.{ext}" if dot else f"{gen_name}_DUPLICATE"

            is_approved = bool(
                current_cls
                and current_cls.predicted_type_code != "UNKNOWN"
                and not doc.is_excluded
                and not doc.is_duplicate
            )

            proc = doc.processed_document
            if not proc:
                proc = ProcessedDocument(
                    uploaded_document_id=doc.id,
                    applicant_id=applicant.id,
                    batch_id=doc.batch_id,
                    document_type_id=dt.id if dt else None,
                    generated_filename=gen_name,
                    relative_folder_path=folder_path,
                    storage_key=doc.storage_key,
                    document_order=doc_order,
                    version_index=idx,
                    is_approved_for_export=is_approved,
                )
                db.add(proc)
            else:
                proc.document_type_id = dt.id if dt else None
                proc.generated_filename = gen_name
                proc.relative_folder_path = folder_path
                proc.document_order = doc_order
                proc.version_index = idx
                proc.is_approved_for_export = is_approved

    # Also update excluded docs so they aren't approved for export
    for doc in applicant.documents:
        if doc.is_excluded and doc.processed_document:
            doc.processed_document.is_approved_for_export = False

    db.flush()

    if not req_version:
        return []

    # Reconcile checklist rows against RequirementVersion items
    existing_rows = {
        row.document_requirement_id: row
        for row in db.scalars(
            select(ApplicantDocumentStatus).where(ApplicantDocumentStatus.applicant_id == applicant.id)
        ).all()
    }

    context = {
        **(applicant.eligibility_context or {}),
        "destination": applicant.destination.code,
        "purpose": applicant.purpose.code,
        "category": applicant.category.code,
        "applicant_type": applicant.applicant_type,
    }

    now = datetime.now(timezone.utc)
    updated_statuses: list[ApplicantDocumentStatus] = []

    for req_item in req_version.items:
        code = req_item.document_type.code
        candidate_codes = [code]
        for alt_id in req_item.alternative_doc_type_ids or []:
            if alt_id in doc_types_by_id:
                candidate_codes.append(doc_types_by_id[alt_id].code)
            elif alt_id in doc_types_by_code:
                candidate_codes.append(alt_id)

        matched_docs: list[UploadedDocument] = []
        for c_code in candidate_codes:
            matched_docs.extend(docs_by_code.get(c_code, []))

        primary_doc = next((d for d in matched_docs if not d.is_duplicate), matched_docs[0] if matched_docs else None)
        issues: list[str] = []
        verification_stage = "DETECTED"

        if not primary_doc:
            if req_item.requirement_level == "OPTIONAL":
                item_status = "OPTIONAL"
            elif req_item.requirement_level == "CONDITIONAL":
                applies = evaluate_condition(req_item.condition_expression, context)
                item_status = "MISSING" if applies else "CONDITIONAL"
            else:
                item_status = "MISSING"
        else:
            cls = next((c for c in primary_doc.classifications if c.is_current), None)
            ext = primary_doc.extracted_data
            if cls and cls.possible_issues:
                issues.extend(cls.possible_issues)

            # Check expiry rules
            if cls and cls.expiry_date:
                exp_dt = _parse_date_safe(cls.expiry_date)
                if exp_dt:
                    days_remaining = (exp_dt - now).days
                    if days_remaining < 0:
                        cls.is_expired = True
                        issues.append(f"Document expired on {cls.expiry_date}.")
                    elif req_item.min_validity_days and days_remaining < req_item.min_validity_days:
                        issues.append(
                            f"Document has {days_remaining} days validity remaining, below minimum {req_item.min_validity_days} days."
                        )

            if ext and (not ext.is_readable or ext.is_blurry):
                item_status = "UNREADABLE"
                verification_stage = "QUALITY_CHECKED"
            elif cls and (cls.is_expired or cls.has_name_mismatch or (ext and ext.is_incomplete)):
                item_status = "POTENTIALLY_INVALID"
                verification_stage = "QUALITY_CHECKED"
            elif cls and cls.status == "APPROVED":
                item_status = "FOUND"
                verification_stage = "OFFICER_APPROVED"
            elif cls and cls.status == "CORRECTED":
                item_status = "FOUND"
                verification_stage = "MANUALLY_REVIEWED"
            elif cls and cls.status in {"PENDING_REVIEW", "MANUAL_REQUIRED"}:
                item_status = "PENDING_REVIEW"
                verification_stage = "QUALITY_CHECKED"
            else:
                item_status = "PENDING_REVIEW" if (cls and cls.confidence_tier != "HIGH") else "FOUND"
                verification_stage = "QUALITY_CHECKED"

        row = existing_rows.get(req_item.id)
        if not row:
            row = ApplicantDocumentStatus(
                applicant_id=applicant.id,
                requirement_version_id=req_version.id,
                document_requirement_id=req_item.id,
                document_type_id=req_item.document_type_id,
                status=item_status,
                verification_stage=verification_stage,
                matched_document_id=primary_doc.id if primary_doc else None,
                quality_issues=issues,
            )
            db.add(row)
        else:
            row.status = item_status
            row.verification_stage = verification_stage
            row.matched_document_id = primary_doc.id if primary_doc else None
            row.quality_issues = issues
        updated_statuses.append(row)

    db.flush()
    return updated_statuses
