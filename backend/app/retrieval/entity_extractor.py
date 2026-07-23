"""
Entity Extractor for Natural Language Queries.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from app.retrieval.schemas import ExtractedEntities

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts metadata entities from natural language queries."""

    DISTRICTS = [
        "bagalkot", "ballari", "belagavi", "bengaluru", "bengaluru rural", 
        "bidar", "chamarajanagar", "chikkaballapur", "chikkamagaluru", 
        "chitradurga", "dakshina kannada", "davanagere", "dharwad", 
        "gadag", "hassan", "haveri", "kalaburagi", "kodagu", "kolar", 
        "koppal", "mandya", "mysuru", "raichur", "ramanagara", "shivamogga", 
        "tumakuru", "udupi", "uttara kannada", "vijayanagara", "vijayapura", "yadgir"
    ]

    CRIME_TYPES = [
        "theft", "murder", "robbery", "dacoity", "assault", "rape", 
        "kidnapping", "fraud", "cyber", "cheating", "riot", "arson",
        "burglary", "extortion", "dowry", "homicide", "corruption",
        "smuggling", "trafficking", "narcotics", "drugs"
    ]

    DOCUMENT_TYPES = {
        "case": "case_summary",
        "accused": "accused_profile",
        "victim": "victim_profile",
        "officer": "officer_profile",
        "district": "district_summary",
        "court": "court_summary"
    }

    def extract(self, query: str) -> ExtractedEntities:
        """Extract all supported entities from the query."""
        if not query:
            return ExtractedEntities()

        text = query.lower()

        district = self._extract_district(text)
        crime_type = self._extract_crime_type(text)
        year = self._extract_year(text)
        case_numbers = self._extract_case_numbers(text)
        ipc_sections = self._extract_ipc_sections(text)
        names = self._extract_names(text)
        doc_type = self._extract_document_type(text)

        # Build raw entities list for explanations
        raw_entities = []
        if district: raw_entities.append(f"district:{district}")
        if crime_type: raw_entities.append(f"crime_type:{crime_type}")
        if year: raw_entities.append(f"year:{year}")
        if doc_type: raw_entities.append(f"document_type:{doc_type}")
        for cn in case_numbers: raw_entities.append(f"case:{cn}")
        for ipc in ipc_sections: raw_entities.append(f"ipc:{ipc}")
        for name in names: raw_entities.append(f"name:{name}")

        return ExtractedEntities(
            district=district,
            crime_type=crime_type,
            year=year,
            case_numbers=case_numbers,
            ipc_sections=ipc_sections,
            names=names,
            document_type=doc_type,
            raw_entities=raw_entities
        )

    def _extract_district(self, text: str) -> str | None:
        """Match known districts."""
        for dist in self.DISTRICTS:
            if re.search(rf"\b{dist}\b", text):
                return dist.title()
        # Handle Bangalore variant
        if re.search(r"\bbangalore\b", text):
            return "Bengaluru"
        return None

    def _extract_crime_type(self, text: str) -> str | None:
        """Match known crime types."""
        for ctype in self.CRIME_TYPES:
            if re.search(rf"\b{ctype}\b", text):
                return ctype
        return None

    def _extract_year(self, text: str) -> int | None:
        """Extract a 4 digit year between 1990 and 2030."""
        matches = re.findall(r"\b(199[0-9]|20[0-2][0-9]|2030)\b", text)
        if matches:
            return int(matches[0])
        return None

    def _extract_case_numbers(self, text: str) -> list[str]:
        """Extract patterns like 'CR/123/2023' or '123/2023'."""
        patterns = [
            r"\bcr/\d+/\d{4}\b",     # cr/123/2023
            r"\bcrime no\.?\s*\d+\b", # crime no 123
            r"\bfir\s+no\.?\s*\d+\b"  # fir no 123
        ]
        
        results = []
        for p in patterns:
            matches = re.findall(p, text)
            results.extend(matches)
            
        # Optional: just simple digits/digits if Context specifies "case 123/2024"
        generic_case = re.findall(r"\bcase\s+(\d+/\d{4})\b", text)
        results.extend(generic_case)
        
        return list(set(results))

    def _extract_ipc_sections(self, text: str) -> list[str]:
        """Extract IPC sections like '302', '420', '376' if preceded by ipc/section."""
        matches = re.findall(r"\b(?:ipc|section|sec\.?)\s+(\d{3}[A-Za-z]?)\b", text)
        return list(set(matches))

    def _extract_names(self, text: str) -> list[str]:
        """Extract potential names (capitalized words after removing known keywords).
        Since text is already lowercased, this is tricky. We will extract words after 'officer', 'inspector', 'accused', 'victim'.
        """
        names = []
        # Look for names after specific titles
        patterns = [
            r"\b(?:officer|inspector|constable|si|pi)\s+([a-z]+(?:\s+[a-z]+)?)\b",
            r"\b(?:accused|culprit|criminal)\s+([a-z]+(?:\s+[a-z]+)?)\b",
            r"\b(?:victim|complainant)\s+([a-z]+(?:\s+[a-z]+)?)\b"
        ]
        
        for p in patterns:
            matches = re.findall(p, text)
            for m in matches:
                # Filter out generic words
                if m not in ["in", "at", "the", "a", "an", "is", "was", "for", "of"]:
                    names.append(m.title())
                    
        return list(set(names))

    def _extract_document_type(self, text: str) -> str | None:
        """Map query intents to document types."""
        for keyword, doc_type in self.DOCUMENT_TYPES.items():
            if re.search(rf"\b{keyword}(?:s)?\b", text):
                return doc_type
        return None
