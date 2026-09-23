"""
Graph Builder Orchestrator.

Manages the two-pass loading process:
Pass 1: Load nodes
Pass 2: Load relationships

Source tables are addressed by logical name (see queries/nodes.py) and
resolved to their physical schema.table through ColumnMapper, so the same
configuration policy governs the chat tools and the graph build.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterator

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.neo4j_db import get_neo4j_driver
from app.graph.config import GraphConfig
from app.graph.queries.nodes import NODE_QUERIES
from app.graph.queries.relationships import RELATIONSHIP_QUERIES
from app.graph.schema_manager import init_graph_schema
from app.services.tools.exceptions import MappingError
from app.services.tools.mapper import ColumnMapper

logger = logging.getLogger(__name__)


class GraphBuildError(Exception):
    """Raised when the graph build could not process any source table."""

    def __init__(self, message: str, stats: dict[str, Any]):
        super().__init__(message)
        self.stats = stats


class GraphBuilder:
    def __init__(self, engine: Engine, config: GraphConfig, mapper: ColumnMapper | None = None):
        self._engine = engine
        self._config = config
        self._mapper = mapper or ColumnMapper.get_instance()
        self._driver = get_neo4j_driver()
        self._resolved: dict[str, str] = {}  # logical -> quoted physical
        self.stats: dict[str, Any] = {
            "status": "pending",
            "tables_processed": 0,
            "tables_failed": 0,
            "nodes_created": 0,
            "relationships_created": 0,
            "source_tables": {},
            "errors": [],
        }

    # ── Source resolution ─────────────────────────────────────────────

    def _resolve_sources(self) -> None:
        """Resolve every logical table used by node/relationship queries up front."""
        logical_tables = list(dict.fromkeys(
            list(NODE_QUERIES) + [key.split(":")[0] for key in RELATIONSHIP_QUERIES]
        ))
        for index, logical in enumerate(logical_tables):
            try:
                schema, table = self._mapper.resolve_physical_table(logical, refresh=(index == 0))
            except MappingError as exc:
                msg = (
                    f"Source table for '{logical}' not found: {exc} "
                    f"(source_schema={self._config.source_schema}, clean_schema={self._config.clean_schema}, "
                    f"require_clean_schema={self._config.require_clean_schema}). "
                    f"Run the ETL pipeline (POST /api/v1/etl/run) or check SOURCE_SCHEMA/CLEAN_SCHEMA."
                )
                logger.error(msg)
                self.stats["errors"].append(msg)
                self.stats["tables_failed"] += 1
                continue
            self._resolved[logical] = f'"{schema}"."{table}"'
            self.stats["source_tables"][logical] = f"{schema}.{table}"
            logger.info("[GRAPH] %s -> %s.%s", logical, schema, table)

    # ── Build ─────────────────────────────────────────────────────────

    def build(self) -> dict[str, Any]:
        """Orchestrate the full graph build process."""
        start_time = time.time()
        logger.info("Starting Neo4j graph generation")

        self._resolve_sources()
        if not self._resolved:
            self.stats["status"] = "failed"
            self.stats["duration_seconds"] = round(time.time() - start_time, 2)
            raise GraphBuildError(
                "Graph build failed: no PostgreSQL source tables could be resolved.", self.stats
            )

        with self._driver.session() as session:
            init_graph_schema(session)
            self._load_nodes(session)
            self._load_relationships(session)

        duration = time.time() - start_time
        self.stats["duration_seconds"] = round(duration, 2)
        if self.stats["tables_processed"] == 0:
            self.stats["status"] = "failed"
            raise GraphBuildError("Graph build failed: no source table could be loaded.", self.stats)
        self.stats["status"] = "completed_with_errors" if self.stats["errors"] else "success"
        logger.info("Graph generation %s in %.2fs", self.stats["status"], duration)
        return self.stats

    def _get_table_data_batched(self, logical: str) -> Iterator[list[dict[str, Any]]]:
        """Yield batches of row dicts from the resolved physical table."""
        query = f"SELECT * FROM {self._resolved[logical]}"
        with self._engine.connect() as conn:
            result = conn.execution_options(stream_results=True).execute(text(query))
            keys = list(result.keys())
            while True:
                batch = result.fetchmany(self._config.batch_size)
                if not batch:
                    break
                yield [dict(zip(keys, row)) for row in batch]

    def _load_nodes(self, neo_session) -> None:
        """Pass 1: Load all nodes into Neo4j."""
        logger.info("=== Starting Pass 1: Nodes ===")
        for logical, cypher_query in NODE_QUERIES.items():
            if logical not in self._resolved:
                continue  # already reported during resolution
            physical = self.stats["source_tables"][logical]
            logger.info("Loading nodes for %s from %s...", logical, physical)
            total_nodes = 0
            try:
                for batch in self._get_table_data_batched(logical):
                    summary = neo_session.run(cypher_query, batch=batch).consume()
                    total_nodes += summary.counters.nodes_created
                logger.info("Completed nodes for %s: +%d nodes", logical, total_nodes)
                self.stats["nodes_created"] += total_nodes
                self.stats["tables_processed"] += 1
            except Exception as exc:
                msg = f"Failed to load nodes for {logical} from {physical}: {exc}"
                logger.error(msg)
                self.stats["errors"].append(msg)
                self.stats["tables_failed"] += 1

    def _load_relationships(self, neo_session) -> None:
        """Pass 2: Load all relationships into Neo4j."""
        logger.info("=== Starting Pass 2: Relationships ===")
        for rel_key, cypher_query in RELATIONSHIP_QUERIES.items():
            logical, rel_name = rel_key.split(":")
            if logical not in self._resolved:
                continue
            physical = self.stats["source_tables"][logical]
            logger.info("Loading relationship %s from %s...", rel_name, physical)
            total_rels = 0
            try:
                for batch in self._get_table_data_batched(logical):
                    summary = neo_session.run(cypher_query, batch=batch).consume()
                    total_rels += summary.counters.relationships_created
                logger.info("Completed %s: +%d relationships", rel_name, total_rels)
                self.stats["relationships_created"] += total_rels
            except Exception as exc:
                msg = f"Failed to load relationship {rel_name} from {physical}: {exc}"
                logger.error(msg)
                self.stats["errors"].append(msg)

    def get_statistics(self) -> dict[str, Any]:
        """Fetch current live stats from Neo4j DB."""
        with self._driver.session() as session:
            nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            labels_raw = session.run("CALL db.labels() YIELD label RETURN label").value()
            rel_types_raw = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType").value()

            entities = {
                label: session.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()["c"]
                for label in labels_raw
            }
            relationships = {
                rel_type: session.run(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) AS c").single()["c"]
                for rel_type in rel_types_raw
            }

            return {
                "nodes": nodes,
                "relationships": rels,
                "entities": entities,
                "relationship_types": relationships,
            }
