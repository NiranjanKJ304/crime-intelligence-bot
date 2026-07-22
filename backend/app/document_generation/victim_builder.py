"""
Victim Profile Builder.
"""

from __future__ import annotations

import logging

from app.document_generation.base_builder import BaseDocumentBuilder
from app.document_generation.metadata_builder import MetadataBuilder
from app.document_generation.schemas import AIDocument
from app.document_generation.utils import build_sentence, safe_str

logger = logging.getLogger(__name__)


class VictimProfileBuilder(BaseDocumentBuilder):
    """Generates Victim Profile documents."""

    document_type = "victim_profile"

    def build_batch(self, offset: int, limit: int) -> list[AIDocument]:
        query = f"""
        SELECT 
            v.*,
            c."CrimeNo",
            d."DistrictName",
            u."UnitName"
             
        FROM "{self.config.clean_schema}"."clean_Victim" v
        LEFT JOIN "{self.config.clean_schema}"."clean_CaseMaster" c ON v."CaseMasterID" = c."CaseMasterID"
        LEFT JOIN "{self.config.clean_schema}"."clean_Unit" u ON c."PoliceStationID" = u."UnitID"
        LEFT JOIN "{self.config.clean_schema}"."clean_District" d ON u."DistrictID" = d."DistrictID"
        ORDER BY v."VictimMasterID"
        LIMIT :limit OFFSET :offset
        """
        
        rows = self._execute_query(query, {"limit": limit, "offset": offset})
        docs = []
        
        for row in rows:
            try:
                docs.append(self._render_document(row))
            except Exception as e:
                logger.error(f"Failed to render victim_profile for {row.get('VictimMasterID')}: {e}")
                
        return docs

    def _render_document(self, row: dict) -> AIDocument:
        entity_id = row["VictimMasterID"]
        name = safe_str(row.get("VictimName"), "An unnamed individual")
        age = row.get("AgeYear")
        
        sections = []
        
        # 1. Personal Info
        intro_parts = [f"{name}"]
        if age:
            intro_parts.append(f"is a {age}-year-old victim")
        else:
            intro_parts.append("is a victim")
            
        sections.append(build_sentence(intro_parts))
        
        # 2. Case Involvement
        crime_no = safe_str(row.get("CrimeNo"))
        district = safe_str(row.get("DistrictName"))
        station = safe_str(row.get("UnitName"))
        
        if crime_no or district or station:
            case_parts = ["They are listed as a victim in"]
            if crime_no:
                case_parts.append(f"Crime No. {crime_no}")
            else:
                case_parts.append("a registered case")
                
            if station:
                case_parts.append(f"at {station}")
            if district:
                case_parts.append(f"in {district}")
                
            sections.append(build_sentence(case_parts))
            
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
