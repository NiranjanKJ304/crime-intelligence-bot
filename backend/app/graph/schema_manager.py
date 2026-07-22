"""
Graph Schema Manager.

Responsible for setting up Neo4j constraints and indexes to
ensure data integrity and query performance.
"""

from __future__ import annotations

import logging
from typing import Sequence

from neo4j import Session

logger = logging.getLogger(__name__)

# List of cypher queries to initialize the schema
SCHEMA_QUERIES: Sequence[str] = [
    # ── Unique Constraints ──────────────────────────────────────────────
    "CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.CaseMasterID IS UNIQUE",
    "CREATE CONSTRAINT accused_id IF NOT EXISTS FOR (n:Accused) REQUIRE n.AccusedMasterID IS UNIQUE",
    "CREATE CONSTRAINT victim_id IF NOT EXISTS FOR (n:Victim) REQUIRE n.VictimMasterID IS UNIQUE",
    "CREATE CONSTRAINT complainant_id IF NOT EXISTS FOR (n:Complainant) REQUIRE n.ComplainantID IS UNIQUE",
    "CREATE CONSTRAINT employee_id IF NOT EXISTS FOR (n:Employee) REQUIRE n.EmployeeID IS UNIQUE",
    "CREATE CONSTRAINT court_id IF NOT EXISTS FOR (n:Court) REQUIRE n.CourtID IS UNIQUE",
    "CREATE CONSTRAINT district_id IF NOT EXISTS FOR (n:District) REQUIRE n.DistrictID IS UNIQUE",
    "CREATE CONSTRAINT unit_id IF NOT EXISTS FOR (n:Unit) REQUIRE n.UnitID IS UNIQUE",
    "CREATE CONSTRAINT arrest_id IF NOT EXISTS FOR (n:Arrest) REQUIRE n.ArrestSurrenderID IS UNIQUE",
    "CREATE CONSTRAINT chargesheet_id IF NOT EXISTS FOR (n:Chargesheet) REQUIRE n.CSID IS UNIQUE",
    
    # ── Property Indexes ────────────────────────────────────────────────
    "CREATE INDEX case_no_idx IF NOT EXISTS FOR (n:Case) ON (n.CaseNo)",
    "CREATE INDEX case_crimeno_idx IF NOT EXISTS FOR (n:Case) ON (n.CrimeNo)",
]


def init_graph_schema(session: Session) -> None:
    """Run schema initialization queries against Neo4j."""
    logger.info("Initializing Neo4j Graph Schema (Constraints & Indexes)")
    for query in SCHEMA_QUERIES:
        try:
            session.run(query)
        except Exception as e:
            logger.error(f"Failed to execute schema query '{query}': {e}")
            raise
    logger.info("Graph schema initialized successfully")
