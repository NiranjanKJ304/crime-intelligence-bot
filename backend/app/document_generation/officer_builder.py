"""
Officer Profile Builder.
"""

from __future__ import annotations

import logging

from app.document_generation.base_builder import BaseDocumentBuilder
from app.document_generation.metadata_builder import MetadataBuilder
from app.document_generation.schemas import AIDocument
from app.document_generation.utils import build_sentence, safe_str, pluralize

logger = logging.getLogger(__name__)


class OfficerProfileBuilder(BaseDocumentBuilder):
    """Generates Officer Profile documents."""

    document_type = "officer_profile"

    def build_batch(self, offset: int, limit: int) -> list[AIDocument]:
        query = f"""
        SELECT 
            e.*,
            d."DistrictName",
            u."UnitName",
            
            -- Aggregations
            (SELECT count(*) FROM "{self.config.clean_schema}"."clean_CaseMaster" c 
             WHERE c."PolicePersonID" = e."EmployeeID") AS "InvestigatedCases",
             
            (SELECT count(*) FROM "{self.config.clean_schema}"."clean_ChargesheetDetails" cs 
             WHERE cs."PolicePersonID" = e."EmployeeID") AS "ChargesheetsFiled"
             
        FROM "{self.config.clean_schema}"."clean_Employee" e
        LEFT JOIN "{self.config.clean_schema}"."clean_District" d ON e."DistrictID" = d."DistrictID"
        LEFT JOIN "{self.config.clean_schema}"."clean_Unit" u ON e."UnitID" = u."UnitID"
        ORDER BY e."EmployeeID"
        LIMIT :limit OFFSET :offset
        """
        
        rows = self._execute_query(query, {"limit": limit, "offset": offset})
        docs = []
        
        for row in rows:
            try:
                docs.append(self._render_document(row))
            except Exception as e:
                logger.error(f"Failed to render officer_profile for {row.get('EmployeeID')}: {e}")
                
        return docs

    def _render_document(self, row: dict) -> AIDocument:
        entity_id = row["EmployeeID"]
        name = safe_str(row.get("FirstName"), "An officer")
        kgid = safe_str(row.get("KGID"))
        district = safe_str(row.get("DistrictName"))
        unit = safe_str(row.get("UnitName"))
        
        sections = []
        
        # 1. Identity & Assignment
        intro = [name]
        if kgid:
            intro.append(f"(KGID: {kgid})")
        intro.append("is a law enforcement officer")
        
        if unit:
            intro.append(f"currently assigned to {unit}")
        if district:
            intro.append(f"in {district}")
            
        sections.append(build_sentence(intro))
        
        # 2. Caseload
        cases = row.get("InvestigatedCases", 0)
        cs_filed = row.get("ChargesheetsFiled", 0)
        
        if cases > 0 or cs_filed > 0:
            caseload = []
            if cases > 0:
                caseload.append(f"has been assigned to investigate {cases} {pluralize(cases, 'case', 'cases')}")
            if cs_filed > 0:
                if cases > 0:
                    caseload.append("and")
                caseload.append(f"has filed {cs_filed} {pluralize(cs_filed, 'chargesheet', 'chargesheets')}")
                
            sections.append(f"This officer " + " ".join(caseload) + " during their service.")
            
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
