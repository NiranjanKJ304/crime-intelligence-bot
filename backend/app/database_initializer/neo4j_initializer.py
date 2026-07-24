"""
Neo4j Initialization Module.
Checks if the graph is empty and automatically builds it.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.core.neo4j_db import get_neo4j_driver
from app.graph.builder import GraphBuilder
from app.graph.config import build_graph_config

logger = logging.getLogger("crime_bot")


class Neo4jInitializer:
    """Initializes Neo4j with graph data if empty."""

    def __init__(self, settings: Settings, engine: Engine):
        self.settings = settings
        self.engine = engine
        self.driver = get_neo4j_driver()

    def is_empty(self) -> bool:
        """Check if Neo4j contains any nodes."""
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) AS c")
                count = result.single()["c"]
                return count == 0
        except Exception as e:
            logger.error(f"[INIT] Failed to check Neo4j status: {e}")
            return True  # Assume empty for retry, though usually we'd fail safe

    def initialize(self) -> bool:
        """Run the Neo4j initialization process."""
        logger.info("[INIT] Checking Neo4j...")
        
        if not self.is_empty():
            logger.info("[INIT] Neo4j graph is already populated. Skipping initialization.")
            return True

        logger.info("[INIT] Graph empty")

        success = False
        
        # 1. Try Cypher script if provided
        cypher_path = self.settings.neo4j_cypher_path
        if cypher_path and os.path.exists(cypher_path):
            logger.info(f"[INIT] Restoring graph from Cypher script {cypher_path}")
            success = self._execute_cypher_script(cypher_path)

        # 2. Fallback: Rebuild from PostgreSQL Clean schema using GraphBuilder
        if not success:
            logger.info("[INIT] Building graph using GraphBuilder from clean PostgreSQL schema...")
            try:
                # Assuming the clean schema has been populated by the ETL pipeline
                config = build_graph_config(self.settings)
                builder = GraphBuilder(self.engine, config)
                stats = builder.build()
                if stats.get("errors"):
                    logger.warning(f"[INIT] GraphBuilder finished with {len(stats['errors'])} errors.")
                success = True
            except Exception as e:
                logger.error(f"[INIT] GraphBuilder failed: {e}")
                return False

        if success:
            self._validate()
            logger.info("[INIT] Neo4j Ready")
            return True
            
        return False

    def _execute_cypher_script(self, file_path: str) -> bool:
        """Execute a raw Cypher script."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                queries = [q.strip() for q in f.read().split(";") if q.strip()]
            
            with self.driver.session() as session:
                for q in queries:
                    session.run(q)
            return True
        except Exception as e:
            logger.error(f"[INIT] Failed to execute Cypher script {file_path}: {e}")
            return False

    def _validate(self) -> None:
        """Validate node and relationship counts."""
        logger.info("[INIT] Validating Neo4j imports...")
        try:
            with self.driver.session() as session:
                nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                
                logger.info(f"[INIT] Total Nodes: {nodes}")
                logger.info(f"[INIT] Total Relationships: {rels}")
        except Exception as e:
            logger.error(f"[INIT] Neo4j validation failed: {e}")
