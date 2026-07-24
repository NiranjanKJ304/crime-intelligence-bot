"""
Neo4j Tool Functions.

Parameterised Cypher queries for relationship-based lookups.
Each function is a pre-defined operation — the LLM never generates Cypher.
Gracefully returns empty results if Neo4j is offline.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _run_cypher(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a Cypher query and return results as dicts. Handles Neo4j being offline."""
    try:
        from app.core.neo4j_db import get_neo4j_driver
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]
    except Exception as e:
        logger.warning(f"Neo4j query failed (may be offline): {e}")
        return []


def find_related_accused(accused_id: int) -> list[dict[str, Any]]:
    """Find cases that share the same accused person."""
    return _run_cypher(
        """
        MATCH (a:Accused {AccusedMasterID: $aid})<-[:HAS_ACCUSED]-(c:Case)
        RETURN c.CaseMasterID AS case_id, c.CrimeNumber AS crime_number,
               c.CrimeType AS crime_type, c.Status AS status
        LIMIT 20
        """,
        {"aid": accused_id},
    )


def find_officer_cases(officer_id: int) -> list[dict[str, Any]]:
    """Find all cases investigated by a specific officer."""
    return _run_cypher(
        """
        MATCH (e:Employee {EmployeeID: $oid})-[:INVESTIGATES]->(c:Case)
        RETURN c.CaseMasterID AS case_id, c.CrimeNumber AS crime_number,
               c.CrimeType AS crime_type, c.Status AS status
        ORDER BY c.CaseMasterID
        LIMIT 50
        """,
        {"oid": officer_id},
    )


def find_co_accused(case_id: int) -> list[dict[str, Any]]:
    """Find all accused persons on the same case."""
    return _run_cypher(
        """
        MATCH (c:Case {CaseMasterID: $cid})-[:HAS_ACCUSED]->(a:Accused)
        RETURN a.AccusedMasterID AS accused_id, a.AccusedName AS name,
               a.Age AS age, a.Sex AS sex
        """,
        {"cid": case_id},
    )


def find_related_victims(case_id: int) -> list[dict[str, Any]]:
    """Find all victims associated with a case."""
    return _run_cypher(
        """
        MATCH (c:Case {CaseMasterID: $cid})-[:HAS_VICTIM]->(v:Victim)
        RETURN v.VictimMasterID AS victim_id, v.VictimName AS name,
               v.Age AS age, v.Sex AS sex
        """,
        {"cid": case_id},
    )


def find_case_network(case_id: int) -> list[dict[str, Any]]:
    """Find the full neighbourhood of a case (accused, victims, officer, station)."""
    return _run_cypher(
        """
        MATCH (c:Case {CaseMasterID: $cid})
        OPTIONAL MATCH (c)-[:HAS_ACCUSED]->(a:Accused)
        OPTIONAL MATCH (c)-[:HAS_VICTIM]->(v:Victim)
        OPTIONAL MATCH (e:Employee)-[:INVESTIGATES]->(c)
        OPTIONAL MATCH (c)-[:REGISTERED_AT]->(u:Unit)
        RETURN c.CaseMasterID AS case_id,
               c.CrimeNumber AS crime_number,
               collect(DISTINCT {id: a.AccusedMasterID, name: a.AccusedName}) AS accused,
               collect(DISTINCT {id: v.VictimMasterID, name: v.VictimName}) AS victims,
               collect(DISTINCT {id: e.EmployeeID, name: e.EmployeeName}) AS officers,
               collect(DISTINCT {id: u.UnitID, name: u.UnitName}) AS stations
        """,
        {"cid": case_id},
    )


def get_case_timeline(case_id: int) -> list[dict[str, Any]]:
    """Get chronological events for a case (arrests, chargesheets)."""
    return _run_cypher(
        """
        MATCH (c:Case {CaseMasterID: $cid})
        OPTIONAL MATCH (c)-[:HAS_ARREST]->(arr:Arrest)
        OPTIONAL MATCH (c)-[:HAS_CHARGESHEET]->(cs:Chargesheet)
        RETURN c.CaseMasterID AS case_id,
               collect(DISTINCT {type: 'arrest', id: arr.ArrestSurrenderID, date: arr.ArrestDate}) AS arrests,
               collect(DISTINCT {type: 'chargesheet', id: cs.CSID, date: cs.CSDate}) AS chargesheets
        """,
        {"cid": case_id},
    )


def find_accused_who_appear_together(accused_id: int) -> list[dict[str, Any]]:
    """Find other accused who appear on the same cases as the given accused."""
    return _run_cypher(
        """
        MATCH (a1:Accused {AccusedMasterID: $aid})<-[:HAS_ACCUSED]-(c:Case)-[:HAS_ACCUSED]->(a2:Accused)
        WHERE a1 <> a2
        RETURN DISTINCT a2.AccusedMasterID AS accused_id, a2.AccusedName AS name,
               count(c) AS shared_cases
        ORDER BY shared_cases DESC
        LIMIT 20
        """,
        {"aid": accused_id},
    )
