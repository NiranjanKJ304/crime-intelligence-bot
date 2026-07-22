"""
Graph Builder Orchestrator.

Manages the two-pass loading process:
Pass 1: Load nodes
Pass 2: Load relationships
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.neo4j_db import get_neo4j_driver
from app.graph.config import GraphConfig
from app.graph.schema_manager import init_graph_schema
from app.graph.queries.nodes import NODE_QUERIES
from app.graph.queries.relationships import RELATIONSHIP_QUERIES

logger = logging.getLogger(__name__)


class GraphBuilder:
    def __init__(self, engine: Engine, config: GraphConfig):
        self._engine = engine
        self._config = config
        self._driver = get_neo4j_driver()
        self.stats = {
            "tables_processed": 0,
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": [],
        }

    def build(self) -> dict[str, Any]:
        """Orchestrate the full graph build process."""
        start_time = time.time()
        logger.info("Starting Neo4j graph generation")

        with self._driver.session() as session:
            # 1. Init Schema
            init_graph_schema(session)
            
            # 2. Pass 1: Nodes
            self._load_nodes(session)
            
            # 3. Pass 2: Relationships
            self._load_relationships(session)
            
        duration = time.time() - start_time
        logger.info(f"Graph generation complete in {duration:.2f}s")
        self.stats["duration_seconds"] = round(duration, 2)
        return self.stats

    def _get_table_data_batched(self, table_name: str):
        """Yield batches of dictionaries from PostgreSQL."""
        query = f'SELECT * FROM "{self._config.source_schema}"."{table_name}"'
        with self._engine.connect() as conn:
            # Server-side cursor via stream_results
            result = conn.execution_options(stream_results=True).execute(text(query))
            while True:
                batch = result.fetchmany(self._config.batch_size)
                if not batch:
                    break
                # Convert rows to dicts
                keys = list(result.keys())
                yield [dict(zip(keys, row)) for row in batch]

    def _load_nodes(self, neo_session):
        """Pass 1: Load all nodes into Neo4j."""
        logger.info("=== Starting Pass 1: Nodes ===")
        for table_name, cypher_query in NODE_QUERIES.items():
            logger.info(f"Loading nodes for {table_name}...")
            total_nodes = 0
            try:
                for batch in self._get_table_data_batched(table_name):
                    # Filter out null identifiers before passing to Neo4j to avoid constraint errors
                    # Neo4j MERGE requires identifiers not to be null. We just pass the dict.
                    # For a robust production pipeline, we might filter dicts that lack primary IDs.
                    res = neo_session.run(cypher_query, batch=batch)
                    summary = res.consume()
                    created = summary.counters.nodes_created
                    total_nodes += created
                    
                logger.info(f"Completed nodes for {table_name}: +{total_nodes} nodes")
                self.stats["nodes_created"] += total_nodes
                self.stats["tables_processed"] += 1
            except Exception as e:
                msg = f"Failed to load nodes for {table_name}: {e}"
                logger.error(msg)
                self.stats["errors"].append(msg)

    def _load_relationships(self, neo_session):
        """Pass 2: Load all relationships into Neo4j."""
        logger.info("=== Starting Pass 2: Relationships ===")
        
        # We group relationship queries by the base table they depend on
        for rel_key, cypher_query in RELATIONSHIP_QUERIES.items():
            table_name = rel_key.split(":")[0]
            rel_name = rel_key.split(":")[1]
            logger.info(f"Loading relationship {rel_name} from {table_name}...")
            total_rels = 0
            try:
                for batch in self._get_table_data_batched(table_name):
                    res = neo_session.run(cypher_query, batch=batch)
                    summary = res.consume()
                    created = summary.counters.relationships_created
                    total_rels += created
                    
                logger.info(f"Completed {rel_name}: +{total_rels} relationships")
                self.stats["relationships_created"] += total_rels
            except Exception as e:
                msg = f"Failed to load relationship {rel_name} from {table_name}: {e}"
                logger.error(msg)
                self.stats["errors"].append(msg)

    def get_statistics(self) -> dict[str, Any]:
        """Fetch current live stats from Neo4j DB."""
        with self._driver.session() as session:
            nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            labels_raw = session.run("CALL db.labels() YIELD label RETURN label").value()
            
            entities = {}
            for label in labels_raw:
                count = session.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()["c"]
                entities[label] = count

            return {
                "nodes": nodes,
                "relationships": rels,
                "entities": entities
            }
