"""
Metadata builder utility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.document_generation.schemas import DocumentMetadata
from app.document_generation.utils import safe_str


class MetadataBuilder:
    """Builds structured metadata from query rows."""

    @staticmethod
    def build(
        document_type: str,
        entity_id: int,
        row: dict[str, Any],
        text_length: int = 0,
        section_count: int = 0
    ) -> DocumentMetadata:
        """Extract common metadata fields from a query row."""
        
        now = datetime.now(timezone.utc).isoformat()
        
        return DocumentMetadata(
            document_id=f"{document_type}_{entity_id}",
            document_type=document_type,
            entity_id=entity_id,
            
            # Case fields
            case_id=row.get("CaseMasterID"),
            crime_number=safe_str(row.get("CrimeNo")) or None,
            case_number=safe_str(row.get("CaseNo")) or None,
            
            # Location fields
            district_id=row.get("DistrictID"),
            district_name=safe_str(row.get("DistrictName")) or None,
            police_station_id=row.get("PoliceStationID"),
            police_station_name=safe_str(row.get("UnitName")) or None,
            
            # Classification
            crime_category_id=row.get("CaseCategoryID"),
            major_crime_id=row.get("CrimeMajorHeadID"),
            minor_crime_id=row.get("CrimeMinorHeadID"),
            case_status_id=row.get("CaseStatusID"),
            
            # Temporal
            crime_year=row.get("CrimeYear") or row.get("crime_year"),
            crime_month=row.get("CrimeMonth") or row.get("crime_month"),
            
            # Court/Officer
            court_id=row.get("CourtID"),
            court_name=safe_str(row.get("CourtName")) or None,
            officer_id=row.get("PolicePersonID"),
            
            # Derived
            text_length=text_length,
            section_count=section_count,
            created_at=now,
            updated_at=now
        )
