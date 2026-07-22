"""
Reusable data cleaners following the Strategy pattern.

Each cleaner implements `BaseCleaner.clean(df, table_meta, config) → df`.
Cleaners are metadata-aware: they inspect column types and names
to decide what to clean and what to preserve (e.g., evidence text).

The `CleaningPipeline` composes cleaners and applies them in order.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd

from app.core.logging_config import get_stage_logger
from app.etl.config import ETLConfig
from app.etl.metadata import TableMetadata

logger = get_stage_logger("clean")


# ══════════════════════════════════════════════════════════════════════
# Base class
# ══════════════════════════════════════════════════════════════════════

class BaseCleaner(ABC):
    """Abstract base for all data cleaners."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def clean(
        self,
        df: pd.DataFrame,
        table_meta: TableMetadata | None,
        config: ETLConfig,
    ) -> pd.DataFrame:
        """Apply cleaning logic and return the cleaned DataFrame."""
        ...


# ══════════════════════════════════════════════════════════════════════
# Concrete cleaners
# ══════════════════════════════════════════════════════════════════════

class TrimSpacesCleaner(BaseCleaner):
    """Strip leading/trailing whitespace from all string columns."""

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object", "str"]).columns:
            if config.is_evidence_column(col):
                continue
            df[col] = df[col].map(
                lambda x: x.strip() if isinstance(x, str) else x
            )
        return df


class CollapseSpacesCleaner(BaseCleaner):
    """Replace multiple consecutive spaces with a single space."""

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object", "str"]).columns:
            if config.is_evidence_column(col):
                continue
            df[col] = df[col].map(
                lambda x: re.sub(r"\s+", " ", x) if isinstance(x, str) else x
            )
        return df


class NullNormalizerCleaner(BaseCleaner):
    """Convert common null-like strings to actual None/NaN."""

    NULL_STRINGS = {
        "", "null", "none", "n/a", "na", "nan", "nil", "undefined",
        "not available", "not applicable", "-", "--", ".",
    }

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object", "str"]).columns:
            df[col] = df[col].map(
                lambda x: None
                if isinstance(x, str) and x.strip().lower() in self.NULL_STRINGS
                else x
            )
        return df


class GenderNormalizerCleaner(BaseCleaner):
    """Normalize gender values: M/Male/MALE → 'Male', F/Female → 'Female', etc."""

    _MALE = {"m", "male", "man", "boy", "gents", "masculine"}
    _FEMALE = {"f", "female", "woman", "girl", "ladies", "feminine"}
    _OTHER = {"o", "other", "transgender", "trans", "non-binary"}

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.columns:
            if not config.is_gender_column(col):
                continue
            df[col] = df[col].map(self._normalize)
        return df

    def _normalize(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        v = value.strip().lower()
        if v in self._MALE:
            return "Male"
        if v in self._FEMALE:
            return "Female"
        if v in self._OTHER:
            return "Other"
        return value  # Unknown values passed through


class PhoneNormalizerCleaner(BaseCleaner):
    """Normalize Indian phone numbers (strip +91, 0-prefix, spaces, dashes)."""

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.columns:
            if not config.is_phone_column(col):
                continue
            df[col] = df[col].map(self._normalize)
        return df

    @staticmethod
    def _normalize(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        # Remove all non-digit characters
        digits = re.sub(r"\D", "", value)
        if not digits:
            return value
        # Remove country code (91) prefix
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if len(digits) == 10:
            return digits
        return value  # Return original if we can't normalize


class CrimeNumberNormalizerCleaner(BaseCleaner):
    """Standardize crime/FIR number formats (uppercase, strip extra spaces)."""

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.columns:
            if not config.is_crime_number_column(col):
                continue
            df[col] = df[col].map(self._normalize)
        return df

    @staticmethod
    def _normalize(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        # Uppercase, collapse spaces, strip
        return re.sub(r"\s+", " ", value.strip().upper())


class DateNormalizerCleaner(BaseCleaner):
    """Parse multiple date formats into ISO 8601 strings."""

    _FORMATS = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object", "str"]).columns:
            if not config.is_date_column(col):
                continue
            df[col] = df[col].map(self._normalize)
        return df

    def _normalize(self, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            return value
        value = value.strip()
        for fmt in self._FORMATS:
            try:
                from datetime import datetime
                parsed = datetime.strptime(value, fmt)
                return parsed.isoformat()
            except (ValueError, TypeError):
                continue
        # Fallback to pandas parsing
        try:
            parsed = pd.to_datetime(value, dayfirst=True)
            return parsed.isoformat()
        except Exception:
            return value  # Return original if unparseable


class DatetimeConverterCleaner(BaseCleaner):
    """Convert string date columns to datetime64 dtype."""

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object", "str"]).columns:
            if not config.is_date_column(col):
                continue
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
            except Exception:
                pass  # Skip if conversion fails entirely
        return df


class DuplicateRemoverCleaner(BaseCleaner):
    """Remove exact duplicate rows, keeping the first occurrence."""

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(keep="first").reset_index(drop=True)
        removed = before - len(df)
        if removed > 0:
            logger.info(
                f"Removed {removed} duplicate rows",
                extra={"stage": "clean", "rows": removed},
            )
        return df


class NumericConverterCleaner(BaseCleaner):
    """Coerce columns that should be numeric based on metadata."""

    def clean(
        self, df: pd.DataFrame, table_meta: TableMetadata | None, config: ETLConfig,
    ) -> pd.DataFrame:
        if table_meta is None:
            return df
        for col_meta in table_meta.numeric_columns:
            if col_meta.name not in df.columns:
                continue
            if pd.api.types.is_numeric_dtype(df[col_meta.name]):
                continue  # Already numeric
            try:
                df[col_meta.name] = pd.to_numeric(df[col_meta.name], errors="coerce")
            except Exception:
                pass
        return df


# ══════════════════════════════════════════════════════════════════════
# Cleaning pipeline
# ══════════════════════════════════════════════════════════════════════

class CleaningPipeline:
    """
    Compose and apply multiple cleaners in sequence.

    Usage:
        pipeline = CleaningPipeline.default()
        cleaned_df = pipeline.clean(df, table_meta, config)
    """

    def __init__(self, cleaners: list[BaseCleaner] | None = None) -> None:
        self._cleaners = cleaners or []

    def add(self, cleaner: BaseCleaner) -> "CleaningPipeline":
        self._cleaners.append(cleaner)
        return self

    def clean(
        self,
        df: pd.DataFrame,
        table_meta: TableMetadata | None,
        config: ETLConfig,
    ) -> pd.DataFrame:
        """Apply all cleaners in order."""
        for cleaner in self._cleaners:
            try:
                before_rows = len(df)
                df = cleaner.clean(df, table_meta, config)
                logger.debug(
                    f"Applied {cleaner.name}: {before_rows}→{len(df)} rows",
                    extra={"stage": "clean"},
                )
            except Exception as exc:
                logger.warning(
                    f"Cleaner {cleaner.name} failed: {exc}",
                    extra={"stage": "clean", "warnings": 1},
                    exc_info=True,
                )
        return df

    @classmethod
    def default(cls) -> "CleaningPipeline":
        """Build the default cleaning pipeline with all standard cleaners."""
        return cls(
            cleaners=[
                NullNormalizerCleaner(),
                TrimSpacesCleaner(),
                CollapseSpacesCleaner(),
                GenderNormalizerCleaner(),
                PhoneNormalizerCleaner(),
                CrimeNumberNormalizerCleaner(),
                DateNormalizerCleaner(),
                DatetimeConverterCleaner(),
                DuplicateRemoverCleaner(),
                NumericConverterCleaner(),
            ]
        )
