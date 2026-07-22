"""
Neo4j driver connection management.

Provides a global singleton for the Neo4j driver to be used
throughout the application for graph operations.
"""

from __future__ import annotations

import logging
from typing import Generator

from neo4j import GraphDatabase, Driver

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def init_neo4j_driver() -> None:
    """Initialize the global Neo4j driver singleton."""
    global _driver
    if _driver is None:
        settings = get_settings()
        logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}")
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        # Verify connectivity
        _driver.verify_connectivity()


def get_neo4j_driver() -> Driver:
    """Return the global Neo4j driver instance."""
    global _driver
    if _driver is None:
        init_neo4j_driver()
    assert _driver is not None, "Neo4j driver initialization failed"
    return _driver


def close_neo4j_driver() -> None:
    """Close the global Neo4j driver."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def get_neo4j_session() -> Generator:
    """
    FastAPI dependency yielding a Neo4j session.
    
    Usage:
        @app.get("/example")
        def endpoint(session=Depends(get_neo4j_session)):
            ...
    """
    driver = get_neo4j_driver()
    with driver.session() as session:
        yield session
