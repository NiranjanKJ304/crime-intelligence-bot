"""
Post-cleaning data validation.

Validates primary key uniqueness, foreign key integrity, data type
conformance, date ranges, coordinate ranges, required columns, and
categorical values.

Generates JSON validation reports saved to reports/validation/.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.logging_config import StageTimer, get_stage_logger
from app.etl.config import ETLConfig
from app.etl.metadata import DatabaseMetadata, TableMetadata

logger = get_stage_logger("validate")


class DataValidator:
    """
    Validate cleaned DataFrames for data integrity.

    Usage:
        validator = DataValidator(db_metadata, etl_config)
        reports = validator.validate_all(dataframes)
    """

    def __init__(
        self,
        db_metadata: DatabaseMetadata,
        config: ETLConfig,
    ) -> None:
        self._metadata = db_metadata
        self._config = config
        self._report_dir = Path(config.report_dir) / "validation"
        self._report_dir.mkdir(parents=True, exist_ok=True)

    def validate_all(
        self,
        dataframes: dict[str, pd.DataFrame],
    ) -> dict[str, dict[str, Any]]:
        """Validate every DataFrame and save reports."""
        reports: dict[str, dict[str, Any]] = {}

        with StageTimer("validate"):
            for table_name, df in dataframes.items():
                try:
                    logger.info(f"Validating {table_name}...")
                    table_meta = self._metadata.get_table(table_name)
                    report = self.validate_table(table_name, df, table_meta, dataframes)
                    reports[table_name] = report
                    self._save_report(table_name, report)

                    errors = report.get("total_errors", 0)
                    warnings = report.get("total_warnings", 0)
                    logger.info(
                        f"Validated '{table_name}': {errors} errors, {warnings} warnings",
                        extra={
                            "stage": "validate",
                            "table": table_name,
                            "errors": errors,
                            "warnings": warnings,
                        },
                    )
                except Exception as exc:
                    logger.warning(f"WARNING: Skipping table {table_name} because {exc}")
                    logger.error(
                        f"Failed to validate '{table_name}': {exc}",
                        extra={"stage": "validate", "table": table_name, "errors": 1},
                        exc_info=True,
                    )
                    raise RuntimeError(f"Cannot process table {table_name}: {exc}") from exc

        return reports

    def validate_table(
        self,
        table_name: str,
        df: pd.DataFrame,
        table_meta: TableMetadata | None,
        all_dataframes: dict[str, pd.DataFrame],
    ) -> dict[str, Any]:
        """Run all validations on a single table."""
        report: dict[str, Any] = {
            "table": table_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rows": len(df),
            "checks": {},
            "total_errors": 0,
            "total_warnings": 0,
        }

        checks = [
            ("pk_uniqueness", self._check_pk_uniqueness),
            ("fk_integrity", lambda d, m: self._check_fk_integrity(d, m, all_dataframes)),
            ("data_types", self._check_data_types),
            ("date_ranges", self._check_date_ranges),
            ("coordinates", self._check_coordinates),
            ("required_columns", self._check_required_columns),
            ("categorical_values", self._check_categorical_values),
        ]

        for check_name, check_fn in checks:
            try:
                result = check_fn(df, table_meta)
                if result:
                    report["checks"][check_name] = result
                    report["total_errors"] += result.get("errors", 0)
                    report["total_warnings"] += result.get("warnings", 0)
            except Exception as exc:
                report["checks"][check_name] = {
                    "status": "error",
                    "message": str(exc),
                    "errors": 1,
                }
                report["total_errors"] += 1

        return report

    # ── Validation checks ──────────────────────────────────────────────

    def _check_pk_uniqueness(
        self, df: pd.DataFrame, table_meta: TableMetadata | None,
    ) -> dict[str, Any] | None:
        if not table_meta or not table_meta.primary_keys:
            return None
        pks = [pk for pk in table_meta.primary_keys if pk in df.columns]
        if not pks:
            return None

        dup_count = int(df.duplicated(subset=pks, keep=False).sum())
        return {
            "status": "fail" if dup_count > 0 else "pass",
            "columns": pks,
            "duplicate_count": dup_count,
            "errors": 1 if dup_count > 0 else 0,
            "warnings": 0,
        }

    def _check_fk_integrity(
        self,
        df: pd.DataFrame,
        table_meta: TableMetadata | None,
        all_dataframes: dict[str, pd.DataFrame],
    ) -> dict[str, Any] | None:
        if not table_meta or not table_meta.foreign_keys:
            return None

        violations: dict[str, Any] = {}
        total_errors = 0

        for fk in table_meta.foreign_keys:
            if fk.column not in df.columns:
                continue
            ref_table = fk.referred_table
            ref_col = fk.referred_column

            if ref_table not in all_dataframes:
                violations[fk.column] = {
                    "status": "skipped",
                    "reason": f"Referenced table '{ref_table}' not in dataframes",
                    "warnings": 1,
                }
                continue

            ref_df = all_dataframes[ref_table]
            if ref_col not in ref_df.columns:
                violations[fk.column] = {
                    "status": "skipped",
                    "reason": f"Referenced column '{ref_col}' not found in '{ref_table}'",
                    "warnings": 1,
                }
                continue

            local_values = df[fk.column].dropna().unique()
            ref_values = set(ref_df[ref_col].dropna().unique())
            orphans = [v for v in local_values if v not in ref_values]

            if orphans:
                violations[fk.column] = {
                    "status": "fail",
                    "referenced_table": ref_table,
                    "referenced_column": ref_col,
                    "orphan_count": len(orphans),
                    "sample_orphans": [str(v) for v in orphans[:10]],
                    "errors": 1,
                }
                total_errors += 1
            else:
                violations[fk.column] = {"status": "pass", "errors": 0}

        if not violations:
            return None

        total_warnings = sum(v.get("warnings", 0) for v in violations.values())
        return {
            "checks": violations,
            "errors": total_errors,
            "warnings": total_warnings,
        }

    def _check_data_types(
        self, df: pd.DataFrame, table_meta: TableMetadata | None,
    ) -> dict[str, Any] | None:
        if not table_meta:
            return None

        mismatches: dict[str, Any] = {}
        for col_meta in table_meta.columns:
            if col_meta.name not in df.columns:
                continue
            actual_dtype = str(df[col_meta.name].dtype)
            expected_python = col_meta.python_type

            # Check for major mismatches
            is_ok = self._types_compatible(actual_dtype, expected_python)
            if not is_ok:
                mismatches[col_meta.name] = {
                    "expected": expected_python,
                    "actual": actual_dtype,
                    "sql_type": col_meta.data_type,
                }

        if not mismatches:
            return None
        return {"mismatches": mismatches, "errors": 0, "warnings": len(mismatches)}

    @staticmethod
    def _types_compatible(pandas_dtype: str, python_type: str) -> bool:
        """Check if a pandas dtype is compatible with the expected Python type."""
        dtype_lower = pandas_dtype.lower()
        if python_type in ("int", "float"):
            return "int" in dtype_lower or "float" in dtype_lower or "numeric" in dtype_lower
        if python_type == "str":
            return "object" in dtype_lower or "string" in dtype_lower
        if python_type in ("datetime", "date"):
            return "datetime" in dtype_lower or "object" in dtype_lower
        if python_type == "bool":
            return "bool" in dtype_lower or "object" in dtype_lower
        return True  # Unknown types pass

    def _check_date_ranges(
        self, df: pd.DataFrame, table_meta: TableMetadata | None,
    ) -> dict[str, Any] | None:
        issues: dict[str, Any] = {}
        for col in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df[col]):
                continue
            series = df[col].dropna()
            if series.empty:
                continue

            min_date = series.min()
            max_date = series.max()
            min_valid = pd.Timestamp("1900-01-01")
            max_valid = pd.Timestamp("2035-12-31")

            out_of_range = int(((series < min_valid) | (series > max_valid)).sum())
            if out_of_range > 0:
                issues[col] = {
                    "out_of_range_count": out_of_range,
                    "min_found": str(min_date),
                    "max_found": str(max_date),
                    "expected_range": "1900-01-01 to 2035-12-31",
                }

        if not issues:
            return None
        return {"columns": issues, "errors": 0, "warnings": len(issues)}

    def _check_coordinates(
        self, df: pd.DataFrame, table_meta: TableMetadata | None,
    ) -> dict[str, Any] | None:
        """Validate coordinate columns if they exist. Skip if absent."""
        issues: dict[str, Any] = {}

        for col in df.columns:
            if self._config.is_latitude_column(col) and pd.api.types.is_numeric_dtype(df[col]):
                series = df[col].dropna()
                out = int(((series < -90) | (series > 90)).sum())
                if out > 0:
                    issues[col] = {"out_of_range": out, "valid_range": "[-90, 90]"}

            elif self._config.is_longitude_column(col) and pd.api.types.is_numeric_dtype(df[col]):
                series = df[col].dropna()
                out = int(((series < -180) | (series > 180)).sum())
                if out > 0:
                    issues[col] = {"out_of_range": out, "valid_range": "[-180, 180]"}

        if not issues:
            return None
        return {"columns": issues, "errors": len(issues), "warnings": 0}

    def _check_required_columns(
        self, df: pd.DataFrame, table_meta: TableMetadata | None,
    ) -> dict[str, Any] | None:
        if not table_meta:
            return None

        issues: dict[str, int] = {}
        for col_meta in table_meta.columns:
            if col_meta.nullable:
                continue
            if col_meta.name not in df.columns:
                continue
            null_count = int(df[col_meta.name].isnull().sum())
            if null_count > 0:
                issues[col_meta.name] = null_count

        if not issues:
            return None
        return {
            "columns_with_nulls": issues,
            "errors": len(issues),
            "warnings": 0,
        }

    def _check_categorical_values(
        self, df: pd.DataFrame, table_meta: TableMetadata | None,
    ) -> dict[str, Any] | None:
        """Check known categorical columns for unexpected values."""
        issues: dict[str, Any] = {}

        # Gender validation
        for col in df.columns:
            if self._config.is_gender_column(col):
                valid = {"Male", "Female", "Other", None}
                unique_vals = set(df[col].dropna().unique())
                invalid = unique_vals - {v for v in valid if v is not None}
                if invalid:
                    issues[col] = {
                        "invalid_values": [str(v) for v in list(invalid)[:20]],
                        "valid_values": ["Male", "Female", "Other"],
                    }

        if not issues:
            return None
        return {"columns": issues, "errors": 0, "warnings": len(issues)}

    def _save_report(self, table_name: str, report: dict[str, Any]) -> None:
        filepath = self._report_dir / f"{table_name}_validation.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Saved validation report: {filepath}")
