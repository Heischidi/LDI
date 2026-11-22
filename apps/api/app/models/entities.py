"""Normalized SQLAlchemy 2.0 database models for Leaders Document Intelligence."""

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        Uuid(as_uuid=False),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Uuid(as_uuid=False),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )
    users: Mapped[list["User"]] = relationship("User", back_populates="role")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    assigned_applicants: Mapped[list["Applicant"]] = relationship(
        "Applicant", back_populates="assigned_officer"
    )


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class TravelPurpose(Base):
    __tablename__ = "travel_purposes"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ApplicationCategory(Base):
    __tablename__ = "application_categories"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    destination_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("destinations.id", ondelete="SET NULL"), nullable=True
    )
    purpose_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("travel_purposes.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    destination: Mapped["Destination | None"] = relationship("Destination")
    purpose: Mapped["TravelPurpose | None"] = relationship("TravelPurpose")


class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="GENERAL", nullable=False)
    default_order: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    has_expiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    naming_prefix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    aliases: Mapped[list["DocumentAlias"]] = relationship(
        "DocumentAlias", back_populates="document_type", cascade="all, delete-orphan"
    )


class DocumentAlias(Base):
    __tablename__ = "document_aliases"
    __table_args__ = (UniqueConstraint("document_type_id", "alias_name", name="uq_doc_alias"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    document_type_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("document_types.id", ondelete="CASCADE"), nullable=False
    )
    alias_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    document_type: Mapped["DocumentType"] = relationship("DocumentType", back_populates="aliases")


class RequirementSet(Base):
    __tablename__ = "requirement_sets"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    destination_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purpose_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("travel_purposes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("application_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    applicant_type: Mapped[str] = mapped_column(String(60), default="STANDARD", nullable=False)
    naming_convention: Mapped[str] = mapped_column(
        String(200), default="{document_order}_{document_type}.{extension}", nullable=False
    )
    folder_template: Mapped[str] = mapped_column(
        String(255),
        default="LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    active_version_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    destination: Mapped["Destination"] = relationship("Destination")
    purpose: Mapped["TravelPurpose"] = relationship("TravelPurpose")
    category: Mapped["ApplicationCategory"] = relationship("ApplicationCategory")
    versions: Mapped[list["RequirementVersion"]] = relationship(
        "RequirementVersion",
        back_populates="requirement_set",
        cascade="all, delete-orphan",
        order_by="RequirementVersion.version_number.desc()",
    )


class RequirementVersion(Base):
    __tablename__ = "requirement_versions"
    __table_args__ = (
        UniqueConstraint("requirement_set_id", "version_number", name="uq_req_set_version"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    requirement_set_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("requirement_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    requirement_set: Mapped["RequirementSet"] = relationship("RequirementSet", back_populates="versions")
    items: Mapped[list["DocumentRequirement"]] = relationship(
        "DocumentRequirement",
        back_populates="requirement_version",
        cascade="all, delete-orphan",
        order_by="DocumentRequirement.display_order.asc()",
    )


class DocumentRequirement(Base):
    __tablename__ = "document_requirements"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    requirement_version_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("requirement_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False
    )
    requirement_level: Mapped[str] = mapped_column(
        String(30), default="REQUIRED", nullable=False
    )  # REQUIRED | OPTIONAL | CONDITIONAL
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    condition_expression: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    condition_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternative_doc_type_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allow_multiple_versions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expiry_rule_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    naming_prefix_override: Mapped[str | None] = mapped_column(String(50), nullable=True)

    requirement_version: Mapped["RequirementVersion"] = relationship(
        "RequirementVersion", back_populates="items"
    )
    document_type: Mapped["DocumentType"] = relationship("DocumentType")


class Applicant(Base):
    __tablename__ = "applicants"
    __table_args__ = (
        Index("ix_applicants_search_name", "first_name", "last_name"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    application_reference: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )
    tracking_token: Mapped[str | None] = mapped_column(
        String(80), unique=True, nullable=True, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationality: Mapped[str] = mapped_column(String(100), nullable=False)
    passport_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    applicant_type: Mapped[str] = mapped_column(String(60), default="STANDARD", nullable=False)
    eligibility_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    destination_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purpose_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("travel_purposes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("application_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_officer_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requirement_version_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("requirement_versions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", nullable=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    destination: Mapped["Destination"] = relationship("Destination")
    purpose: Mapped["TravelPurpose"] = relationship("TravelPurpose")
    category: Mapped["ApplicationCategory"] = relationship("ApplicationCategory")
    assigned_officer: Mapped["User | None"] = relationship("User", back_populates="assigned_applicants")
    requirement_version: Mapped["RequirementVersion | None"] = relationship("RequirementVersion")
    batches: Mapped[list["UploadBatch"]] = relationship(
        "UploadBatch", back_populates="applicant", cascade="all, delete-orphan"
    )
    documents: Mapped[list["UploadedDocument"]] = relationship(
        "UploadedDocument", back_populates="applicant", cascade="all, delete-orphan"
    )
    checklist_statuses: Mapped[list["ApplicantDocumentStatus"]] = relationship(
        "ApplicantDocumentStatus", back_populates="applicant", cascade="all, delete-orphan"
    )
    stage_updates: Mapped[list["ClientStageUpdate"]] = relationship(
        "ClientStageUpdate",
        back_populates="applicant",
        cascade="all, delete-orphan",
        order_by="ClientStageUpdate.created_at.desc()",
    )


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    applicant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requirement_version_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("requirement_versions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="UPLOADED", nullable=False, index=True)
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    applicant: Mapped["Applicant"] = relationship("Applicant", back_populates="batches")
    documents: Mapped[list["UploadedDocument"]] = relationship(
        "UploadedDocument", back_populates="batch", cascade="all, delete-orphan"
    )


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    __table_args__ = (
        Index("ix_uploaded_docs_applicant_hash", "applicant_id", "sha256_hash"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    batch_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    applicant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_archive_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    ingestion_type: Mapped[str] = mapped_column(String(40), default="UNKNOWN", nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(40), default="UPLOADED", nullable=False, index=True
    )
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_of_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True
    )
    duplicate_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    batch: Mapped["UploadBatch"] = relationship("UploadBatch", back_populates="documents")
    applicant: Mapped["Applicant"] = relationship("Applicant", back_populates="documents")
    extracted_data: Mapped["ExtractedDocumentData | None"] = relationship(
        "ExtractedDocumentData", back_populates="uploaded_document", uselist=False, cascade="all, delete-orphan"
    )
    classifications: Mapped[list["DocumentClassification"]] = relationship(
        "DocumentClassification",
        back_populates="uploaded_document",
        cascade="all, delete-orphan",
        order_by="DocumentClassification.created_at.desc()",
    )
    processed_document: Mapped["ProcessedDocument | None"] = relationship(
        "ProcessedDocument", back_populates="uploaded_document", uselist=False, cascade="all, delete-orphan"
    )
    reviews: Mapped[list["DocumentReview"]] = relationship(
        "DocumentReview", back_populates="uploaded_document", cascade="all, delete-orphan"
    )


class ExtractedDocumentData(Base):
    __tablename__ = "extracted_document_data"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    uploaded_document_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    normalized_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    page_texts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_readable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blurry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_incomplete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detected_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    uploaded_document: Mapped["UploadedDocument"] = relationship(
        "UploadedDocument", back_populates="extracted_data"
    )


class DocumentClassification(Base):
    __tablename__ = "document_classifications"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    uploaded_document_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("document_types.id", ondelete="SET NULL"), nullable=True
    )
    predicted_type_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_tier: Mapped[str] = mapped_column(String(20), nullable=False)  # HIGH | MEDIUM | LOW
    extracted_applicant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_name_mismatch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_readable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    possible_issues: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    classification_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(60), nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_ai_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), default="PENDING_REVIEW", nullable=False, index=True
    )  # AUTO_PREPARED | PENDING_REVIEW | MANUAL_REQUIRED | APPROVED | CORRECTED | EXCLUDED
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    uploaded_document: Mapped["UploadedDocument"] = relationship(
        "UploadedDocument", back_populates="classifications"
    )
    document_type: Mapped["DocumentType | None"] = relationship("DocumentType")


class ProcessedDocument(Base):
    __tablename__ = "processed_documents"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    uploaded_document_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    applicant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False
    )
    document_type_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("document_types.id", ondelete="SET NULL"), nullable=True
    )
    generated_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_folder_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_order: Mapped[int] = mapped_column(Integer, default=99, nullable=False)
    version_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_approved_for_export: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    uploaded_document: Mapped["UploadedDocument"] = relationship(
        "UploadedDocument", back_populates="processed_document"
    )
    document_type: Mapped["DocumentType | None"] = relationship("DocumentType")


class DocumentReview(Base):
    __tablename__ = "document_reviews"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    uploaded_document_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classification_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("document_classifications.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    previous_type_code: Mapped[str] = mapped_column(String(80), nullable=False)
    new_type_code: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    corrected_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    uploaded_document: Mapped["UploadedDocument"] = relationship(
        "UploadedDocument", back_populates="reviews"
    )
    reviewed_by: Mapped["User | None"] = relationship("User")


class ApplicantDocumentStatus(Base):
    __tablename__ = "applicant_document_status"
    __table_args__ = (
        UniqueConstraint("applicant_id", "document_requirement_id", name="uq_applicant_req_status"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    applicant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_version_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("requirement_versions.id", ondelete="CASCADE"), nullable=False
    )
    document_requirement_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("document_requirements.id", ondelete="CASCADE"), nullable=False
    )
    document_type_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(40), default="MISSING", nullable=False
    )  # FOUND | MISSING | PENDING_REVIEW | UNREADABLE | POTENTIALLY_INVALID | OPTIONAL | CONDITIONAL
    verification_stage: Mapped[str] = mapped_column(
        String(40), default="DETECTED", nullable=False
    )  # DETECTED | QUALITY_CHECKED | MANUALLY_REVIEWED | OFFICER_APPROVED
    matched_document_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True
    )
    quality_issues: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    applicant: Mapped["Applicant"] = relationship("Applicant", back_populates="checklist_statuses")
    document_requirement: Mapped["DocumentRequirement"] = relationship("DocumentRequirement")
    document_type: Mapped["DocumentType"] = relationship("DocumentType")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    batch_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_document_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="QUEUED", nullable=False, index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ExportPackage(Base):
    __tablename__ = "export_packages"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    applicant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    folder_root: Mapped[str] = mapped_column(String(500), nullable=False)
    zip_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    report_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    approved_doc_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_doc_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    actor_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="GENERAL", nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ClientStageUpdate(Base):
    __tablename__ = "client_stage_updates"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    applicant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stage_code: Mapped[str] = mapped_column(String(60), nullable=False)
    stage_label: Mapped[str] = mapped_column(String(150), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(40), default="LOGGED_READY", nullable=False)
    delivery_provider: Mapped[str] = mapped_column(String(40), default="OUTBOX", nullable=False)
    delivery_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sent_by_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    applicant: Mapped["Applicant"] = relationship("Applicant", back_populates="stage_updates")


class PersonalReminder(Base):
    __tablename__ = "personal_reminders"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    times_per_day: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    morning_time: Mapped[str] = mapped_column(String(10), default="09:00", nullable=False)
    evening_time: Mapped[str] = mapped_column(String(10), default="17:00", nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_send_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_delivery_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_delivery_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_delivery_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User")


class StatementOfPurpose(Base):
    __tablename__ = "statements_of_purpose"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid_str)
    applicant_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("applicants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    candidate_name: Mapped[str] = mapped_column(String(200), nullable=False)
    university_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_or_program: Mapped[str] = mapped_column(String(255), nullable=False)
    degree_level: Mapped[str] = mapped_column(String(100), default="Master's", nullable=False)
    entry_term: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_country: Mapped[str] = mapped_column(String(120), nullable=False)
    academic_background: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    career_goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_university: Mapped[str | None] = mapped_column(Text, nullable=True)
    funding_and_ties: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str] = mapped_column(String(60), default="ACADEMIC_PROFESSIONAL", nullable=False)
    word_count_target: Mapped[int] = mapped_column(Integer, default=750, nullable=False)
    generated_content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(60), default="CHIDI_AI_SOP_ENGINE", nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), default="chidi-sop-v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    applicant: Mapped["Applicant | None"] = relationship("Applicant")
    created_by: Mapped["User | None"] = relationship("User")
