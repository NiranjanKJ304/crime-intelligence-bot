"""
Tests for data transformers.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.etl.config import ETLConfig
from app.etl.metadata import TableMetadata
from app.etl.transform import (
    CanonicalAddressTransformer,
    DatePartsTransformer,
    IncidentDurationTransformer,
    NightCrimeTransformer,
    SearchTextTransformer,
    TimePartsTransformer,
    TransformationPipeline,
    WeekendTransformer,
)


class TestDatePartsTransformer:
    def test_generates_date_parts(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "crime_date": pd.to_datetime(["2024-01-15", "2024-06-22", "2024-12-31"]),
        })
        result = DatePartsTransformer().transform(df, None, etl_config)
        assert list(result["crime_year"]) == [2024, 2024, 2024]
        assert list(result["crime_month"]) == [1, 6, 12]
        assert "crime_week" in result.columns
        assert "crime_weekday" in result.columns

    def test_skips_when_no_datetime(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"name": ["Alice", "Bob"]})
        result = DatePartsTransformer().transform(df, None, etl_config)
        assert "crime_year" not in result.columns


class TestTimePartsTransformer:
    def test_generates_hour(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "crime_datetime": pd.to_datetime(["2024-01-15 10:30:00", "2024-01-15 23:45:00"]),
        })
        result = TimePartsTransformer().transform(df, None, etl_config)
        assert list(result["crime_hour"]) == [10, 23]


class TestWeekendTransformer:
    def test_detects_weekends(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "crime_date": pd.to_datetime([
                "2024-01-15",  # Monday
                "2024-01-20",  # Saturday
                "2024-01-21",  # Sunday
            ]),
        })
        result = WeekendTransformer().transform(df, None, etl_config)
        assert list(result["is_weekend"]) == [False, True, True]


class TestNightCrimeTransformer:
    def test_detects_night_crimes(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "crime_datetime": pd.to_datetime([
                "2024-01-15 03:00:00",  # Night
                "2024-01-15 12:00:00",  # Day
                "2024-01-15 23:00:00",  # Night
            ]),
        })
        result = NightCrimeTransformer().transform(df, None, etl_config)
        assert list(result["is_night_crime"]) == [True, False, True]


class TestIncidentDurationTransformer:
    def test_computes_duration(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "reported_date": pd.to_datetime(["2024-01-15 10:00:00"]),
            "resolved_date": pd.to_datetime(["2024-01-15 16:00:00"]),
        })
        result = IncidentDurationTransformer().transform(df, None, etl_config)
        assert "incident_duration_hours" in result.columns
        assert result["incident_duration_hours"].iloc[0] == 6.0


class TestCanonicalAddressTransformer:
    def test_concatenates_address(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "address": ["123 Main St"],
            "city": ["Mumbai"],
            "state": ["Maharashtra"],
        })
        result = CanonicalAddressTransformer().transform(df, None, etl_config)
        assert "canonical_address" in result.columns
        assert "Mumbai" in result["canonical_address"].iloc[0]

    def test_skips_without_address_cols(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({"name": ["Alice"]})
        result = CanonicalAddressTransformer().transform(df, None, etl_config)
        assert "canonical_address" not in result.columns


class TestSearchTextTransformer:
    def test_creates_search_text(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "name": ["John Doe"],
            "district": ["Mumbai"],
            "status": ["Open"],
        })
        result = SearchTextTransformer().transform(df, None, etl_config)
        assert "search_text" in result.columns
        search = result["search_text"].iloc[0]
        assert "John Doe" in search
        assert "Mumbai" in search


class TestTransformationPipeline:
    def test_default_pipeline(self, etl_config: ETLConfig) -> None:
        df = pd.DataFrame({
            "crime_date": pd.to_datetime(["2024-01-15 10:30:00", "2024-06-22 23:00:00"]),
            "district": ["Mumbai", "Delhi"],
            "address": ["123 Main St", "456 Oak Ave"],
            "city": ["Mumbai", "Delhi"],
        })
        pipeline = TransformationPipeline.default()
        result = pipeline.transform(df, None, etl_config)

        # Date parts should be generated
        assert "crime_year" in result.columns
        assert "crime_month" in result.columns
        assert "crime_hour" in result.columns
        assert "is_weekend" in result.columns
        assert "is_night_crime" in result.columns
        assert "canonical_address" in result.columns
        assert "search_text" in result.columns
