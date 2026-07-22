"""
Cypher queries for merging nodes.
Each query expects a parameter `$batch` containing a list of dictionaries.
"""

from __future__ import annotations

# MERGE is used with ON CREATE SET to define properties only once 
# and ON MATCH SET (if needed for updates). Here we use simple MERGE + SET 
# for full batch updates.

MERGE_DISTRICT_NODES = """
UNWIND $batch AS row
MERGE (n:District {DistrictID: row.DistrictID})
SET n += row
"""

MERGE_UNIT_NODES = """
UNWIND $batch AS row
MERGE (n:Unit {UnitID: row.UnitID})
SET n += row
"""

MERGE_COURT_NODES = """
UNWIND $batch AS row
MERGE (n:Court {CourtID: row.CourtID})
SET n += row
"""

MERGE_EMPLOYEE_NODES = """
UNWIND $batch AS row
MERGE (n:Employee {EmployeeID: row.EmployeeID})
SET n += row
"""

MERGE_CASE_NODES = """
UNWIND $batch AS row
MERGE (n:Case {CaseMasterID: row.CaseMasterID})
SET n += row
"""

MERGE_COMPLAINANT_NODES = """
UNWIND $batch AS row
MERGE (n:Complainant {ComplainantID: row.ComplainantID})
SET n += row
"""

MERGE_VICTIM_NODES = """
UNWIND $batch AS row
MERGE (n:Victim {VictimMasterID: row.VictimMasterID})
SET n += row
"""

MERGE_ACCUSED_NODES = """
UNWIND $batch AS row
MERGE (n:Accused {AccusedMasterID: row.AccusedMasterID})
SET n += row
"""

MERGE_ACTSECTION_NODES = """
UNWIND $batch AS row
MERGE (n:ActSection {ActID: row.ActID, SectionID: row.SectionID})
SET n += row
"""

MERGE_CHARGESHEET_NODES = """
UNWIND $batch AS row
MERGE (n:Chargesheet {CSID: row.CSID})
SET n += row
"""

MERGE_ARREST_NODES = """
UNWIND $batch AS row
MERGE (n:Arrest {ArrestSurrenderID: row.ArrestSurrenderID})
SET n += row
"""

# Mapping dictionary for easy access in loader
NODE_QUERIES = {
    "clean_District": MERGE_DISTRICT_NODES,
    "clean_Unit": MERGE_UNIT_NODES,
    "clean_Court": MERGE_COURT_NODES,
    "clean_Employee": MERGE_EMPLOYEE_NODES,
    "clean_CaseMaster": MERGE_CASE_NODES,
    "clean_ComplainantDetails": MERGE_COMPLAINANT_NODES,
    "clean_Victim": MERGE_VICTIM_NODES,
    "clean_Accused": MERGE_ACCUSED_NODES,
    "clean_ActSectionAssociation": MERGE_ACTSECTION_NODES,
    "clean_ChargesheetDetails": MERGE_CHARGESHEET_NODES,
    "clean_ArrestSurrender": MERGE_ARREST_NODES,
}
