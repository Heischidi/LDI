"""Pydantic schemas for dashboard metrics, reports, audit logs, and system settings."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_applicants: int
    total_documents_processed: int
    applications_processing: int
    completed_batches: int
    applications_with_missing_docs: int
    documents_awaiting_review: int
    failed_processing_jobs: int
    completion_rate_percent: float
    documents_over_time: list[dict[str, Any]]
    applicants_by_destination: list[dict[str, Any]]
    applicants_by_purpose: list[dict[str, Any]]
    missing_document_stats: list[dict[str, Any]]
    recent_applicants: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]
    officer_activity: list[dict[str, Any]]


class AuditLogRead(BaseModel):
    id: str
    actor_user_id: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    ip_address: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class SystemSettingUpdate(BaseModel):
    value_json: dict[str, Any]
    description: str | None = None
