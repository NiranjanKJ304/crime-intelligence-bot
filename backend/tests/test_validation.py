"""
Tests for data validation.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.etl.config import ETLConfig
from app.etl.metadata import DatabaseMetadata, TableMetadata
from app.etl.validation import DataValidator


@pytest.fixture
def validator(sample_db_metadata: DatabaseMetadata, etl_config: ETLConfig) -> DataValidator:
    return DataValidator(sample_db_metadata, etl_config)


class TestPKValidation:
    def test_unique_pks_pass(
        self, validator: DataValidator, sample_table_metadata: TableMetadata,
    ) -> None:
        df = pd.DataFrame({"case_id": [1, 2, 3]})
        result = validator._check_pk_uniqueness(df, sample_table_metadata)
        assert result is not None
        assert result["status"] == "pass"

    def test_duplicate_pks_fail(
        self, validator: DataValidator, sample_table_metadata: TableMetadata,
    ) -> None:
        df = pd.DataFrame({"case_id": [1, 1, 2]})
        result = validator._check_pk_uniqueness(df, sample_table_metadata)
        assert result is not None
        assert result["status"] == "fail"
        assert result["duplicate_count"] == 2


class TestFKValidation:
    def test_valid_fks_pass(
        self,
        validator: DataValidator,
        sample_accused_metadata: TableMetadata,
    ) -> None:
        case_df = pd.DataFrame({"case_id": [1, 2, 3]})
        accused_df = pd.DataFrame({"accused_id": [1, 2], "case_id": [1, 2]})
        all_dfs = {"CaseMaster": case_df, "Accused": accused_df}

        result = validator._check_fk_integrity(accused_df, sample_accused_metadata, all_dfs)
        assert result is not None
        assert result["checks"]["case_id"]["status"] == "pass"

    def test_orphan_fks_fail(
        self,
        validator: DataValidator,
        sample_accused_metadata: TableMetadata,
    ) -> None:
        case_df = pd.DataFrame({"case_id": [1, 2]})
        accused_df = pd.DataFrame({"accused_id": [1, 2], "case_id": [1, 99]})
        all_dfs = {"CaseMaster": case_df, "Accused": accused_df}

        result = validator._check_fk_integrity(accused_df, sample_accused_metadata, all_dfs)
        assert result is not None
        assert result["checks"]["case_id"]["status"] == "fail"
        assert result["checks"]["case_id"]["orphan_count"] == 1


class TestDateRangeValidation:
    def test_valid_dates_pass(self, validator: DataValidator) -> None:
        df = pd.DataFrame({
            "crime_date": pd.to_datetime(["2024-01-15", "2024-06-22"]),
        })
        result = validator._check_date_ranges(df, None)
        assert result is None  # No issues

    def test_out_of_range_dates(self, validator: DataValidator) -> None:
        df = pd.DataFrame({
            "crime_date": pd.to_datetime(["1800-01-01", "2040-01-01", "2024-01-15"]),
        })
        result = validator._check_date_ranges(df, None)
        assert result is not None
        assert "crime_date" in result["columns"]


class TestCoordinateValidation:
    def test_valid_coordinates(self, validator: DataValidator) -> None:
        df = pd.DataFrame({
            "latitude": [19.076, 28.704],
            "longitude": [72.877, 77.102],
        })
        result = validator._check_coordinates(df, None)
        assert result is None

    def test_invalid_coordinates(self, validator: DataValidator) -> None:
        df = pd.DataFrame({
            "latitude": [19.076, 91.5],  # 91.5 is out of range
            "longitude": [72.877, 200.0],  # 200 is out of range
        })
        result = validator._check_coordinates(df, None)
        assert result is not None
        assert "latitude" in result["columns"]
        assert "longitude" in result["columns"]

    def test_skips_when_no_coords(self, validator: DataValidator) -> None:
        df = pd.DataFrame({"name": ["Alice"], "age": [25]})
        result = validator._check_coordinates(df, None)
        assert result is None


class TestRequiredColumns:
    def test_non_nullable_with_nulls(
        self, validator: DataValidator, sample_table_metadata: TableMetadata,
    ) -> None:
        df = pd.DataFrame({"case_id": [1, None, 3]})
        result = validator._check_required_columns(df, sample_table_metadata)
        assert result is not None
        assert "case_id" in result["columns_with_nulls"]


class TestCategoricalValidation:
    def test_valid_genders(self, validator: DataValidator) -> None:
        df = pd.DataFrame({"gender": ["Male", "Female", "Other"]})
        result = validator._check_categorical_values(df, None)
        assert result is None

    def test_invalid_genders(self, validator: DataValidator) -> None:
        df = pd.DataFrame({"gender": ["Male", "Unknown", "XYZ"]})
        result = validator._check_categorical_values(df, None)
        assert result is not None
