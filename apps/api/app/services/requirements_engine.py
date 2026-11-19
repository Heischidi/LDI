"""Configurable requirements matching, condition evaluation, and versioning engine."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    DocumentAlias,
    DocumentRequirement,
    DocumentType,
    RequirementSet,
    RequirementVersion,
)


def evaluate_condition(
    condition_expression: dict[str, Any] | None,
    context: dict[str, Any],
) -> bool:
    """Evaluate logical rules like {"field": "is_sponsored", "op": "==", "value": True} or AND/OR groups."""
    if not condition_expression:
        return True

    if "and" in condition_expression:
        return all(evaluate_condition(sub, context) for sub in condition_expression["and"])
    if "or" in condition_expression:
        return any(evaluate_condition(sub, context) for sub in condition_expression["or"])

    field = condition_expression.get("field")
    op = condition_expression.get("op", "==")
    expected = condition_expression.get("value")
    actual = context.get(field)

    if op == "==":
        return str(actual).lower() == str(expected).lower() if actual is not None else False
    if op == "!=":
        return str(actual).lower() != str(expected).lower()
    if op == "in":
        return actual in (expected or [])
    if op == "truthy":
        return bool(actual)
    return False


def find_matching_requirement_set(
    db: Session,
    *,
    destination_id: str,
    purpose_id: str,
    category_id: str,
    applicant_type: str = "STANDARD",
) -> RequirementSet | None:
    """Resolve the active RequirementSet matching destination, purpose, category, and applicant_type."""
    req_set = db.scalar(
        select(RequirementSet)
        .options(
            joinedload(RequirementSet.destination),
            joinedload(RequirementSet.purpose),
            joinedload(RequirementSet.category),
            joinedload(RequirementSet.versions)
            .joinedload(RequirementVersion.items)
            .joinedload(DocumentRequirement.document_type),
        )
        .where(
            RequirementSet.destination_id == destination_id,
            RequirementSet.purpose_id == purpose_id,
            RequirementSet.category_id == category_id,
            RequirementSet.applicant_type == applicant_type,
            RequirementSet.is_active.is_(True),
        )
    )
    if req_set:
        return req_set

    # Fallback match ignoring applicant_type specialization
    return db.scalar(
        select(RequirementSet)
        .options(
            joinedload(RequirementSet.destination),
            joinedload(RequirementSet.purpose),
            joinedload(RequirementSet.category),
            joinedload(RequirementSet.versions)
            .joinedload(RequirementVersion.items)
            .joinedload(DocumentRequirement.document_type),
        )
        .where(
            RequirementSet.destination_id == destination_id,
            RequirementSet.purpose_id == purpose_id,
            RequirementSet.category_id == category_id,
            RequirementSet.is_active.is_(True),
        )
    )


def get_active_version(req_set: RequirementSet | None) -> RequirementVersion | None:
    """Return the active RequirementVersion for a RequirementSet."""
    if not req_set or not req_set.versions:
        return None
    if req_set.active_version_id:
        for v in req_set.versions:
            if v.id == req_set.active_version_id:
                return v
    return req_set.versions[0]


def resolve_canonical_document_type(db: Session, type_or_alias: str) -> DocumentType | None:
    """Resolve a canonical DocumentType by exact code, name, or configured DocumentAlias."""
    cleaned = type_or_alias.strip()
    upper_code = cleaned.upper().replace(" ", "_")
    dt = db.scalar(select(DocumentType).where(DocumentType.code == upper_code))
    if dt:
        return dt

    dt = db.scalar(select(DocumentType).where(DocumentType.name.ilike(cleaned)))
    if dt:
        return dt

    alias = db.scalar(
        select(DocumentAlias)
        .options(joinedload(DocumentAlias.document_type))
        .where(DocumentAlias.alias_name.ilike(cleaned), DocumentAlias.is_active.is_(True))
    )
    if alias:
        return alias.document_type

    return db.scalar(select(DocumentType).where(DocumentType.code == "UNKNOWN"))


def create_new_requirement_version(
    db: Session,
    *,
    req_set: RequirementSet,
    items: list[dict[str, Any]],
    change_notes: str | None,
    created_by_id: str | None,
) -> RequirementVersion:
    """Create a new RequirementVersion without altering historical applicant records pinned to old versions."""
    now = datetime.now(timezone.utc)
    max_version = max((v.version_number for v in req_set.versions), default=0)

    # Mark previous active version effective_to
    for v in req_set.versions:
        if v.id == req_set.active_version_id and v.effective_to is None:
            v.effective_to = now

    new_version = RequirementVersion(
        requirement_set_id=req_set.id,
        version_number=max_version + 1,
        effective_from=now,
        change_notes=change_notes or f"Version {max_version + 1}",
        created_by_id=created_by_id,
    )
    db.add(new_version)
    db.flush()

    for item in items:
        db.add(
            DocumentRequirement(
                requirement_version_id=new_version.id,
                document_type_id=item["document_type_id"],
                requirement_level=item.get("requirement_level", "REQUIRED"),
                display_order=item.get("display_order", 1),
                condition_expression=item.get("condition_expression"),
                condition_explanation=item.get("condition_explanation"),
                alternative_doc_type_ids=item.get("alternative_doc_type_ids", []),
                allow_multiple_versions=item.get("allow_multiple_versions", True),
                expiry_rule_days=item.get("expiry_rule_days"),
                min_validity_days=item.get("min_validity_days"),
                custom_instructions=item.get("custom_instructions"),
                naming_prefix_override=item.get("naming_prefix_override"),
            )
        )

    req_set.active_version_id = new_version.id
    db.flush()
    return new_version
