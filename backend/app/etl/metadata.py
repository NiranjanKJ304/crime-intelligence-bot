"""
Pydantic metadata models for the discovered database schema.

These models form an in-memory schema graph that every ETL stage
consumes instead of hardcoded table/column references.

Hierarchy:
    DatabaseMetadata
      └── SchemaMetadata
            └── TableMetadata
                  ├── ColumnMetadata[]
                  ├── ForeignKeyMetadata[]
                  └── IndexMetadata[]
    RelationshipMetadata (cross-table links)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    """Metadata for a single database column."""

    name: str
    data_type: str  # SQL type as string, e.g. "VARCHAR(255)", "INTEGER"
    python_type: str = "str"  # Mapped Python type name
    nullable: bool = True
    default: str | None = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    max_length: int | None = None  # For VARCHAR / TEXT length hints
    comment: str | None = None


class ForeignKeyMetadata(BaseModel):
    """Metadata for a single foreign-key constraint."""

    constraint_name: str | None = None
    column: str  # Local column name
    referred_schema: str
    referred_table: str
    referred_column: str


class IndexMetadata(BaseModel):
    """Metadata for a single index."""

    name: str | None = None
    columns: list[str] = Field(default_factory=list)
    unique: bool = False


class TableMetadata(BaseModel):
    """Metadata for a single database table."""

    name: str
    schema_name: str
    columns: list[ColumnMetadata] = Field(default_factory=list)
    primary_keys: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyMetadata] = Field(default_factory=list)
    indexes: list[IndexMetadata] = Field(default_factory=list)
    row_count: int | None = None
    comment: str | None = None

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def column_map(self) -> dict[str, ColumnMetadata]:
        return {c.name: c for c in self.columns}

    def get_column(self, name: str) -> ColumnMetadata | None:
        return self.column_map.get(name)

    def has_column(self, name: str) -> bool:
        return name in self.column_map

    @property
    def text_columns(self) -> list[ColumnMetadata]:
        """Return columns that hold string/text data."""
        text_types = {"text", "varchar", "character varying", "char", "character", "citext"}
        return [
            c for c in self.columns
            if any(t in c.data_type.lower() for t in text_types)
        ]

    @property
    def numeric_columns(self) -> list[ColumnMetadata]:
        numeric_types = {"integer", "int", "bigint", "smallint", "numeric", "decimal", "real", "double", "float"}
        return [
            c for c in self.columns
            if any(t in c.data_type.lower() for t in numeric_types)
        ]

    @property
    def datetime_columns(self) -> list[ColumnMetadata]:
        dt_types = {"timestamp", "date", "time", "datetime"}
        return [
            c for c in self.columns
            if any(t in c.data_type.lower() for t in dt_types)
        ]


class RelationshipMetadata(BaseModel):
    """A discovered relationship between two tables."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str
    constraint_name: str | None = None
    relationship_type: str = "many-to-one"  # Default FK relationship


class SchemaMetadata(BaseModel):
    """Metadata for a database schema containing multiple tables."""

    schema_name: str
    tables: dict[str, TableMetadata] = Field(default_factory=dict)
    relationships: list[RelationshipMetadata] = Field(default_factory=list)

    @property
    def table_names(self) -> list[str]:
        return list(self.tables.keys())


class DatabaseMetadata(BaseModel):
    """
    Root metadata object representing the entire discovered database.

    Provides a relationship graph (adjacency list) for downstream
    modules like Neo4j export and entity resolution.
    """

    schemas: dict[str, SchemaMetadata] = Field(default_factory=dict)

    @property
    def all_tables(self) -> dict[str, TableMetadata]:
        """Flat map of all tables across all schemas: table_name → metadata."""
        result: dict[str, TableMetadata] = {}
        for schema in self.schemas.values():
            result.update(schema.tables)
        return result

    @property
    def all_relationships(self) -> list[RelationshipMetadata]:
        """All relationships across all schemas."""
        result: list[RelationshipMetadata] = []
        for schema in self.schemas.values():
            result.extend(schema.relationships)
        return result

    @property
    def relationship_graph(self) -> dict[str, list[str]]:
        """
        Adjacency list: source_table → [target_table, ...].

        Useful for graph traversal, topological sorting, and
        future Neo4j/knowledge-graph construction.
        """
        graph: dict[str, list[str]] = {}
        for rel in self.all_relationships:
            graph.setdefault(rel.source_table, []).append(rel.target_table)
            graph.setdefault(rel.target_table, [])  # Ensure all nodes exist
        return graph

    def get_table(self, table_name: str) -> TableMetadata | None:
        """Look up a table across all schemas."""
        return self.all_tables.get(table_name)

    def get_related_tables(self, table_name: str) -> list[str]:
        """Return table names directly related via FK to the given table."""
        return self.relationship_graph.get(table_name, [])

    def model_dump_summary(self) -> dict[str, Any]:
        """Lightweight summary suitable for API responses."""
        return {
            "schemas": list(self.schemas.keys()),
            "total_tables": len(self.all_tables),
            "total_relationships": len(self.all_relationships),
            "tables": {
                name: {
                    "columns": len(t.columns),
                    "primary_keys": t.primary_keys,
                    "foreign_keys": len(t.foreign_keys),
                    "row_count": t.row_count,
                }
                for name, t in self.all_tables.items()
            },
            "relationship_graph": self.relationship_graph,
        }
