"""
Database schema discovery via SQLAlchemy Inspector.

Introspects PostgreSQL metadata (schemas, tables, columns, PKs, FKs,
indexes) and builds a complete DatabaseMetadata graph with zero
hardcoded table or column names.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.logging_config import StageTimer, get_stage_logger
from app.etl.metadata import (
    ColumnMetadata,
    DatabaseMetadata,
    ForeignKeyMetadata,
    IndexMetadata,
    RelationshipMetadata,
    SchemaMetadata,
    TableMetadata,
)

logger = get_stage_logger("discovery")

# ── SQL type → Python type mapping ────────────────────────────────────
_SQL_TO_PYTHON: dict[str, str] = {
    "integer": "int",
    "int": "int",
    "bigint": "int",
    "smallint": "int",
    "serial": "int",
    "bigserial": "int",
    "numeric": "float",
    "decimal": "float",
    "real": "float",
    "double precision": "float",
    "float": "float",
    "boolean": "bool",
    "bool": "bool",
    "text": "str",
    "varchar": "str",
    "character varying": "str",
    "char": "str",
    "character": "str",
    "citext": "str",
    "uuid": "str",
    "json": "dict",
    "jsonb": "dict",
    "date": "date",
    "timestamp": "datetime",
    "timestamp without time zone": "datetime",
    "timestamp with time zone": "datetime",
    "time": "time",
    "bytea": "bytes",
    "inet": "str",
    "array": "list",
}


def _map_python_type(sql_type: str) -> str:
    """Map a SQL type string to a Python type name."""
    sql_lower = sql_type.lower().strip()
    for key, value in _SQL_TO_PYTHON.items():
        if key in sql_lower:
            return value
    return "str"


def _get_max_length(col_info: dict) -> int | None:
    """Extract max_length from SQLAlchemy column info if available."""
    col_type = col_info.get("type")
    if col_type is not None and hasattr(col_type, "length"):
        return col_type.length
    return None


class SchemaDiscovery:
    """
    Discovers the full database schema using SQLAlchemy's Inspector API.

    Usage:
        discovery = SchemaDiscovery(engine)
        metadata = discovery.discover()
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._inspector = inspect(engine)

    def discover(self, schema_name: str = "public") -> DatabaseMetadata:
        """
        Discover all tables, columns, keys, and relationships in
        the specified schema. Returns a complete DatabaseMetadata graph.
        """
        with StageTimer("discovery", schema=schema_name):
            schema_meta = self._discover_schema(schema_name)
            db_meta = DatabaseMetadata(schemas={schema_name: schema_meta})

            logger.info(
                f"Discovery complete: {len(schema_meta.tables)} tables, "
                f"{len(schema_meta.relationships)} relationships",
                extra={
                    "stage": "discovery",
                    "rows": len(schema_meta.tables),
                },
            )
            return db_meta

    def _discover_schema(self, schema_name: str) -> SchemaMetadata:
        """Discover all tables and relationships within a schema."""
        table_names = self._inspector.get_table_names(schema=schema_name)
        logger.info(f"Found {len(table_names)} tables in schema '{schema_name}'")

        tables: dict[str, TableMetadata] = {}
        for table_name in table_names:
            logger.info(f"Discovering table {table_name}...")
            tables[table_name] = self._discover_table(table_name, schema_name)

        all_relationships: list[RelationshipMetadata] = []

        for table_name in table_names:
            try:
                table_meta = self._discover_table(table_name, schema_name)
                tables[table_name] = table_meta

                # Extract relationships from foreign keys
                for fk in table_meta.foreign_keys:
                    rel = RelationshipMetadata(
                        source_table=table_name,
                        source_column=fk.column,
                        target_table=fk.referred_table,
                        target_column=fk.referred_column,
                        constraint_name=fk.constraint_name,
                    )
                    all_relationships.append(rel)

                logger.info(
                    f"Discovered table '{table_name}': "
                    f"{len(table_meta.columns)} columns, "
                    f"{len(table_meta.primary_keys)} PKs, "
                    f"{len(table_meta.foreign_keys)} FKs",
                    extra={"stage": "discovery", "table": table_name},
                )

            except Exception as exc:
                logger.error(
                    f"Failed to discover table '{table_name}': {exc}",
                    extra={"stage": "discovery", "table": table_name},
                    exc_info=True,
                )

        return SchemaMetadata(
            schema_name=schema_name,
            tables=tables,
            relationships=all_relationships,
        )

    def _discover_table(self, table_name: str, schema_name: str) -> TableMetadata:
        """Discover full metadata for a single table."""
        # ── Columns ───────────────────────────────────────────────
        raw_columns = self._inspector.get_columns(table_name, schema=schema_name)
        columns = [
            ColumnMetadata(
                name=col["name"],
                data_type=str(col["type"]),
                python_type=_map_python_type(str(col["type"])),
                nullable=col.get("nullable", True),
                default=str(col["default"]) if col.get("default") is not None else None,
                max_length=_get_max_length(col),
                comment=col.get("comment"),
            )
            for col in raw_columns
        ]

        # ── Primary Keys ─────────────────────────────────────────
        pk_constraint = self._inspector.get_pk_constraint(table_name, schema=schema_name)
        primary_keys: list[str] = pk_constraint.get("constrained_columns", [])

        # Mark PK columns
        pk_set = set(primary_keys)
        for col in columns:
            if col.name in pk_set:
                col.is_primary_key = True

        # ── Foreign Keys ─────────────────────────────────────────
        raw_fks = self._inspector.get_foreign_keys(table_name, schema=schema_name)
        foreign_keys: list[ForeignKeyMetadata] = []
        fk_columns: set[str] = set()

        for fk in raw_fks:
            for local_col, ref_col in zip(
                fk.get("constrained_columns", []),
                fk.get("referred_columns", []),
            ):
                foreign_keys.append(
                    ForeignKeyMetadata(
                        constraint_name=fk.get("name"),
                        column=local_col,
                        referred_schema=fk.get("referred_schema") or schema_name,
                        referred_table=fk["referred_table"],
                        referred_column=ref_col,
                    )
                )
                fk_columns.add(local_col)

        # Mark FK columns
        for col in columns:
            if col.name in fk_columns:
                col.is_foreign_key = True

        # ── Indexes ───────────────────────────────────────────────
        raw_indexes = self._inspector.get_indexes(table_name, schema=schema_name)
        indexes = [
            IndexMetadata(
                name=idx.get("name"),
                columns=idx.get("column_names", []),
                unique=idx.get("unique", False),
            )
            for idx in raw_indexes
        ]

        # ── Row count (approximate for large tables) ──────────────
        row_count = self._get_row_count(table_name, schema_name)

        return TableMetadata(
            name=table_name,
            schema_name=schema_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            indexes=indexes,
            row_count=row_count,
        )

    def _get_row_count(self, table_name: str, schema_name: str) -> int | None:
        """Get approximate row count using pg_class statistics."""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT reltuples::bigint AS estimate "
                        "FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE c.relname = :table AND n.nspname = :schema"
                    ),
                    {"table": table_name, "schema": schema_name},
                )
                row = result.fetchone()
                return int(row[0]) if row and row[0] >= 0 else None
        except Exception:
            return None
