"""
Graph Loader Configuration.

Extracts Neo4j-specific configuration from the core Settings.

Source tables are NOT addressed by a single schema: each logical table
(CaseMaster, Employee, ...) is resolved at build time to the ETL output
``<clean_schema>.clean_<T>`` when it exists, otherwise to the raw import
``<source_schema>.<T>``. ``require_clean_schema`` disables the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class GraphConfig:
    """Immutable graph loader configuration."""
    source_schema: str
    clean_schema: str
    require_clean_schema: bool
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    batch_size: int


def build_graph_config(settings: Settings | None = None) -> GraphConfig:
    """Build a GraphConfig from application settings."""
    settings = settings or get_settings()
    return GraphConfig(
        source_schema=settings.source_schema,
        clean_schema=settings.clean_schema,
        require_clean_schema=settings.require_clean_schema,
        neo4j_uri=settings.neo4j_uri,
        neo4j_username=settings.neo4j_username,
        neo4j_password=settings.neo4j_password,
        batch_size=settings.batch_size,
    )
