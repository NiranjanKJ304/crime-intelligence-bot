"""
Shared test fixtures and helpers.
"""

from __future__ import annotations

import pytest
import pandas as pd

from app.etl.config import ETLConfig
from app.etl.metadata import (
    ColumnMetadata,
    DatabaseMetadata,
    ForeignKeyMetadata,
    IndexMetadata,
    RelationshipMetadata,
    SchemaMetadata,
    TableMetadata,
)


@pytest.fixture
def etl_config() -> ETLConfig:
    """Standard ETL config for testing."""
    return ETLConfig(
        source_schema="public",
        clean_schema="test_clean",
        batch_size=1000,
        evidence_patterns=["narrative", "evidence", "description"],
        latitude_patterns=["latitude", "lat"],
        longitude_patterns=["longitude", "lon", "lng"],
        report_dir="test_reports",
        log_dir="test_logs",
    )


@pytest.fixture
def sample_table_metadata() -> TableMetadata:
    """CaseMaster-like table metadata for testing."""
    return TableMetadata(
        name="CaseMaster",
        schema_name="public",
        columns=[
            ColumnMetadata(name="case_id", data_type="INTEGER", python_type="int", is_primary_key=True, nullable=False),
            ColumnMetadata(name="fir_no", data_type="VARCHAR(50)", python_type="str"),
            ColumnMetadata(name="crime_date", data_type="TIMESTAMP", python_type="datetime"),
            ColumnMetadata(name="district", data_type="VARCHAR(100)", python_type="str"),
            ColumnMetadata(name="address", data_type="VARCHAR(500)", python_type="str"),
            ColumnMetadata(name="city", data_type="VARCHAR(100)", python_type="str"),
            ColumnMetadata(name="state", data_type="VARCHAR(100)", python_type="str"),
            ColumnMetadata(name="gender", data_type="VARCHAR(10)", python_type="str"),
            ColumnMetadata(name="phone", data_type="VARCHAR(20)", python_type="str"),
            ColumnMetadata(name="narrative", data_type="TEXT", python_type="str"),
            ColumnMetadata(name="status", data_type="VARCHAR(20)", python_type="str"),
            ColumnMetadata(name="latitude", data_type="DOUBLE PRECISION", python_type="float"),
            ColumnMetadata(name="longitude", data_type="DOUBLE PRECISION", python_type="float"),
        ],
        primary_keys=["case_id"],
        foreign_keys=[],
        indexes=[],
    )


@pytest.fixture
def sample_accused_metadata() -> TableMetadata:
    """Accused table metadata with FK to CaseMaster."""
    return TableMetadata(
        name="Accused",
        schema_name="public",
        columns=[
            ColumnMetadata(name="accused_id", data_type="INTEGER", python_type="int", is_primary_key=True, nullable=False),
            ColumnMetadata(name="case_id", data_type="INTEGER", python_type="int", is_foreign_key=True),
            ColumnMetadata(name="name", data_type="VARCHAR(200)", python_type="str"),
            ColumnMetadata(name="gender", data_type="VARCHAR(10)", python_type="str"),
            ColumnMetadata(name="age", data_type="INTEGER", python_type="int"),
        ],
        primary_keys=["accused_id"],
        foreign_keys=[
            ForeignKeyMetadata(
                constraint_name="fk_accused_case",
                column="case_id",
                referred_schema="public",
                referred_table="CaseMaster",
                referred_column="case_id",
            )
        ],
        indexes=[],
    )


@pytest.fixture
def sample_db_metadata(
    sample_table_metadata: TableMetadata,
    sample_accused_metadata: TableMetadata,
) -> DatabaseMetadata:
    """Database metadata with CaseMaster + Accused tables."""
    return DatabaseMetadata(
        schemas={
            "public": SchemaMetadata(
                schema_name="public",
                tables={
                    "CaseMaster": sample_table_metadata,
                    "Accused": sample_accused_metadata,
                },
                relationships=[
                    RelationshipMetadata(
                        source_table="Accused",
                        source_column="case_id",
                        target_table="CaseMaster",
                        target_column="case_id",
                        constraint_name="fk_accused_case",
                    )
                ],
            )
        }
    )


@pytest.fixture
def sample_case_df() -> pd.DataFrame:
    """Sample CaseMaster DataFrame with intentional data quality issues."""
    return pd.DataFrame({
        "case_id": [1, 2, 3, 4, 5],
        "fir_no": ["  fir/001/2024  ", "FIR/002/2024", "fir 003 2024", "FIR/004/2024", "FIR/005/2024"],
        "crime_date": ["2024-01-15 10:30:00", "15/02/2024", "2024-03-20", "invalid-date", "2024-05-01 23:45:00"],
        "district": ["  Mumbai  ", "Delhi", "  Bangalore  ", "NULL", "Chennai"],
        "address": ["123 Main St", "456 Oak Ave", "789 Pine Rd", None, "321 Elm St"],
        "city": ["Mumbai", "Delhi", "Bangalore", "N/A", "Chennai"],
        "state": ["Maharashtra", "Delhi", "Karnataka", "none", "Tamil Nadu"],
        "gender": ["M", "Female", "male", "MALE", "f"],
        "phone": ["+91-9876543210", "09876543211", "9876543212", "91 9876543213", "invalid"],
        "narrative": ["  This is a FIR narrative  with  multiple   spaces  ", "Another narrative", "Third one", None, "Fifth narrative"],
        "status": ["Open", "Closed", "Open", "", "Under Investigation"],
        "latitude": [19.076, 28.704, 12.972, 91.5, None],
        "longitude": [72.877, 77.102, 77.594, 200.0, None],
    })


@pytest.fixture
def sample_accused_df() -> pd.DataFrame:
    """Sample Accused DataFrame."""
    return pd.DataFrame({
        "accused_id": [1, 2, 3, 4],
        "case_id": [1, 2, 3, 99],  # 99 is an orphan FK
        "name": ["  John Doe  ", "Jane   Smith", "Bob", "Alice"],
        "gender": ["m", "F", "Male", "FEMALE"],
        "age": [25, 30, "35", None],  # "35" is string, None is missing
    })
