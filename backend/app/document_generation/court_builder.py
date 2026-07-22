"""
Court Summary Builder.
"""

from __future__ import annotations

import logging

from app.document_generation.base_builder import BaseDocumentBuilder
from app.document_generation.metadata_builder import MetadataBuilder
from app.document_generation.schemas import AIDocument
from app.document_generation.utils import safe_str, pluralize

logger = logging.getLogger(__name__)


class CourtSummaryBuilder(BaseDocumentBuilder):
    """Generates Court Summary documents."""

    document_type = "court_summary"

    def build_batch(self, offset: int, limit: int) -> list[AIDocument]:
        query = f"""
        SELECT 
            crt.*,
            d."DistrictName",
            (SELECT count(*) FROM "{self.config.clean_schema}"."clean_CaseMaster" c WHERE c."CourtID" = crt."CourtID") AS "CaseCount",
            (SELECT count(*) FROM "{self.config.clean_schema}"."clean_ArrestSurrender" a WHERE a."CourtID" = crt."CourtID") AS "ProductionCount"
        FROM "{self.config.clean_schema}"."clean_Court" crt
        LEFT JOIN "{self.config.clean_schema}"."clean_District" d ON crt."DistrictID" = d."DistrictID"
        ORDER BY crt."CourtID"
        LIMIT :limit OFFSET :offset
        """
        
        rows = self._execute_query(query, {"limit": limit, "offset": offset})
        docs = []
        
        for row in rows:
            try:
                docs.append(self._render_document(row))
            except Exception as e:
                logger.error(f"Failed to render court_summary for {row.get('CourtID')}: {e}")
                
        return docs

    def _render_document(self, row: dict) -> AIDocument:
        entity_id = row["CourtID"]
        name = safe_str(row.get("CourtName"), "Unknown Court")
        district = safe_str(row.get("DistrictName"))
        cases = row.get("CaseCount", 0)
        prods = row.get("ProductionCount", 0)
        
        sections = []
        
        intro = f"{name} is a judicial court"
        if district:
            intro += f" operating in the district of {district}"
        sections.append(intro + ".")
        
        if cases > 0:
            sections.append(f"It is currently assigned {cases} active or closed {pluralize(cases, 'case', 'cases')}.")
            
        if prods > 0:
            sections.append(f"Records indicate {prods} accused {pluralize(prods, 'person has', 'persons have')} been produced before this court.")
            
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
