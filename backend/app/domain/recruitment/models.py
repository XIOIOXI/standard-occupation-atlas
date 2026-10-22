"""Typed contracts for the recruitment CSV import foundation.

These models intentionally stop before role profiling, skills, and LLM inference.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


RecordStatus = Literal["valid", "invalid", "duplicate", "superseded", "expired"]
IssueSeverity = Literal["error", "warning"]


class FieldIssue(BaseModel):
    field: str
    code: str
    message: str
    severity: IssueSeverity = "warning"


class ValidationReport(BaseModel):
    valid: bool
    headers: list[str]
    field_mapping: dict[str, str] = Field(default_factory=dict)
    missing_required_fields: list[str] = Field(default_factory=list)
    unknown_headers: list[str] = Field(default_factory=list)
    row_issues: dict[int, list[FieldIssue]] = Field(default_factory=dict)


class RecruitmentRecord(BaseModel):
    """Normalised CSV record while retaining original values for audit."""

    record_id: str
    row_number: int
    updated_at: date | None = None
    company_name: str | None = None
    company_type: str | None = None
    recruitment_session: str | None = None
    recruitment_batch: str | None = None
    industry_category: str | None = None
    location: str | None = None
    job_title: str | None = None
    normalized_job_title: str | None = None
    deadline: date | None = None
    deadline_raw: str | None = None
    education_requirement: str | None = None
    major_requirement: str | None = None
    normalized_major_requirement: str | None = None
    recruitment_url: HttpUrl | None = None
    announcement_url: HttpUrl | None = None
    record_status: RecordStatus
    eligible_for_market_analysis: bool
    eligible_for_industry_analysis: bool
    eligibility_reasons: list[str] = Field(default_factory=list)
    validation_issues: list[FieldIssue] = Field(default_factory=list)
    raw_payload: dict[str, str] = Field(default_factory=dict)


class PreviewResult(BaseModel):
    source_file_name: str
    encoding: str
    requested_rows: int
    returned_rows: int
    schema_report: ValidationReport
    records: list[RecruitmentRecord]


class DatasetSnapshot(BaseModel):
    """In-memory snapshot contract; persistence is added by a repository later."""

    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    source_name: str = "2026 recruitment dataset"
    source_format: Literal["csv", "xlsx"] = "csv"
    source_file_name: str
    source_checksum: str
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_updated_at: date | None = None
    schema_version: str = "2026-recruitment-csv-v1"
    record_count: int
    valid_record_count: int
    invalid_record_count: int
    validation_summary: dict[str, int]
    records: list[RecruitmentRecord]


def stable_record_id(payload: dict[str, str]) -> str:
    """Create a deterministic identity without relying on row order."""

    identity_fields = (
        "company_name",
        "job_title",
        "recruitment_session",
        "recruitment_batch",
        "location",
        "recruitment_url",
        "announcement_url",
    )
    material = "|".join(payload.get(field, "") for field in identity_fields)
    return sha256(material.encode("utf-8")).hexdigest()[:24]
