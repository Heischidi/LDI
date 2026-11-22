"""Pydantic schemas for uploaded documents, classification review, and processing batches."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ClassificationRead(BaseModel):
    id: str
    predicted_type_code: str
    document_type_id: str | None = None
    document_type_name: str | None = None
    confidence: float
    confidence_tier: str
    extracted_applicant_name: str | None = None
    name_match_score: float | None = None
    has_name_mismatch: bool
    document_number: str | None = None
    issuing_authority: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    is_expired: bool
    page_count: int
    is_readable: bool
    possible_issues: list[str] = Field(default_factory=list)
    classification_reason: str
    ai_provider: str
    ai_model: str
    status: str
    created_at: datetime


class DocumentDetailRead(BaseModel):
    id: str
    batch_id: str
    applicant_id: str
    original_filename: str
    source_archive_name: str | None = None
    file_extension: str
    detected_mime_type: str
    file_size_bytes: int
    sha256_hash: str
    ingestion_type: str
    page_count: int
    processing_status: str
    is_excluded: bool
    is_duplicate: bool
    duplicate_of_id: str | None = None
    duplicate_reason: str | None = None
    error_message: str | None = None
    extracted_text_preview: str = ""
    extraction_method: str | None = None
    ocr_confidence: float | None = None
    is_blurry: bool = False
    is_incomplete: bool = False
    classification: ClassificationRead | None = None
    proposed_filename: str | None = None
    is_approved_for_export: bool = False
    preview_url: str
    created_at: datetime
    updated_at: datetime


class ClassificationCorrectionRequest(BaseModel):
    document_type_code: str | None = None
    action: str = Field(
        default="CHANGE_TYPE",
        pattern="^(CONFIRM|CHANGE_TYPE|CORRECT_METADATA|MARK_UNKNOWN|MARK_ADDITIONAL|FLAG_DUPLICATE|EXCLUDE|INCLUDE)$",
    )
    extracted_applicant_name: str | None = None
    document_number: str | None = None
    issuing_authority: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    custom_filename: str | None = Field(default=None, max_length=255)
    is_duplicate: bool | None = None
    is_excluded: bool | None = None
    notes: str | None = None


class BulkApproveRequest(BaseModel):
    applicant_id: str
    min_confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    document_ids: list[str] | None = None


class BatchStartRequest(BaseModel):
    batch_id: str
    naming_convention: str | None = None


class ProcessingJobRead(BaseModel):
    id: str
    batch_id: str
    uploaded_document_id: str | None = None
    original_filename: str | None = None
    status: str
    progress_percent: int
    attempt_count: int
    error_log: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BatchStatusRead(BaseModel):
    id: str
    applicant_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    jobs: list[ProcessingJobRead] = Field(default_factory=list)
    documents: list[DocumentDetailRead] = Field(default_factory=list)
