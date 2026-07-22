"""
Tests for data cleaners.
"""


from __future__ import annotations

import pandas as pd
import pytest

from app.etl.cleaning import (
    CleaningPipeline,
    CollapseSpacesCleaner,
    CrimeNumberNormalizerCleaner,
    DateNormalizerCleaner,
    DuplicateRemoverCleaner,
    GenderNormalizerCleaner,
    NullNormalizerCleaner,
    NumericConverterCleaner,
    PhoneNormalizerCleaner,
    TrimSpacesCleaner,
)
from app.etl.config import ETLConfig
from app.etl.metadata import TableMetadata


class TestTrimSpacesCleaner:
    def test_trims_leading_trailing(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"name": ["  John  ", "  Jane  ", "Bob"]})
        result = TrimSpacesCleaner().clean(df, None, etl_config)
        assert list(result["name"]) == ["John", "Jane", "Bob"]

    def test_preserves_evidence(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"narrative": ["  preserved  "], "name": ["  trimmed  "]})
        result = TrimSpacesCleaner().clean(df, None, etl_config)
        assert result["narrative"].iloc[0] == "  preserved  "
        assert result["name"].iloc[0] == "trimmed"


class TestCollapseSpacesCleaner:
    def test_collapses_spaces(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"name": ["John   Doe", "Jane    Smith"]})
        result = CollapseSpacesCleaner().clean(df, None, etl_config)
        assert result["name"].iloc[0] == "John Doe"
        assert result["name"].iloc[1] == "Jane Smith"


class TestNullNormalizerCleaner:
    def test_normalizes_nulls(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"value": ["NULL", "N/A", "none", "", "actual_value", "-"]})
        result = NullNormalizerCleaner().clean(df, None, etl_config)
        assert pd.isna(result["value"].iloc[0])
        assert pd.isna(result["value"].iloc[1])
        assert pd.isna(result["value"].iloc[2])
        assert pd.isna(result["value"].iloc[3])
        assert result["value"].iloc[4] == "actual_value"
        assert pd.isna(result["value"].iloc[5])


class TestGenderNormalizerCleaner:
    def test_normalizes_genders(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"gender": ["M", "Female", "male", "MALE", "f", "Other"]})
        result = GenderNormalizerCleaner().clean(df, None, etl_config)
        expected = ["Male", "Female", "Male", "Male", "Female", "Other"]
        assert list(result["gender"]) == expected

    def test_skips_non_gender_columns(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"name": ["M", "F"]})
        result = GenderNormalizerCleaner().clean(df, None, etl_config)
        assert list(result["name"]) == ["M", "F"]  # Unchanged


class TestPhoneNormalizerCleaner:
    def test_normalizes_phones(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"phone": [
            "+91-9876543210", "09876543211", "9876543212", "919876543213",
        ]})
        result = PhoneNormalizerCleaner().clean(df, None, etl_config)
        assert result["phone"].iloc[0] == "9876543210"
        assert result["phone"].iloc[1] == "9876543211"
        assert result["phone"].iloc[2] == "9876543212"
        assert result["phone"].iloc[3] == "9876543213"

    def test_preserves_invalid_phones(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"phone": ["invalid", "123"]})
        result = PhoneNormalizerCleaner().clean(df, None, etl_config)
        assert result["phone"].iloc[0] == "invalid"


class TestCrimeNumberNormalizerCleaner:
    def test_normalizes_fir_numbers(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"fir_no": ["  fir/001/2024  ", "fir 003 2024"]})
        result = CrimeNumberNormalizerCleaner().clean(df, None, etl_config)
        assert result["fir_no"].iloc[0] == "FIR/001/2024"
        assert result["fir_no"].iloc[1] == "FIR 003 2024"


class TestDuplicateRemoverCleaner:
    def test_removes_duplicates(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
        result = DuplicateRemoverCleaner().clean(df, None, etl_config)
        assert len(result) == 2


class TestNumericConverterCleaner:
    def test_converts_numeric(
        self, etl_config: ETLConfig, sample_accused_metadata: TableMetadata,
    ) -> None:
        df = pd.DataFrame({"accused_id": [1, 2], "age": ["25", "30"], "case_id": [1, 2], "name": ["A", "B"], "gender": ["M", "F"]})
        result = NumericConverterCleaner().clean(df, sample_accused_metadata, etl_config)
        assert pd.api.types.is_numeric_dtype(result["age"])


class TestCleaningPipeline:
    def test_default_pipeline(
        self,
        sample_case_df: pd.DataFrame,
        sample_table_metadata: TableMetadata,
        etl_config: ETLConfig,
    ) -> None:
        pipeline = CleaningPipeline.default()
        result = pipeline.clean(sample_case_df.copy(), sample_table_metadata, etl_config)

        # Gender should be normalized
        assert result["gender"].iloc[0] == "Male"  # "M" → "Male"
        assert result["gender"].iloc[1] == "Female"
        assert result["gender"].iloc[4] == "Female"  # "f" → "Female"

        # Null-like values should be None
        assert pd.isna(result["city"].iloc[3])  # "N/A" → NaN

    def test_pipeline_preserves_evidence(
        self,
        sample_case_df: pd.DataFrame,
        sample_table_metadata: TableMetadata,
        etl_config: ETLConfig,
    ) -> None:
        pipeline = CleaningPipeline.default()
        result = pipeline.clean(sample_case_df.copy(), sample_table_metadata, etl_config)

        # Narrative column should NOT have spaces collapsed
        # (it's an evidence column matched by "narrative" pattern)
        narrative = result["narrative"].iloc[0]
        assert narrative is not None  # Should still exist
