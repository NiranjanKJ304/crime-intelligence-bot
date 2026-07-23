"""
Neo4j Graph Search for the Enterprise Retrieval Engine.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.neo4j_db import get_neo4j_driver
from app.retrieval.schemas import ExtractedEntities, GraphResult

logger = logging.getLogger(__name__)


class GraphSearch:
    """Executes Cypher queries against Neo4j to augment semantic search."""

    def __init__(self):
        self.driver = get_neo4j_driver()

    def search_by_entities(self, entities: ExtractedEntities) -> list[GraphResult]:
        """Dynamically search the graph based on extracted entities."""
        results = []
        
        with self.driver.session() as session:
            # 1. District/Court search
            if entities.district:
                cypher = """
                MATCH (d:District {DistrictName: $district})
                OPTIONAL MATCH (d)-[:HAS_COURT]->(c:Court)
                OPTIONAL MATCH (d)-[:HAS_UNIT]->(u:Unit)
                RETURN d.DistrictName AS District, collect(DISTINCT c.CourtName)[..3] AS Courts, 
                       collect(DISTINCT u.UnitName)[..3] AS Units
                """
                res = session.run(cypher, district=entities.district)
                for record in res:
                    results.append(GraphResult(
                        node=f"District: {record['District']}",
                        relationship="HAS_COURT/UNIT",
                        connected_to=f"{len(record['Courts'])} Courts, {len(record['Units'])} Units"
                    ))
            
            # 2. Name search (Officer/Accused/Victim)
            if entities.names:
                for name in entities.names:
                    # Officer
                    cypher_off = """
                    MATCH (e:Employee)-[:INVESTIGATES]->(c:Case)
                    WHERE toLower(e.EmployeeName) CONTAINS toLower($name) 
                       OR toLower(e.FirstName) CONTAINS toLower($name)
                    RETURN e.EmployeeName AS Name, count(c) AS CaseCount
                    LIMIT 3
                    """
                    for record in session.run(cypher_off, name=name):
                        results.append(GraphResult(
                            node=f"Officer: {record['Name']}",
                            relationship="INVESTIGATES",
                            connected_to=f"{record['CaseCount']} Cases"
                        ))
                    
                    # Accused
                    cypher_acc = """
                    MATCH (a:Accused)<-[:HAS_ACCUSED]-(c:Case)
                    WHERE toLower(a.AccusedName) CONTAINS toLower($name)
                    RETURN a.AccusedName AS Name, count(c) AS CaseCount
                    LIMIT 3
                    """
                    for record in session.run(cypher_acc, name=name):
                        results.append(GraphResult(
                            node=f"Accused: {record['Name']}",
                            relationship="INVOLVED_IN",
                            connected_to=f"{record['CaseCount']} Cases"
                        ))

            # 3. Specific Case Numbers
            if entities.case_numbers:
                for cn in entities.case_numbers:
                    # Very basic exact match on CaseMasterID or FIRNo, often needs normalization
                    cypher_case = """
                    MATCH (c:Case)
                    WHERE c.CaseMasterID = $cn OR c.FIRNo CONTAINS $cn
                    OPTIONAL MATCH (c)-[:HAS_ACCUSED]->(a:Accused)
                    RETURN c.CaseMasterID AS CaseID, collect(a.AccusedName)[..3] AS Accused
                    LIMIT 3
                    """
                    for record in session.run(cypher_case, cn=cn):
                        results.append(GraphResult(
                            node=f"Case: {record['CaseID']}",
                            relationship="HAS_ACCUSED",
                            connected_to=", ".join(record['Accused']) if record['Accused'] else "Unknown"
                        ))

            # 4. IPC Sections
            if entities.ipc_sections:
                for ipc in entities.ipc_sections:
                    cypher_ipc = """
                    MATCH (act:ActSection)<-[:HAS_SECTION]-(c:Case)
                    WHERE act.SectionID = $ipc OR act.SectionID CONTAINS $ipc
                    RETURN act.SectionID AS Section, count(c) AS CaseCount
                    LIMIT 3
                    """
                    for record in session.run(cypher_ipc, ipc=ipc):
                        results.append(GraphResult(
                            node=f"IPC Section: {record['Section']}",
                            relationship="APPLIED_IN",
                            connected_to=f"{record['CaseCount']} Cases"
                        ))

        return results

    def find_connected_accused(self, case_id: str) -> list[GraphResult]:
        """Find other cases where the accused in this case was involved."""
        cypher = """
        MATCH (c1:Case {CaseMasterID: $case_id})-[:HAS_ACCUSED]->(a:Accused)<-[:HAS_ACCUSED]-(c2:Case)
        WHERE c1 <> c2
        RETURN a.AccusedName AS Accused, c2.CaseMasterID AS OtherCase
        LIMIT 5
        """
        results = []
        with self.driver.session() as session:
            for record in session.run(cypher, case_id=case_id):
                results.append(GraphResult(
                    node=f"Accused: {record['Accused']}",
                    relationship="ALSO_INVOLVED_IN",
                    connected_to=f"Case: {record['OtherCase']}"
                ))
        return results
