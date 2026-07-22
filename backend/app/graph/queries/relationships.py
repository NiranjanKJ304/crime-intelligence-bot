"""
Cypher queries for merging relationships.
Each query expects a parameter `$batch` containing a list of dictionaries.
"""

from __future__ import annotations

# We MATCH on the indexed properties (which were constrained as unique in schema_manager)
# and then MERGE the relationships.

# --- District/Unit/Court Relationships ---
MERGE_UNIT_DISTRICT = """
UNWIND $batch AS row
MATCH (u:Unit {UnitID: row.UnitID})
MATCH (d:District {DistrictID: row.DistrictID})
MERGE (d)-[:HAS_UNIT]->(u)
"""

MERGE_COURT_DISTRICT = """
UNWIND $batch AS row
MATCH (c:Court {CourtID: row.CourtID})
MATCH (d:District {DistrictID: row.DistrictID})
MERGE (d)-[:HAS_COURT]->(c)
"""

# --- Employee Relationships ---
MERGE_EMPLOYEE_UNIT = """
UNWIND $batch AS row
MATCH (e:Employee {EmployeeID: row.EmployeeID})
MATCH (u:Unit {UnitID: row.UnitID})
MERGE (u)-[:HAS_EMPLOYEE]->(e)
"""

MERGE_EMPLOYEE_DISTRICT = """
UNWIND $batch AS row
MATCH (e:Employee {EmployeeID: row.EmployeeID})
MATCH (d:District {DistrictID: row.DistrictID})
MERGE (e)-[:WORKS_IN]->(d)
"""

# --- Case Relationships ---
MERGE_CASE_UNIT = """
UNWIND $batch AS row
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MATCH (u:Unit {UnitID: row.PoliceStationID})
MERGE (c)-[:REGISTERED_AT]->(u)
"""

MERGE_CASE_COURT = """
UNWIND $batch AS row
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MATCH (court:Court {CourtID: row.CourtID})
MERGE (c)-[:HEARD_IN]->(court)
"""

MERGE_CASE_EMPLOYEE_IO = """
UNWIND $batch AS row
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MATCH (e:Employee {EmployeeID: row.PolicePersonID})
MERGE (e)-[:INVESTIGATES]->(c)
"""

MERGE_CASE_ACCUSED = """
UNWIND $batch AS row
MATCH (a:Accused {AccusedMasterID: row.AccusedMasterID})
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MERGE (c)-[:HAS_ACCUSED]->(a)
"""

MERGE_CASE_VICTIM = """
UNWIND $batch AS row
MATCH (v:Victim {VictimMasterID: row.VictimMasterID})
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MERGE (c)-[:HAS_VICTIM]->(v)
"""

MERGE_CASE_COMPLAINANT = """
UNWIND $batch AS row
MATCH (comp:Complainant {ComplainantID: row.ComplainantID})
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MERGE (c)-[:HAS_COMPLAINANT]->(comp)
"""

MERGE_CASE_ACTSECTION = """
UNWIND $batch AS row
MATCH (assoc:ActSection {ActID: row.ActID, SectionID: row.SectionID})
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MERGE (c)-[:HAS_SECTION]->(assoc)
"""

# --- Chargesheet Relationships ---
MERGE_CASE_CHARGESHEET = """
UNWIND $batch AS row
MATCH (cs:Chargesheet {CSID: row.CSID})
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MERGE (c)-[:HAS_CHARGESHEET]->(cs)
"""

MERGE_CHARGESHEET_EMPLOYEE = """
UNWIND $batch AS row
MATCH (cs:Chargesheet {CSID: row.CSID})
MATCH (e:Employee {EmployeeID: row.PolicePersonID})
MERGE (e)-[:FILES_CHARGESHEET]->(cs)
"""

# --- Arrest Relationships ---
MERGE_CASE_ARREST = """
UNWIND $batch AS row
MATCH (arr:Arrest {ArrestSurrenderID: row.ArrestSurrenderID})
MATCH (c:Case {CaseMasterID: row.CaseMasterID})
MERGE (c)-[:HAS_ARREST]->(arr)
"""

MERGE_ARREST_ACCUSED = """
UNWIND $batch AS row
MATCH (arr:Arrest {ArrestSurrenderID: row.ArrestSurrenderID})
MATCH (a:Accused {AccusedMasterID: row.AccusedMasterID})
MERGE (arr)-[:ARRESTED_PERSON]->(a)
"""

MERGE_ARREST_EMPLOYEE = """
UNWIND $batch AS row
MATCH (arr:Arrest {ArrestSurrenderID: row.ArrestSurrenderID})
MATCH (e:Employee {EmployeeID: row.IOID})
MERGE (e)-[:MADE_ARREST]->(arr)
"""

MERGE_ARREST_COURT = """
UNWIND $batch AS row
MATCH (arr:Arrest {ArrestSurrenderID: row.ArrestSurrenderID})
MATCH (court:Court {CourtID: row.CourtID})
MERGE (arr)-[:PRODUCED_IN]->(court)
"""


RELATIONSHIP_QUERIES = {
    # District/Unit/Court
    "clean_Unit:HAS_UNIT": MERGE_UNIT_DISTRICT,
    "clean_Court:HAS_COURT": MERGE_COURT_DISTRICT,
    "clean_Employee:HAS_EMPLOYEE": MERGE_EMPLOYEE_UNIT,
    "clean_Employee:WORKS_IN": MERGE_EMPLOYEE_DISTRICT,
    
    # CaseMaster
    "clean_CaseMaster:REGISTERED_AT": MERGE_CASE_UNIT,
    "clean_CaseMaster:HEARD_IN": MERGE_CASE_COURT,
    "clean_CaseMaster:INVESTIGATES": MERGE_CASE_EMPLOYEE_IO,
    
    # Entity-to-Case
    "clean_Accused:HAS_ACCUSED": MERGE_CASE_ACCUSED,
    "clean_Victim:HAS_VICTIM": MERGE_CASE_VICTIM,
    "clean_ComplainantDetails:HAS_COMPLAINANT": MERGE_CASE_COMPLAINANT,
    "clean_ActSectionAssociation:HAS_SECTION": MERGE_CASE_ACTSECTION,
    
    # Chargesheet
    "clean_ChargesheetDetails:HAS_CHARGESHEET": MERGE_CASE_CHARGESHEET,
    "clean_ChargesheetDetails:FILES_CHARGESHEET": MERGE_CHARGESHEET_EMPLOYEE,
    
    # Arrest
    "clean_ArrestSurrender:HAS_ARREST": MERGE_CASE_ARREST,
    "clean_ArrestSurrender:ARRESTED_PERSON": MERGE_ARREST_ACCUSED,
    "clean_ArrestSurrender:MADE_ARREST": MERGE_ARREST_EMPLOYEE,
    "clean_ArrestSurrender:PRODUCED_IN": MERGE_ARREST_COURT,
}
