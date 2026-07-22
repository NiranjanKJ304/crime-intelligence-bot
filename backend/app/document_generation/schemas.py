"""
Pydantic schemas for AI Document Generation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata schema for generated AI Documents."""

    document_id: str
    document_type: str
    entity_id: int

    # Case-level fields
    case_id: int | None = None
    crime_number: str | None = None
    case_number: str | None = None

    # Location fields
    district_id: int | None = None
    district_name: str | None = None
    police_station_id: int | None = None
    police_station_name: str | None = None

    # Classification fields
    crime_category_id: int | None = None
    major_crime_id: int | None = None
    minor_crime_id: int | None = None
    case_status_id: int | None = None

    # Temporal fields
    crime_year: int | None = None
    crime_month: int | None = None

    # Court/Officer fields
    court_id: int | None = None
    court_name: str | None = None
    officer_id: int | None = None

    # Document quality
    text_length: int = 0
    section_count: int = 0

    # Timestamps
    created_at: str
    updated_at: str


class AIDocument(BaseModel):
    """The generated natural-language AI document."""

    document_id: str
    document_type: str
    text: str
    metadata: DocumentMetadata


class ValidationIssue(BaseModel):
    """An issue found during document validation."""
    document_id: str
    severity: str  # "warning" or "error"
    message: str


class ValidationResult(BaseModel):
    """Result of validating a single document."""
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class DocumentStatistics(BaseModel):
    """Build statistics for document generation."""
    
    total_documents: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    avg_length: float = 0.0
    validation: dict[str, int] = Field(default_factory=dict)


class BuildResult(BaseModel):
    """Result of a document generation build."""

    status: str
    started_at: str
    completed_at: str
    duration_seconds: float
    documents_generated: dict[str, int]
    total_documents: int
    validation: dict[str, int]
    errors: list[str]
