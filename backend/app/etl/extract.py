"""
Data extraction from PostgreSQL into Pandas DataFrames.

Iterates over all discovered tables and loads each into a DataFrame.
Uses chunked reading for large tables. If one table fails, the
remaining tables are still extracted.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

from app.core.logging_config import StageTimer, get_stage_logger
from app.etl.config import ETLConfig
from app.etl.metadata import DatabaseMetadata, TableMetadata

logger = get_stage_logger("extract")


class DataExtractor:
    """
    Extract all discovered tables into Pandas DataFrames.

    Usage:
        extractor = DataExtractor(engine, db_metadata, etl_config)
        dataframes = extractor.extract_all()
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

    def extract_all(self) -> dict[str, pd.DataFrame]:
        """
        Extract every discovered table into a DataFrame.

        Returns:
            dict mapping table_name → DataFrame
        """
        dataframes: dict[str, pd.DataFrame] = {}

        with StageTimer("extract"):
            for table_name, table_meta in self._metadata.all_tables.items():
                try:
                    logger.info(f"Extracting {table_name}...")
                    df = self.extract_table(table_name, table_meta)
                    dataframes[table_name] = df
                    logger.info(
                        f"Extracted '{table_name}': {len(df)} rows, {len(df.columns)} cols",
                        extra={"stage": "extract", "table": table_name, "rows": len(df)},
                    )
                except Exception as exc:
                    logger.warning(f"WARNING: Skipping table {table_name} because {exc}")
                    logger.error(
                        f"Failed to extract '{table_name}': {exc}",
                        extra={"stage": "extract", "table": table_name, "errors": 1},
                        exc_info=True,
                    )
                    raise RuntimeError(f"Cannot process table {table_name}: {exc}") from exc

        logger.info(
            f"Extraction complete: {len(dataframes)}/{len(self._metadata.all_tables)} tables",
            extra={"stage": "extract", "rows": len(dataframes)},
        )
        return dataframes

    def extract_table(
        self,
        table_name: str,
        table_meta: TableMetadata,
    ) -> pd.DataFrame:
        """
        Extract a single table into a DataFrame.

        Uses chunked reading for tables estimated to be large.
        """
        schema = table_meta.schema_name
        qualified = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'

        # For large tables, use chunked reading and concatenate
        estimated_rows = table_meta.row_count or 0
        if estimated_rows > self._config.batch_size:
            return self._extract_chunked(qualified)

        return pd.read_sql_table(
            table_name,
            con=self._engine,
            schema=schema,
        )

    def _extract_chunked(self, qualified_name: str) -> pd.DataFrame:
        """Read a large table in chunks and concatenate."""
        chunks: list[pd.DataFrame] = []
        query = f"SELECT * FROM {qualified_name}"

        for chunk in pd.read_sql_query(
            query,
            con=self._engine,
            chunksize=self._config.batch_size,
        ):
            chunks.append(chunk)

        if not chunks:
            return pd.DataFrame()

        return pd.concat(chunks, ignore_index=True)
