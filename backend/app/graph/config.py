"""
Graph Loader Configuration.

Extracts Neo4j-specific configuration from the core Settings.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class GraphConfig:
    """Immutable graph loader configuration."""
    source_schema: str
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    batch_size: int


def build_graph_config(settings: Settings | None = None) -> GraphConfig:
    """Build a GraphConfig from application settings."""
    settings = settings or get_settings()
    return GraphConfig(
        source_schema=settings.clean_schema, # Graph reads from clean schema
        neo4j_uri=settings.neo4j_uri,
        neo4j_username=settings.neo4j_username,
        neo4j_password=settings.neo4j_password,
        batch_size=settings.batch_size,
    )
