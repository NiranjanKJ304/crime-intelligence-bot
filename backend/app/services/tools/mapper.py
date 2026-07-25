"""
Dynamic column mapping for PostgreSQL tools.

Retrieves actual physical column names from the database schema 
by matching logical patterns to avoid hardcoded column names.
"""

from __future__ import annotations

import logging
from typing import Any
from sqlalchemy import text
from app.core.database import get_engine
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ColumnMapper:
    """Maps logical identifiers to physical schema columns."""
    
    _instance: ColumnMapper | None = None
    
    def __init__(self):
        self.settings = get_settings()
        self.schema = self.settings.clean_schema
        self.engine = get_engine()
        self._mappings: dict[str, dict[str, str]] = {}
        
        # Define logical patterns to search for in specific tables
        self.patterns = {
            "clean_CaseMaster": {
                "case_id": ["casemasterid", "case_id", "id"],
                "case_number": ["caseno", "case_no", "casenumber", "case_number"],
                "crime_number": ["crimeno", "firno", "crime_number", "fir_number", "crimenumber"],
                "station_id": ["policestationid", "stationid", "station_id", "unitid"],
                "officer_id": ["policepersonid", "employeeid", "officerid", "io_id"],
                "status": ["status", "casestatus"],
            },
            "clean_Employee": {
                "officer_id": ["employeeid", "officerid", "policepersonid", "id"],
                "name": ["name", "employeename", "officername", "policepersonname"],
                "kgid": ["kgid", "kgid_no"],
                "designation": ["designation"],
                "rank": ["rank"],
            },
            "clean_Victim": {
                "victim_id": ["victimmasterid", "victimid", "id"],
                "case_id": ["casemasterid", "case_id"],
                "name": ["victimname", "name"],
                "age": ["age"],
                "gender": ["sex", "gender"],
            },
            "clean_Accused": {
                "accused_id": ["accusedmasterid", "accusedid", "id"],
                "case_id": ["casemasterid", "case_id"],
                "name": ["accusedname", "name"],
                "age": ["age"],
                "gender": ["sex", "gender"],
            },
            "clean_ComplainantDetails": {
                "complainant_id": ["complainantid", "id"],
                "case_id": ["casemasterid", "case_id"],
            },
            "clean_ArrestSurrender": {
                "case_id": ["casemasterid", "case_id"],
            },
            "clean_ChargesheetDetails": {
                "case_id": ["casemasterid", "case_id"],
                "date": ["csdate", "date", "chargesheetdate"],
                "court_name": ["courtname", "court", "court_name"],
            },
            "clean_ActSectionAssociation": {
                "case_id": ["casemasterid", "case_id"],
            }
        }
    
    @classmethod
    def get_instance(cls) -> ColumnMapper:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self) -> None:
        """Fetch columns from DB and build exact mappings."""
        logger.info(f"[MAPPER] Initializing column mappings for schema: {self.schema}")
        
        query = text("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE table_schema = :schema
        """)
        
        schema_columns = {}
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query, {"schema": self.schema})
                for row in result:
                    t_name = row[0]
                    c_name = row[1]
                    if t_name not in schema_columns:
                        schema_columns[t_name] = []
                    schema_columns[t_name].append(c_name)
        except Exception as e:
            logger.error(f"[MAPPER] Failed to query information_schema: {e}")
            raise RuntimeError(f"Database error during mapper initialization: {e}")
            
        for table, logical_maps in self.patterns.items():
            self._mappings[table] = {}
            actual_columns = schema_columns.get(table, [])
            
            if not actual_columns:
                logger.warning(f"[MAPPER] Table {table} not found in schema {self.schema}")
                continue
                
            actual_lower = {c.lower(): c for c in actual_columns}
            
            for logical_name, pattern_list in logical_maps.items():
                match_found = False
                for pattern in pattern_list:
                    if pattern in actual_lower:
                        physical_name = actual_lower[pattern]
                        self._mappings[table][logical_name] = physical_name
                        logger.debug(f"[MAPPER] Mapped {table}.{logical_name} -> {physical_name}")
                        match_found = True
                        break
                
                if not match_found:
                    msg = f"Failed to map logical column '{logical_name}' for table '{table}'."
                    logger.error(f"[MAPPER] {msg}")
                    raise RuntimeError(msg)

        logger.info("[MAPPER] Initialization complete. All required columns mapped successfully.")

    def get_column(self, table: str, logical_name: str) -> str:
        """Get the physical column name for a logical identifier."""
        if table not in self._mappings or logical_name not in self._mappings[table]:
            raise ValueError(f"Mapping not found for {table}.{logical_name}")
        return self._mappings[table][logical_name]
