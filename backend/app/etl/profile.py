"""
Automated data profiling.

Inspects every DataFrame to detect data quality issues:
missing values, duplicates, whitespace, encoding, dates,
outliers, FK violations, and coordinate anomalies.

Generates JSON reports saved to reports/profile/.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.logging_config import StageTimer, get_stage_logger
from app.etl.config import ETLConfig
from app.etl.metadata import DatabaseMetadata, TableMetadata

logger = get_stage_logger("profile")


class DataProfiler:
    """
    Profile all extracted DataFrames for data quality issues.

    Usage:
        profiler = DataProfiler(db_metadata, etl_config)
        reports = profiler.profile_all(dataframes)
    """

    def __init__(
        self,
        db_metadata: DatabaseMetadata,
        config: ETLConfig,
    ) -> None:
        self._metadata = db_metadata
        self._config = config
        self._report_dir = Path(config.report_dir) / "profile"
        self._report_dir.mkdir(parents=True, exist_ok=True)

    def profile_all(
        self,
        dataframes: dict[str, pd.DataFrame],
    ) -> dict[str, dict[str, Any]]:
        """Profile every DataFrame and save reports."""
        reports: dict[str, dict[str, Any]] = {}

        with StageTimer("profile"):
            for table_name, df in dataframes.items():
                try:
                    table_meta = self._metadata.get_table(table_name)
                    report = self.profile_table(table_name, df, table_meta)
                    reports[table_name] = report
                    self._save_report(table_name, report)

                    issues = sum(
                        1 for section in report.get("issues", {}).values()
                        if section  # non-empty issue section
                    )
                    logger.info(
                        f"Profiled '{table_name}': {issues} issue categories found",
                        extra={"stage": "profile", "table": table_name, "rows": len(df)},
                    )
                except Exception as exc:
                    logger.error(
                        f"Failed to profile '{table_name}': {exc}",
                        extra={"stage": "profile", "table": table_name, "errors": 1},
                        exc_info=True,
                    )

        return reports

    def profile_table(
        self,
        table_name: str,
        df: pd.DataFrame,
        table_meta: TableMetadata | None,
    ) -> dict[str, Any]:
        """Generate a comprehensive profile report for a single table."""
        report: dict[str, Any] = {
            "table": table_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "issues": {},
        }

        # ── Missing values ────────────────────────────────────────
        missing = self._check_missing(df)
        if missing:
            report["issues"]["missing_values"] = missing

        # ── Duplicate rows ────────────────────────────────────────
        dup_count = int(df.duplicated().sum())
        if dup_count > 0:
            report["issues"]["duplicate_rows"] = {"count": dup_count}

        # ── Duplicate PKs ─────────────────────────────────────────
        if table_meta and table_meta.primary_keys:
            pk_dups = self._check_pk_duplicates(df, table_meta.primary_keys)
            if pk_dups:
                report["issues"]["duplicate_primary_keys"] = pk_dups

        # ── Invalid FKs ──────────────────────────────────────────
        # (deferred to validation stage for cross-table checks)

        # ── Whitespace issues ─────────────────────────────────────
        ws_issues = self._check_whitespace(df)
        if ws_issues:
            report["issues"]["whitespace"] = ws_issues

        # ── Encoding problems ─────────────────────────────────────
        enc_issues = self._check_encoding(df)
        if enc_issues:
            report["issues"]["encoding"] = enc_issues

        # ── Invalid dates ─────────────────────────────────────────
        date_issues = self._check_dates(df, table_meta)
        if date_issues:
            report["issues"]["invalid_dates"] = date_issues

        # ── Outliers ──────────────────────────────────────────────
        outlier_issues = self._check_outliers(df)
        if outlier_issues:
            report["issues"]["outliers"] = outlier_issues

        # ── Invalid coordinates ───────────────────────────────────
        coord_issues = self._check_coordinates(df)
        if coord_issues:
            report["issues"]["invalid_coordinates"] = coord_issues

        # ── Column statistics ─────────────────────────────────────
        report["statistics"] = self._column_statistics(df)

        return report

    # ── Private profiling methods ──────────────────────────────────────

    def _check_missing(self, df: pd.DataFrame) -> dict[str, Any] | None:
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        if missing.empty:
            return None
        total = len(df)
        return {
            col: {"count": int(count), "percentage": round(count / total * 100, 2)}
            for col, count in missing.items()
        }

    def _check_pk_duplicates(
        self, df: pd.DataFrame, pk_columns: list[str],
    ) -> dict[str, Any] | None:
        available_pks = [pk for pk in pk_columns if pk in df.columns]
        if not available_pks:
            return None
        dup_mask = df.duplicated(subset=available_pks, keep=False)
        dup_count = int(dup_mask.sum())
        if dup_count == 0:
            return None
        return {"columns": available_pks, "duplicate_count": dup_count}

    def _check_whitespace(self, df: pd.DataFrame) -> dict[str, Any] | None:
        issues: dict[str, Any] = {}
        for col in df.select_dtypes(include=["object", "str"]).columns:
            series = df[col].dropna().astype(str)
            if series.empty:
                continue
            leading_trailing = int((series != series.str.strip()).sum())
            multi_space = int(series.str.contains(r"  +", regex=True, na=False).sum())
            if leading_trailing > 0 or multi_space > 0:
                issues[col] = {
                    "leading_trailing_spaces": leading_trailing,
                    "multiple_spaces": multi_space,
                }
        return issues or None

    def _check_encoding(self, df: pd.DataFrame) -> dict[str, Any] | None:
        issues: dict[str, int] = {}
        # Check for common mojibake / non-printable characters
        pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]")
        for col in df.select_dtypes(include=["object", "str"]).columns:
            series = df[col].dropna().astype(str)
            bad_count = int(series.str.contains(pattern, regex=True, na=False).sum())
            if bad_count > 0:
                issues[col] = bad_count
        return issues or None

    def _check_dates(
        self, df: pd.DataFrame, table_meta: TableMetadata | None,
    ) -> dict[str, Any] | None:
        issues: dict[str, int] = {}
        # Check object columns that might contain date strings
        for col in df.select_dtypes(include=["object", "str"]).columns:
            col_lower = col.lower()
            is_date_hint = any(
                kw in col_lower
                for kw in ("date", "dt", "time", "stamp", "created", "updated")
            )
            if not is_date_hint:
                continue
            series = df[col].dropna()
            if series.empty:
                continue
            parsed = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
            invalid = int(parsed.isna().sum())
            if invalid > 0:
                issues[col] = invalid
        return issues or None

    def _check_outliers(self, df: pd.DataFrame) -> dict[str, Any] | None:
        issues: dict[str, Any] = {}
        for col in df.select_dtypes(include=[np.number]).columns:
            series = df[col].dropna()
            if len(series) < 10:
                continue
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_count = int(((series < lower) | (series > upper)).sum())
            if outlier_count > 0:
                issues[col] = {
                    "count": outlier_count,
                    "lower_bound": float(lower),
                    "upper_bound": float(upper),
                }
        return issues or None

    def _check_coordinates(self, df: pd.DataFrame) -> dict[str, Any] | None:
        issues: dict[str, Any] = {}
        for col in df.columns:
            col_lower = col.lower()
            if any(p in col_lower for p in self._config.latitude_patterns):
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    out_of_range = int(
                        ((df[col].dropna() < -90) | (df[col].dropna() > 90)).sum()
                    )
                    if out_of_range > 0:
                        issues[col] = {"out_of_range": out_of_range, "expected": "[-90, 90]"}
            elif any(p in col_lower for p in self._config.longitude_patterns):
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    out_of_range = int(
                        ((df[col].dropna() < -180) | (df[col].dropna() > 180)).sum()
                    )
                    if out_of_range > 0:
                        issues[col] = {"out_of_range": out_of_range, "expected": "[-180, 180]"}
        return issues or None

    def _column_statistics(self, df: pd.DataFrame) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        for col in df.columns:
            col_stats: dict[str, Any] = {
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isnull().sum()),
                "unique_count": int(df[col].nunique()),
            }
            if pd.api.types.is_numeric_dtype(df[col]):
                desc = df[col].describe()
                col_stats.update({
                    "min": float(desc.get("min", 0)),
                    "max": float(desc.get("max", 0)),
                    "mean": float(desc.get("mean", 0)),
                    "std": float(desc.get("std", 0)),
                })
            elif pd.api.types.is_string_dtype(df[col]):
                non_null = df[col].dropna()
                if not non_null.empty:
                    col_stats["avg_length"] = float(non_null.astype(str).str.len().mean())
                    top_values = non_null.value_counts().head(5)
                    col_stats["top_values"] = {
                        str(k): int(v) for k, v in top_values.items()
                    }
            stats[col] = col_stats
        return stats

    def _save_report(self, table_name: str, report: dict[str, Any]) -> None:
        filepath = self._report_dir / f"{table_name}_profile.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Saved profile report: {filepath}")
