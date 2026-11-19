"""Pydantic schemas for applicants, destinations, travel purposes, and categories."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DestinationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    code: str
    region: str | None = None
    is_active: bool


class DestinationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=20)
    region: str | None = None


class TravelPurposeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    code: str
    description: str | None = None
    is_active: bool


class TravelPurposeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=40)
    description: str | None = None


class ApplicationCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    code: str
    destination_id: str | None = None
    purpose_id: str | None = None
    description: str | None = None
    is_archived: bool
    created_at: datetime


class ApplicationCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(min_length=2, max_length=60)
    destination_id: str | None = None
    purpose_id: str | None = None
    description: str | None = None


class ApplicationCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    destination_id: str | None = None
    purpose_id: str | None = None
    description: str | None = None
    is_archived: bool | None = None


class ApplicantCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=50)
    date_of_birth: date | None = None
    nationality: str = Field(min_length=2, max_length=100)
    passport_number: str | None = Field(default=None, max_length=50)
    applicant_type: str = Field(default="STANDARD", max_length=60)
    eligibility_context: dict[str, Any] = Field(default_factory=dict)
    destination_id: str
    purpose_id: str
    category_id: str
    assigned_officer_id: str | None = None


class ApplicantUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = None
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = None
    passport_number: str | None = None
    applicant_type: str | None = None
    eligibility_context: dict[str, Any] | None = None
    destination_id: str | None = None
    purpose_id: str | None = None
    category_id: str | None = None
    assigned_officer_id: str | None = None
    status: str | None = None


class OfficerBrief(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str


class ApplicantSummary(BaseModel):
    id: str
    application_reference: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    full_name: str
    email: str
    phone_number: str
    date_of_birth: date | None = None
    nationality: str
    applicant_type: str
    destination: DestinationRead
    purpose: TravelPurposeRead
    category: ApplicationCategoryRead
    assigned_officer: OfficerBrief | None = None
    requirement_version_id: str | None = None
    status: str
    is_archived: bool
    document_count: int = 0
    missing_required_count: int = 0
    pending_review_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChecklistStatusItem(BaseModel):
    id: str
    document_requirement_id: str
    document_type_id: str
    document_type_code: str
    document_type_name: str
    requirement_level: str
    display_order: int
    status: str
    verification_stage: str
    matched_document_id: str | None = None
    matched_filename: str | None = None
    generated_filename: str | None = None
    condition_explanation: str | None = None
    custom_instructions: str | None = None
    alternative_doc_type_codes: list[str] = Field(default_factory=list)
    quality_issues: list[str] = Field(default_factory=list)


class ApplicantDetail(ApplicantSummary):
    passport_number_masked: str | None = None
    eligibility_context: dict[str, Any] = Field(default_factory=dict)
    checklist: list[ChecklistStatusItem] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    batches: list[dict[str, Any]] = Field(default_factory=list)
    exports: list[dict[str, Any]] = Field(default_factory=list)
