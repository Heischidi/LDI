"""Pydantic schemas for configurable document requirements, types, and aliases."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_type_id: str
    alias_name: str
    is_active: bool


class DocumentTypeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=150)
    category: str = "GENERAL"
    default_order: int = 50
    has_expiry: bool = False
    min_validity_days: int | None = None
    naming_prefix: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)


class DocumentTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    category: str
    default_order: int
    has_expiry: bool
    min_validity_days: int | None = None
    naming_prefix: str | None = None
    description: str | None = None
    is_active: bool
    aliases: list[DocumentAliasRead] = Field(default_factory=list)


class DocumentRequirementItemInput(BaseModel):
    document_type_id: str
    requirement_level: str = Field(default="REQUIRED", pattern="^(REQUIRED|OPTIONAL|CONDITIONAL)$")
    display_order: int = Field(default=1, ge=1, le=999)
    condition_expression: dict[str, Any] | None = None
    condition_explanation: str | None = None
    alternative_doc_type_ids: list[str] = Field(default_factory=list)
    allow_multiple_versions: bool = True
    expiry_rule_days: int | None = None
    min_validity_days: int | None = None
    custom_instructions: str | None = None
    naming_prefix_override: str | None = None


class DocumentRequirementItemRead(BaseModel):
    id: str
    document_type_id: str
    document_type_code: str
    document_type_name: str
    requirement_level: str
    display_order: int
    condition_expression: dict[str, Any] | None = None
    condition_explanation: str | None = None
    alternative_doc_type_ids: list[str] = Field(default_factory=list)
    allow_multiple_versions: bool
    expiry_rule_days: int | None = None
    min_validity_days: int | None = None
    custom_instructions: str | None = None
    naming_prefix_override: str | None = None


class RequirementSetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    destination_id: str
    purpose_id: str
    category_id: str
    applicant_type: str = "STANDARD"
    naming_convention: str = "{document_order}_{document_type}.{extension}"
    folder_template: str = (
        "LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}"
    )
    change_notes: str | None = "Initial requirement specification"
    items: list[DocumentRequirementItemInput] = Field(default_factory=list)


class RequirementSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    applicant_type: str | None = None
    naming_convention: str | None = None
    folder_template: str | None = None
    is_active: bool | None = None
    change_notes: str | None = "Updated requirement version"
    items: list[DocumentRequirementItemInput] | None = None


class RequirementVersionRead(BaseModel):
    id: str
    version_number: int
    effective_from: datetime
    effective_to: datetime | None = None
    change_notes: str | None = None
    created_at: datetime
    items: list[DocumentRequirementItemRead] = Field(default_factory=list)


class RequirementSetRead(BaseModel):
    id: str
    name: str
    destination_id: str
    destination_name: str
    purpose_id: str
    purpose_name: str
    category_id: str
    category_name: str
    applicant_type: str
    naming_convention: str
    folder_template: str
    is_active: bool
    active_version_id: str | None = None
    active_version: RequirementVersionRead | None = None
    versions_summary: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
