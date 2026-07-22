"""
Load cleaned data into PostgreSQL clean schema.

Uses transactional TRUNCATE + INSERT to preserve indexes and constraints.
Never touches raw/source tables.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

import pandas as pd

from app.core.database import ensure_schema_exists
from app.core.logging_config import StageTimer, get_stage_logger
from app.etl.config import ETLConfig
from app.etl.metadata import DatabaseMetadata, TableMetadata

logger = get_stage_logger("load")


class DataLoader:
    """
    Load cleaned DataFrames into the clean schema.

    Strategy:
    1. Ensure clean schema exists.
    2. For each table:
       a. If the clean table does not exist → create via to_sql.
       b. If it exists → TRUNCATE within a transaction, then INSERT
          via to_sql(if_exists='append').

    This preserves indexes, constraints, and table structure across runs.

    Usage:
        loader = DataLoader(engine, db_metadata, etl_config)
        loader.load_all(cleaned_dataframes)
    """

    def __init__(
        self,
        engine: Engine,
        db_metadata: DatabaseMetadata,
        config: ETLConfig,
    ) -> None:
        self._engine = engine
        self._metadata = db_metadata
        self._config = config

    def load_all(self, dataframes: dict[str, pd.DataFrame]) -> dict[str, int]:
        """
        Load all cleaned DataFrames into the clean schema.

        Returns:
            dict mapping clean_table_name → rows loaded.
        """
        results: dict[str, int] = {}

        with StageTimer("load"):
            # Ensure the clean schema exists
            ensure_schema_exists(self._engine, self._config.clean_schema)

            for table_name, df in dataframes.items():
                try:
                    logger.info(f"Loading {table_name}...")
                    rows_loaded = self.load_table(table_name, df)
                    results[f"clean_{table_name}"] = rows_loaded
                    logger.info(
                        f"Loaded '{table_name}' → "
                        f"'{self._config.clean_schema}.clean_{table_name}': "
                        f"{rows_loaded} rows",
                        extra={
                            "stage": "load",
                            "table": table_name,
                            "rows": rows_loaded,
                        },
                    )
                    logger.info(f"Completed {table_name}.")
                except Exception as exc:
                    logger.warning(f"WARNING: Skipping table {table_name} because {exc}")
                    logger.error(
                        f"Failed to load '{table_name}': {exc}",
                        extra={"stage": "load", "table": table_name, "errors": 1},
                        exc_info=True,
                    )
                    raise RuntimeError(f"Cannot process table {table_name}: {exc}") from exc

        return results

    def load_table(self, table_name: str, df: pd.DataFrame) -> int:
        """
        Load a single DataFrame into the clean schema.

        Uses TRUNCATE + INSERT in a transaction to preserve
        table structure, indexes, and constraints.
        """
        clean_name = f"clean_{table_name}"
        schema = self._config.clean_schema

        if df.empty:
            logger.warning(
                f"Skipping empty DataFrame for '{table_name}'",
                extra={"stage": "load", "table": table_name, "warnings": 1},
            )
            return 0

        # Check if the clean table already exists
        table_exists = self._table_exists(clean_name, schema)

        if table_exists:
            # Transactional TRUNCATE + INSERT
            self._truncate_and_insert(clean_name, schema, df)
        else:
            # First run: create the table
            self._create_and_insert(clean_name, schema, df)

        return len(df)

    def _table_exists(self, table_name: str, schema: str) -> bool:
        """Check if a table exists in the given schema."""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT EXISTS ("
                        "  SELECT 1 FROM information_schema.tables "
                        "  WHERE table_schema = :schema "
                        "  AND table_name = :table"
                        ")"
                    ),
                    {"schema": schema, "table": table_name},
                )
                row = result.fetchone()
                return bool(row and row[0])
        except Exception:
            return False

    def _truncate_and_insert(
        self, table_name: str, schema: str, df: pd.DataFrame,
    ) -> None:
        """TRUNCATE then INSERT within a single transaction."""
        with self._engine.begin() as conn:
            # TRUNCATE inside the transaction
            conn.execute(text(f'TRUNCATE TABLE "{schema}"."{table_name}" CASCADE'))
            logger.debug(f"Truncated '{schema}.{table_name}'")

            # INSERT via pandas — uses the same connection/transaction
            df.to_sql(
                name=table_name,
                con=conn,
                schema=schema,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=self._config.batch_size,
            )

    def _create_and_insert(
        self, table_name: str, schema: str, df: pd.DataFrame,
    ) -> None:
        """Create a new table and insert data."""
        df.to_sql(
            name=table_name,
            con=self._engine,
            schema=schema,
            if_exists="fail",  # Should not exist
            index=False,
            method="multi",
            chunksize=self._config.batch_size,
        )

        # Create indexes on common columns for future query performance
        table_meta = self._metadata.get_table(
            table_name.replace("clean_", "", 1)
        )
        if table_meta:
            self._create_indexes(table_name, schema, table_meta)

    def _create_indexes(
        self, clean_table: str, schema: str, source_meta: TableMetadata,
    ) -> None:
        """Create indexes on PK and FK columns in the clean table."""
        try:
            with self._engine.begin() as conn:
                # Index on primary key columns
                for pk_col in source_meta.primary_keys:
                    idx_name = f"idx_{clean_table}_{pk_col}"
                    conn.execute(
                        text(
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                            f'ON "{schema}"."{clean_table}" ("{pk_col}")'
                        )
                    )

                # Index on foreign key columns
                for fk in source_meta.foreign_keys:
                    idx_name = f"idx_{clean_table}_{fk.column}"
                    conn.execute(
                        text(
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                            f'ON "{schema}"."{clean_table}" ("{fk.column}")'
                        )
                    )

                logger.debug(f"Created indexes for '{schema}.{clean_table}'")
        except Exception as exc:
            logger.warning(
                f"Could not create indexes for '{clean_table}': {exc}",
                extra={"stage": "load", "warnings": 1},
            )
