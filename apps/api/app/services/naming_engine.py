"""Automatic document naming and structured folder hierarchy generator."""

import re
from datetime import datetime, timezone

_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def sanitize_segment(value: str, uppercase: bool = False) -> str:
    """Remove invalid filesystem characters and replace spaces with underscores."""
    cleaned = _INVALID_CHARS_RE.sub("", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = _MULTI_UNDERSCORE_RE.sub("_", cleaned).strip("_.")
    if not cleaned:
        cleaned = "ITEM"
    return cleaned.upper() if uppercase else cleaned


def format_document_filename(
    *,
    template: str,
    document_order: int,
    document_type_label: str,
    extension: str,
    applicant_name: str,
    document_date: str | None = None,
    version_index: int = 1,
    total_same_type: int = 1,
) -> str:
    """Generate standardized document filename respecting order, conventions, and duplicate disambiguation."""
    ext = extension.lstrip(".").lower() or "pdf"
    order_str = f"{document_order:02d}"
    doc_type_clean = sanitize_segment(document_type_label)
    applicant_clean = sanitize_segment(applicant_name)

    year_or_date = str(datetime.now(timezone.utc).year)
    if document_date:
        year_or_date = sanitize_segment(document_date[:4] if "{date}" in template and len(document_date) >= 4 else document_date)

    # Render without extension first so we can cleanly append version suffix before .{extension}
    base_template = template.replace(".{extension}", "")
    rendered = base_template.format(
        document_order=order_str,
        document_type=doc_type_clean,
        applicant_name=applicant_clean,
        date=year_or_date,
        extension=ext,
    )
    rendered = sanitize_segment(rendered)

    if total_same_type > 1 or version_index > 1:
        rendered = f"{rendered}_{version_index}"

    return f"{rendered}.{ext}"


def format_applicant_folder_path(
    *,
    folder_template: str,
    destination_name: str,
    purpose_name: str,
    applicant_full_name: str,
    application_reference: str,
) -> str:
    """Render structured folder path e.g. LEADERS_EDU_TOUR_DOCUMENTS/UNITED_KINGDOM/STUDY/JOHN_DOE_LDI-2026-0001."""
    rendered = folder_template.format(
        DESTINATION=sanitize_segment(destination_name, uppercase=True),
        PURPOSE=sanitize_segment(purpose_name, uppercase=True),
        APPLICANT_NAME=sanitize_segment(applicant_full_name, uppercase=True),
        APPLICATION_REFERENCE=sanitize_segment(application_reference, uppercase=True),
    )
    # Normalize slashes
    parts = [sanitize_segment(p, uppercase=True) for p in rendered.replace("\\", "/").split("/") if p.strip()]
    return "/".join(parts)
