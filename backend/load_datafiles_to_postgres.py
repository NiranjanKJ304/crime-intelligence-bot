"""
Utility Script: Load CSV files from datafiles/ directly into PostgreSQL.

Usage:
    python load_datafiles_to_postgres.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import text

current_dir = Path(__file__).resolve().parent
if (current_dir / "backend" / "app").exists():
    sys.path.insert(0, str(current_dir / "backend"))
elif (current_dir / "app").exists():
    sys.path.insert(0, str(current_dir))

from app.core.config import get_settings
from app.core.database import get_engine

# Order is important for relational consistency
TABLE_ORDER = [
    "District",
    "Unit",
    "Court",
    "Employee",
    "CaseMaster",
    "ComplainantDetails",
    "Victim",
    "Accused",
    "ActSectionAssociation",
    "ChargesheetDetails",
    "ArrestSurrender",
]


def load_all_csvs(data_dir: str | Path | None = None) -> None:
    settings = get_settings()
    engine = get_engine()

    if not data_dir:
        # Check standard datafiles directories
        project_root = Path(__file__).resolve().parent.parent
        possible_dirs = [
            project_root / "datafiles",
            Path(__file__).resolve().parent / "datafiles",
            Path(settings.postgres_csv_path) if settings.postgres_csv_path else None,
        ]
        for d in possible_dirs:
            if d and d.exists() and (d / "CaseMaster.csv").exists():
                data_dir = d
                break

    if not data_dir or not Path(data_dir).exists():
        print(f"[ERROR] Could not find 'datafiles' directory.")
        return

    data_dir = Path(data_dir)
    print("=" * 60)
    print(f"[INFO] Loading CSV data from: {data_dir.resolve()}")
    print(f"[INFO] Target Database: {settings.database_url}")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS public;"))
        conn.commit()

    total_rows = 0

    for table in TABLE_ORDER:
        csv_file = data_dir / f"{table}.csv"
        if not csv_file.exists():
            print(f"[WARN] Skipping {table}: File {csv_file.name} not found.")
            continue

        print(f"[*] Reading and importing {table}...")
        try:
            # Read CSV in chunks for memory safety
            chunk_size = 5000
            table_rows = 0

            for i, chunk in enumerate(pd.read_csv(csv_file, chunksize=chunk_size, low_memory=False)):
                # If first chunk, replace table schema if needed, else append
                if_exists_mode = "replace" if i == 0 else "append"
                chunk.to_sql(
                    name=table,
                    con=engine,
                    schema=settings.source_schema,
                    if_exists=if_exists_mode,
                    index=False,
                    method="multi",
                    chunksize=1000,
                )
                table_rows += len(chunk)

            print(f"[+] Table '{table}' loaded: {table_rows:,} rows")
            total_rows += table_rows

        except Exception as e:
            print(f"[ERROR] Error importing {table}: {e}")

    print("=" * 60)
    print(f"[DONE] Successfully imported {total_rows:,} total rows into PostgreSQL!")
    print("=" * 60)


if __name__ == "__main__":
    load_all_csvs()
