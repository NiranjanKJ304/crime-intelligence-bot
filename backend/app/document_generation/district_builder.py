"""
District Summary Builder.
"""

from __future__ import annotations

import logging

from app.document_generation.base_builder import BaseDocumentBuilder
from app.document_generation.metadata_builder import MetadataBuilder
from app.document_generation.schemas import AIDocument
from app.document_generation.utils import safe_str, pluralize

logger = logging.getLogger(__name__)


class DistrictSummaryBuilder(BaseDocumentBuilder):
    """Generates District Summary documents."""

    document_type = "district_summary"

    def build_batch(self, offset: int, limit: int) -> list[AIDocument]:
        # Using LEFT JOIN from District to Unit and CaseMaster and aggregating
        query = f"""
        SELECT 
            d.*,
            (SELECT count(*) FROM "{self.config.clean_schema}"."clean_Unit" u WHERE u."DistrictID" = d."DistrictID") AS "UnitCount",
            (SELECT count(*) FROM "{self.config.clean_schema}"."clean_CaseMaster" c JOIN "{self.config.clean_schema}"."clean_Unit" cu ON c."PoliceStationID" = cu."UnitID" WHERE cu."DistrictID" = d."DistrictID") AS "CaseCount"
        FROM "{self.config.clean_schema}"."clean_District" d
        ORDER BY d."DistrictID"
        LIMIT :limit OFFSET :offset
        """
        
        rows = self._execute_query(query, {"limit": limit, "offset": offset})
        docs = []
        
        for row in rows:
            try:
                docs.append(self._render_document(row))
            except Exception as e:
                logger.error(f"Failed to render district_summary for {row.get('DistrictID')}: {e}")
                
        return docs

    def _render_document(self, row: dict) -> AIDocument:
        entity_id = row["DistrictID"]
        name = safe_str(row.get("DistrictName"), "Unknown District")
        units = row.get("UnitCount", 0)
        cases = row.get("CaseCount", 0)
        
        sections = []
        
        sections.append(f"{name} is an administrative district within the state.")
        
        if units > 0:
            sections.append(f"It oversees {units} police {pluralize(units, 'unit or station', 'units or stations')}.")
            
        if cases > 0:
            sections.append(f"A total of {cases} {pluralize(cases, 'case has', 'cases have')} been registered in this district.")
            
        text = "\n\n".join(sections)
        
        metadata = MetadataBuilder.build(
            document_type=self.document_type,
            entity_id=entity_id,
            row=row,
            text_length=len(text),
            section_count=len(sections)
        )
        
        return AIDocument(
            document_id=metadata.document_id,
            document_type=metadata.document_type,
            text=text,
            metadata=metadata
        )
