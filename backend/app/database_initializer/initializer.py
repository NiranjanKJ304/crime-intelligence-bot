"""
Database Initializer Orchestrator.
Coordinates the startup initialization of PostgreSQL, Neo4j, and Qdrant.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.database import get_engine
from app.database_initializer.postgres_initializer import PostgresInitializer
from app.database_initializer.neo4j_initializer import Neo4jInitializer
from app.database_initializer.qdrant_initializer import QdrantInitializer

logger = logging.getLogger("crime_bot")


class DatabaseInitializer:
    """Orchestrates the automatic initialization of all databases."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = get_engine()

    def initialize_all(self) -> None:
        """Run all database initializers in sequence."""
        if not self.settings.auto_initialize_database:
            logger.info("[INIT] Auto-initialization is disabled.")
            return

        logger.info("=" * 60)
        logger.info("[INIT] STARTING AUTOMATIC DATABASE INITIALIZATION")
        logger.info("=" * 60)

        # 1. PostgreSQL (Must be first, as Neo4j depends on its clean schema)
        postgres_init = PostgresInitializer(self.settings, self.engine)
        if postgres_init.is_empty():
            success = postgres_init.initialize()
            if not success:
                logger.error("[INIT] PostgreSQL initialization failed. Halting startup sequence.")
                return
        else:
            logger.info("[INIT] PostgreSQL is already populated.")

        # 2. Neo4j (Depends on PostgreSQL if using GraphBuilder)
        neo4j_init = Neo4jInitializer(self.settings, self.engine)
        if neo4j_init.is_empty():
            neo4j_init.initialize()
        else:
            logger.info("[INIT] Neo4j is already populated.")

        # 3. Qdrant
        qdrant_init = QdrantInitializer(self.settings)
        if qdrant_init.is_empty():
            qdrant_init.initialize()
        else:
            logger.info("[INIT] Qdrant is already populated.")

        logger.info("=" * 60)
        logger.info("[INIT] DATABASE INITIALIZATION COMPLETE")
        logger.info("=" * 60)
