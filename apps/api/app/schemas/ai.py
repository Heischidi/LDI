"""Strict Pydantic schemas validating AI classification responses."""

from pydantic import BaseModel, Field, field_validator


class AIClassificationResult(BaseModel):
    """Structured JSON schema enforced on every AI provider output."""

    document_type: str = Field(min_length=2, max_length=80)
    confidence: float = Field(ge=0.0, le=1.0)
    applicant_name: str | None = Field(default=None, max_length=200)
    document_number: str | None = Field(default=None, max_length=120)
    issuing_organisation: str | None = Field(default=None, max_length=200)
    issue_date: str | None = Field(default=None, max_length=30)
    expiry_date: str | None = Field(default=None, max_length=30)
    document_date: str | None = Field(default=None, max_length=30)
    page_count: int = Field(default=1, ge=1)
    is_readable: bool = True
    is_incomplete: bool = False
    possible_issues: list[str] = Field(default_factory=list)
    classification_reason: str = Field(default="", max_length=1000)

    @field_validator("document_type")
    @classmethod
    def normalize_doc_type(cls, value: str) -> str:
        return value.strip().upper().replace(" ", "_")
