"""
Accused Profile Builder.
"""

from __future__ import annotations

import logging

from app.document_generation.base_builder import BaseDocumentBuilder
from app.document_generation.metadata_builder import MetadataBuilder
from app.document_generation.schemas import AIDocument
from app.document_generation.utils import build_sentence, safe_str, pluralize

logger = logging.getLogger(__name__)


class AccusedProfileBuilder(BaseDocumentBuilder):
    """Generates Accused Profile documents."""

    document_type = "accused_profile"

    def build_batch(self, offset: int, limit: int) -> list[AIDocument]:
        query = f"""
        SELECT 
            a.*,
            c."CrimeNo",
            d."DistrictName",
            u."UnitName",
            
            -- Arrest info
            (SELECT count(*) FROM "{self.config.clean_schema}"."clean_ArrestSurrender" arr 
             WHERE arr."AccusedMasterID" = a."AccusedMasterID") AS "ArrestCount"
             
        FROM "{self.config.clean_schema}"."clean_Accused" a
        LEFT JOIN "{self.config.clean_schema}"."clean_CaseMaster" c ON a."CaseMasterID" = c."CaseMasterID"
        LEFT JOIN "{self.config.clean_schema}"."clean_District" d ON c."DistrictID" = d."DistrictID"
        LEFT JOIN "{self.config.clean_schema}"."clean_Unit" u ON c."PoliceStationID" = u."UnitID"
        ORDER BY a."AccusedMasterID"
        LIMIT :limit OFFSET :offset
        """
        
        rows = self._execute_query(query, {"limit": limit, "offset": offset})
        docs = []
        
        for row in rows:
            try:
                docs.append(self._render_document(row))
            except Exception as e:
                logger.error(f"Failed to render accused_profile for {row.get('AccusedMasterID')}: {e}")
                
        return docs

    def _render_document(self, row: dict) -> AIDocument:
        entity_id = row["AccusedMasterID"]
        name = safe_str(row.get("AccusedName"), "An unnamed individual")
        age = row.get("AgeYear")
        
        sections = []
        
        # 1. Personal Info
        intro_parts = [f"{name}"]
        if age:
            intro_parts.append(f"is a {age}-year-old accused person")
        else:
            intro_parts.append("is an accused person")
            
        sections.append(build_sentence(intro_parts))
        
        # 2. Case Involvement
        crime_no = safe_str(row.get("CrimeNo"))
        district = safe_str(row.get("DistrictName"))
        station = safe_str(row.get("UnitName"))
        
        if crime_no or district or station:
            case_parts = ["They are associated with"]
            if crime_no:
                case_parts.append(f"Crime No. {crime_no}")
            else:
                case_parts.append("a registered case")
                
            if station:
                case_parts.append(f"at {station}")
            if district:
                case_parts.append(f"in {district}")
                
            sections.append(build_sentence(case_parts))
            
        # 3. Arrests
        arrests = row.get("ArrestCount", 0)
        if arrests > 0:
            sections.append(f"Records indicate {arrests} prior {pluralize(arrests, 'arrest', 'arrests')} or surrender events for this individual.")
            
        text = "\n\n".join(sections)
        
        # Map back to standard metadata
        row["DistrictID"] = row.get("DistrictID") # From JOIN if available, else null
        
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
