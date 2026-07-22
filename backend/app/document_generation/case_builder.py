"""
Case Summary Builder.
"""

from __future__ import annotations

import logging

from app.document_generation.base_builder import BaseDocumentBuilder
from app.document_generation.metadata_builder import MetadataBuilder
from app.document_generation.schemas import AIDocument
from app.document_generation.utils import build_sentence, format_date, pluralize, safe_str

logger = logging.getLogger(__name__)


class CaseSummaryBuilder(BaseDocumentBuilder):
    """Generates Case Summary documents."""

    document_type = "case_summary"

    def build_batch(self, offset: int, limit: int) -> list[AIDocument]:
        # Using a subquery approach because one case has many accused/victims.
        # It's cleaner to query the base cases, then fetch the related entities in Python 
        # or aggregate them in SQL. Let's aggregate them in SQL for simplicity.
        
        query = f"""
        SELECT 
            c.*,
            d."DistrictName",
            u."UnitName",
            emp."FirstName" AS "OfficerName",
            emp."KGID" AS "OfficerKGID",
            crt."CourtName",
            
            -- Aggregate Accused
            (SELECT string_agg(a."AccusedName" || ' (Age: ' || COALESCE(a."AgeYear"::text, 'Unknown') || ')', '; ')
             FROM "{self.config.clean_schema}"."clean_Accused" a WHERE a."CaseMasterID" = c."CaseMasterID") AS "AccusedList",
             
            -- Aggregate Victims
            (SELECT string_agg(v."VictimName" || ' (Age: ' || COALESCE(v."AgeYear"::text, 'Unknown') || ')', '; ')
             FROM "{self.config.clean_schema}"."clean_Victim" v WHERE v."CaseMasterID" = c."CaseMasterID") AS "VictimList",
             
            -- Aggregate Complainants
            (SELECT string_agg(comp."ComplainantName", '; ')
             FROM "{self.config.clean_schema}"."clean_ComplainantDetails" comp WHERE comp."CaseMasterID" = c."CaseMasterID") AS "ComplainantList",
             
            -- Aggregate Arrests
            (SELECT count(*)
             FROM "{self.config.clean_schema}"."clean_ArrestSurrender" arr WHERE arr."CaseMasterID" = c."CaseMasterID") AS "ArrestCount",
             
            -- Chargesheet info
            cs."cstype", cs."csdate"
             
        FROM "{self.config.clean_schema}"."clean_CaseMaster" c
        LEFT JOIN "{self.config.clean_schema}"."clean_District" d ON c."DistrictID" = d."DistrictID"
        LEFT JOIN "{self.config.clean_schema}"."clean_Unit" u ON c."PoliceStationID" = u."UnitID"
        LEFT JOIN "{self.config.clean_schema}"."clean_Employee" emp ON c."PolicePersonID" = emp."EmployeeID"
        LEFT JOIN "{self.config.clean_schema}"."clean_Court" crt ON c."CourtID" = crt."CourtID"
        LEFT JOIN "{self.config.clean_schema}"."clean_ChargesheetDetails" cs ON c."CaseMasterID" = cs."CaseMasterID"
        ORDER BY c."CaseMasterID"
        LIMIT :limit OFFSET :offset
        """
        
        rows = self._execute_query(query, {"limit": limit, "offset": offset})
        docs = []
        
        for row in rows:
            try:
                docs.append(self._render_document(row))
            except Exception as e:
                logger.error(f"Failed to render case_summary for {row.get('CaseMasterID')}: {e}")
                
        return docs

    def _render_document(self, row: dict) -> AIDocument:
        entity_id = row["CaseMasterID"]
        crime_no = safe_str(row.get("CrimeNo"))
        case_no = safe_str(row.get("CaseNo"))
        reg_date = format_date(row.get("CrimeRegistered Date"))
        district = safe_str(row.get("DistrictName"), "an unknown district")
        station = safe_str(row.get("UnitName"), "an unknown police station")
        
        sections = []
        
        # 1. Registration Details
        reg_parts = ["This case"]
        if crime_no:
            reg_parts.append(f"(Crime No. {crime_no})")
        elif case_no:
            reg_parts.append(f"(Case No. {case_no})")
            
        reg_parts.append(f"was registered at {station}")
        reg_parts.append(f"in {district}")
        if reg_date:
            reg_parts.append(f"on {reg_date}")
            
        sections.append(build_sentence(reg_parts))
        
        # 2. Investigating Officer
        officer = safe_str(row.get("OfficerName"))
        kgid = safe_str(row.get("OfficerKGID"))
        if officer:
            officer_str = f"The investigating officer is {officer}"
            if kgid:
                officer_str += f" (ID: {kgid})."
            else:
                officer_str += "."
            sections.append(officer_str)
            
        # 3. Persons Involved
        accused = safe_str(row.get("AccusedList"))
        victims = safe_str(row.get("VictimList"))
        complainant = safe_str(row.get("ComplainantList"))
        
        involved = []
        if accused:
            accused_count = len(accused.split(';'))
            involved.append(f"{accused_count} {pluralize(accused_count, 'accused individual has', 'accused individuals have')} been identified: {accused}.")
        if victims:
            victim_count = len(victims.split(';'))
            involved.append(f"There {pluralize(victim_count, 'is', 'are')} {victim_count} identified {pluralize(victim_count, 'victim', 'victims')}: {victims}.")
        if complainant:
            involved.append(f"The complaint was filed by {complainant}.")
            
        if involved:
            sections.append(" ".join(involved))
            
        # 4. Location & Timeline
        from_date = format_date(row.get("IncidentFromDate"))
        to_date = format_date(row.get("IncidentToDate"))
        if from_date and to_date and from_date != to_date:
            sections.append(f"The incident occurred between {from_date} and {to_date}.")
        elif from_date:
            sections.append(f"The incident occurred on or around {from_date}.")
            
        brief_facts = safe_str(row.get("BriefFacts"))
        if brief_facts:
            sections.append(f"Brief facts of the case: {brief_facts}")
            
        # 5. Legal & Arrests
        cs_type = safe_str(row.get("cstype"))
        cs_date = format_date(row.get("csdate"))
        if cs_type or cs_date:
            cs_str = "A chargesheet"
            if cs_type:
                cs_str += f" of type {cs_type}"
            if cs_date:
                cs_str += f" was filed on {cs_date}"
            else:
                cs_str += " was filed"
            sections.append(cs_str + ".")
            
        arrests = row.get("ArrestCount", 0)
        if arrests > 0:
            sections.append(f"There have been {arrests} {pluralize(arrests, 'arrest', 'arrests')} associated with this case.")
            
        court = safe_str(row.get("CourtName"))
        if court:
            sections.append(f"The case is assigned to {court}.")
            
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
