"""
Data transformation — derived field generation.

Creates analytics-ready columns (CrimeYear, CrimeMonth, CrimeHour,
Weekend, NightCrime, SearchText, etc.) using discovered metadata.

If a required source column does not exist, the transformation is
skipped gracefully — no crashes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from app.core.logging_config import StageTimer, get_stage_logger
from app.etl.config import ETLConfig
from app.etl.metadata import TableMetadata

logger = get_stage_logger("transform")


# ══════════════════════════════════════════════════════════════════════
# Base transformer
# ══════════════════════════════════════════════════════════════════════

class BaseTransformer(ABC):
    """Abstract base for column transformers."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def transform(
        self,
        df: pd.DataFrame,
        table_meta: TableMetadata | None,
        config: ETLConfig,
    ) -> pd.DataFrame:
        ...


# ══════════════════════════════════════════════════════════════════════
# Date/time derived fields
# ══════════════════════════════════════════════════════════════════════

class DatePartsTransformer(BaseTransformer):
    """
    Generate crime_year, crime_month, crime_week, crime_weekday from
    any datetime column detected in the table.
    """

    def transform(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        dt_cols = self._find_datetime_columns(df, config)
        if not dt_cols:
            logger.debug(f"{self.name}: no datetime columns found, skipping")
            return df

        # Use the first date-like column as the primary date source
        primary_col = dt_cols[0]
        series = pd.to_datetime(df[primary_col], errors="coerce")

        df["crime_year"] = series.dt.year.astype("Int64")
        df["crime_month"] = series.dt.month.astype("Int64")
        df["crime_week"] = series.dt.isocalendar().week.astype("Int64")
        df["crime_weekday"] = series.dt.day_name()

        logger.info(
            f"Generated date parts from '{primary_col}'",
            extra={"stage": "transform"},
        )
        return df

    @staticmethod
    def _find_datetime_columns(df: pd.DataFrame, config: ETLConfig) -> list[str]:
        """Find columns that are datetime or look like dates."""
        result: list[str] = []
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                result.append(col)
            elif config.is_date_column(col):
                result.append(col)
        return result


class TimePartsTransformer(BaseTransformer):
    """Generate crime_hour from datetime columns."""

    def transform(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df["crime_hour"] = df[col].dt.hour.astype("Int64")
                logger.info(
                    f"Generated crime_hour from '{col}'",
                    extra={"stage": "transform"},
                )
                return df
        return df


class WeekendTransformer(BaseTransformer):
    """Generate is_weekend boolean flag."""

    def transform(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df["is_weekend"] = df[col].dt.dayofweek >= 5
                return df
        return df


class NightCrimeTransformer(BaseTransformer):
    """Generate is_night_crime flag (22:00–06:00)."""

    def transform(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                hour = df[col].dt.hour
                df["is_night_crime"] = (hour < 6) | (hour >= 22)
                return df
        return df


class IncidentDurationTransformer(BaseTransformer):
    """
    Compute incident_duration_hours from start/end datetime pairs.

    Detects pairs heuristically:
    - *_start / *_end
    - *_from / *_to
    - reported_date / resolved_date
    """

    _PAIRS = [
        ("start", "end"),
        ("from", "to"),
        ("begin", "finish"),
        ("reported", "resolved"),
        ("occurrence", "closure"),
    ]

    def transform(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        dt_cols = [
            col for col in df.columns
            if pd.api.types.is_datetime64_any_dtype(df[col])
        ]
        if len(dt_cols) < 2:
            return df

        for start_hint, end_hint in self._PAIRS:
            start_col = self._find_col(dt_cols, start_hint)
            end_col = self._find_col(dt_cols, end_hint)
            if start_col and end_col and start_col != end_col:
                duration = (df[end_col] - df[start_col]).dt.total_seconds() / 3600
                df["incident_duration_hours"] = duration.round(2)
                logger.info(
                    f"Generated incident_duration_hours from '{start_col}' → '{end_col}'",
                    extra={"stage": "transform"},
                )
                return df
        return df

    @staticmethod
    def _find_col(cols: list[str], hint: str) -> str | None:
        for col in cols:
            if hint in col.lower():
                return col
        return None


# ══════════════════════════════════════════════════════════════════════
# Text-based derived fields
# ══════════════════════════════════════════════════════════════════════

class CanonicalAddressTransformer(BaseTransformer):
    """Concatenate address-related columns into a canonical_address field."""

    def transform(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        address_cols = [col for col in df.columns if config.is_address_column(col)]
        if not address_cols:
            return df

        def _concat_address(row: pd.Series) -> str:
            parts = []
            for col in address_cols:
                val = row.get(col)
                if pd.notna(val) and str(val).strip():
                    parts.append(str(val).strip())
            return ", ".join(parts) if parts else ""

        df["canonical_address"] = df.apply(_concat_address, axis=1)
        df["canonical_address"] = df["canonical_address"].replace("", None)
        logger.info(
            f"Generated canonical_address from {address_cols}",
            extra={"stage": "transform"},
        )
        return df


class SearchTextTransformer(BaseTransformer):
    """
    Concatenate text columns into a single search_text field for RAG.

    Includes all text columns (evidence + non-evidence) to create
    a comprehensive searchable representation of each row.
    """

    def transform(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        text_cols = list(df.select_dtypes(include=["object", "str"]).columns)
        if not text_cols:
            return df

        def _concat_text(row: pd.Series) -> str:
            parts = []
            for col in text_cols:
                val = row.get(col)
                if pd.notna(val) and str(val).strip():
                    parts.append(f"{col}: {str(val).strip()}")
            return " | ".join(parts) if parts else ""

        df["search_text"] = df.apply(_concat_text, axis=1)
        df["search_text"] = df["search_text"].replace("", None)
        logger.info(
            f"Generated search_text from {len(text_cols)} text columns",
            extra={"stage": "transform"},
        )
        return df


# ══════════════════════════════════════════════════════════════════════
# Transformation pipeline
# ══════════════════════════════════════════════════════════════════════

class TransformationPipeline:
    """
    Compose and apply transformers in sequence.

    Usage:
        pipeline = TransformationPipeline.default()
        transformed_df = pipeline.transform(df, table_meta, config)
    """

    def __init__(self, transformers: list[BaseTransformer] | None = None) -> None:
        self._transformers = transformers or []

    def add(self, transformer: BaseTransformer) -> "TransformationPipeline":
        self._transformers.append(transformer)
        return self

    def transform(
        self,
        df: pd.DataFrame,
        table_meta: TableMetadata | None,
        config: ETLConfig,
    ) -> pd.DataFrame:
        """Apply all transformers in order."""
        for transformer in self._transformers:
            try:
                df = transformer.transform(df, table_meta, config)
            except Exception as exc:
                logger.warning(
                    f"Transformer {transformer.name} failed: {exc}",
                    extra={"stage": "transform", "warnings": 1},
                    exc_info=True,
                )
        return df

    @classmethod
    def default(cls) -> "TransformationPipeline":
        """Build the default transformation pipeline."""
        return cls(
            transformers=[
                DatePartsTransformer(),
                TimePartsTransformer(),
                WeekendTransformer(),
                NightCrimeTransformer(),
                IncidentDurationTransformer(),
                CanonicalAddressTransformer(),
                SearchTextTransformer(),
            ]
        )
