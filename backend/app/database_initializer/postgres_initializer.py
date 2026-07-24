"""
PostgreSQL Initialization Module.
Checks if PostgreSQL is empty, creates schema, imports data, and validates.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.core.database import get_engine
from app.etl.pipeline import ETLPipeline
from app.etl.config import build_etl_config

logger = logging.getLogger("crime_bot")


class PostgresInitializer:
    """Initializes PostgreSQL with existing data if empty."""

    def __init__(self, settings: Settings, engine: Engine | None = None):
        self.settings = settings
        self.engine = engine or get_engine()

    def is_public_empty(self) -> bool:
        """Check if the CaseMaster table exists in the public schema."""
        query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'CaseMaster'
            );
        """)
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query).scalar()
                return not result
        except Exception as e:
            logger.error(f"[INIT] Failed to check PostgreSQL status: {e}")
            return True

    def is_clean_empty(self) -> bool:
        """Check if the clean schema is populated."""
        query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'clean' 
                AND table_name = 'clean_CaseMaster'
            );
        """)
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query).scalar()
                return not result
        except Exception:
            return True

    def is_empty(self) -> bool:
        """Required by Initializer orchestrator, returns true if either is empty."""
        return self.is_public_empty() or self.is_clean_empty()

    def initialize(self) -> bool:
        """Run the full PostgreSQL initialization process."""
        logger.info("[INIT] Checking PostgreSQL...")
        
        if not self.is_empty():
            logger.info("[INIT] PostgreSQL is already populated. Skipping initialization.")
            return True

        if self.is_public_empty():
            logger.info("[INIT] Public schema empty. Initializing raw data...")
            # 1. Create Schema
            schema_path = self.settings.postgres_schema_path
            if not schema_path or not os.path.exists(schema_path):
                logger.error(f"[INIT] POSTGRES_SCHEMA_PATH '{schema_path}' not found.")
                return False
                
            logger.info(f"[INIT] Creating schema from {schema_path}")
            if not self._execute_sql_file(schema_path):
                return False

            # 2. Import Data
            backup_path = self.settings.postgres_backup_path
            csv_path = self.settings.postgres_csv_path
            
            success = False
            if backup_path and os.path.exists(backup_path):
                logger.info(f"[INIT] Restoring from backup {backup_path}")
                success = self._execute_sql_file(backup_path)
            
            if not success and csv_path and os.path.exists(csv_path):
                logger.info(f"[INIT] Importing CSV data from {csv_path}")
                success = self._import_csv_data(csv_path)

            if not success:
                logger.error("[INIT] Failed to import data into PostgreSQL.")
                return False

            # 3. Validate
            self._validate()

        if self.is_clean_empty():
            # 4. Trigger ETL Pipeline to populate `clean` schema
            logger.info("[INIT] Triggering ETL Pipeline to populate clean schema...")
        try:
            etl_config = build_etl_config(self.settings)
            pipeline = ETLPipeline(self.engine, etl_config)
            result = pipeline.run()
            if result.errors:
                logger.warning(f"[INIT] ETL Pipeline finished with {len(result.errors)} errors.")
            else:
                logger.info("[INIT] ETL Pipeline completed successfully.")
        except Exception as e:
            logger.error(f"[INIT] ETL Pipeline failed during initialization: {e}")
            return False

        logger.info("[INIT] PostgreSQL Ready")
        return True

    def _execute_sql_file(self, file_path: str) -> bool:
        """Execute a raw SQL script file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                sql = f.read()
            
            # Split by statements or just execute as one block
            # SQLAlchemy text() handles multiple statements if driver supports it, 
            # but psycopg2 usually handles full strings.
            with self.engine.begin() as conn:
                # Raw connection cursor to execute a script with multiple statements and COPY commands
                raw_conn = conn.connection
                with raw_conn.cursor() as cursor:
                    cursor.execute(sql)
            return True
        except Exception as e:
            logger.error(f"[INIT] Failed to execute {file_path}: {e}")
            return False

    def _import_csv_data(self, csv_dir: str) -> bool:
        """Import all CSV data using pandas chunked inserts as a fallback."""
        # Order matters for foreign keys
        tables = [
            "District", "Unit", "Court", "Employee", "CaseMaster", 
            "ComplainantDetails", "Victim", "Accused", 
            "ActSectionAssociation", "ChargesheetDetails", "ArrestSurrender"
        ]
        
        try:
            for table in tables:
                csv_file = Path(csv_dir) / f"{table}.csv"
                if not csv_file.exists():
                    logger.warning(f"[INIT] CSV file not found for table {table}: {csv_file}")
                    continue
                    
                logger.info(f"[INIT] Importing {table}...")
                
                # Read CSV and insert chunk by chunk
                chunk_size = 10000
                for i, chunk in enumerate(pd.read_csv(csv_file, chunksize=chunk_size)):
                    chunk.to_sql(
                        name=table, 
                        con=self.engine, 
                        schema="public", 
                        if_exists="append", 
                        index=False,
                        method="multi",
                        chunksize=1000
                    )
                logger.info(f"[INIT] Imported {table} successfully.")
            return True
        except Exception as e:
            logger.error(f"[INIT] CSV Import failed: {e}")
            return False

    def _validate(self) -> None:
        """Validate row counts after import."""
        tables = [
            "District", "Unit", "Court", "Employee", "CaseMaster", 
            "ComplainantDetails", "Victim", "Accused", 
            "ActSectionAssociation", "ChargesheetDetails", "ArrestSurrender"
        ]
        logger.info("[INIT] Validating PostgreSQL imports...")
        
        try:
            with self.engine.connect() as conn:
                for table in tables:
                    query = text(f'SELECT count(*) FROM "public"."{table}"')
                    count = conn.execute(query).scalar()
                    logger.info(f"[INIT] Table '{table}': {count} rows")
        except Exception as e:
            logger.error(f"[INIT] Validation failed: {e}")
