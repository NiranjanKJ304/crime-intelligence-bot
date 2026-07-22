"""
ETL Pipeline Orchestrator.

Runs the full pipeline: Discovery → Extract → Profile → Clean →
Transform → Validate → Load. Implements the DataProvider protocol
so downstream modules can consume results directly.

Per-table error isolation: if one table fails at any stage,
the remaining tables continue processing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

from app.core.logging_config import StageTimer, get_stage_logger
from app.etl.cleaning import CleaningPipeline
from app.etl.config import ETLConfig
from app.etl.extract import DataExtractor
from app.etl.load import DataLoader
from app.etl.metadata import DatabaseMetadata, RelationshipMetadata, TableMetadata
from app.etl.profile import DataProfiler
from app.etl.schema_discovery import SchemaDiscovery
from app.etl.transform import TransformationPipeline
from app.etl.utils import now_utc, save_json_report
from app.etl.validation import DataValidator

logger = get_stage_logger("pipeline")


class PipelineResult:
    """
    Result of a complete ETL pipeline run.

    Implements the DataProvider protocol so that future modules
    (Neo4j, Qdrant, RAG, LLM Agent) can consume the output directly.
    """

    def __init__(
        self,
        db_metadata: DatabaseMetadata,
        raw_dataframes: dict[str, pd.DataFrame],
        clean_dataframes: dict[str, pd.DataFrame],
        profile_reports: dict[str, dict[str, Any]],
        validation_reports: dict[str, dict[str, Any]],
        load_results: dict[str, int],
        started_at: datetime,
        completed_at: datetime,
        errors: list[str],
    ) -> None:
        self.db_metadata = db_metadata
        self.raw_dataframes = raw_dataframes
        self.clean_dataframes = clean_dataframes
        self.profile_reports = profile_reports
        self.validation_reports = validation_reports
        self.load_results = load_results
        self.started_at = started_at
        self.completed_at = completed_at
        self.errors = errors

    # ── DataProvider protocol implementation ───────────────────────

    def get_clean_dataframes(self) -> dict[str, pd.DataFrame]:
        return self.clean_dataframes

    def get_table_metadata(self, table_name: str) -> TableMetadata | None:
        return self.db_metadata.get_table(table_name)

    def get_database_metadata(self) -> DatabaseMetadata:
        return self.db_metadata

    def get_relationship_graph(self) -> dict[str, list[str]]:
        return self.db_metadata.relationship_graph

    def get_relationships(self) -> list[RelationshipMetadata]:
        return self.db_metadata.all_relationships

    # ── Summary ────────────────────────────────────────────────────

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()

    def summary(self) -> dict[str, Any]:
        """Generate a JSON-serializable summary of the pipeline run."""
        return {
            "status": "completed_with_errors" if self.errors else "success",
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": round(self.duration_seconds, 2),
            "tables_discovered": len(self.db_metadata.all_tables),
            "tables_extracted": len(self.raw_dataframes),
            "tables_cleaned": len(self.clean_dataframes),
            "tables_loaded": len(self.load_results),
            "total_rows_loaded": sum(self.load_results.values()),
            "relationships_discovered": len(self.db_metadata.all_relationships),
            "errors": self.errors,
            "load_results": self.load_results,
        }


class ETLPipeline:
    """
    Orchestrates the full ETL pipeline.

    Usage:
        pipeline = ETLPipeline(engine, config)
        result = pipeline.run()
    """

    def __init__(
        self,
        engine: Engine,
        config: ETLConfig,
        cleaning_pipeline: CleaningPipeline | None = None,
        transformation_pipeline: TransformationPipeline | None = None,
    ) -> None:
        self._engine = engine
        self._config = config
        self._cleaning = cleaning_pipeline or CleaningPipeline.default()
        self._transformation = transformation_pipeline or TransformationPipeline.default()

        # Pipeline state
        self._last_result: PipelineResult | None = None

    @property
    def last_result(self) -> PipelineResult | None:
        return self._last_result

    def run(self) -> PipelineResult:
        """Execute the full ETL pipeline."""
        started_at = now_utc()
        errors: list[str] = []

        logger.info("=" * 60)
        logger.info("ETL PIPELINE STARTED")
        logger.info("=" * 60)

        with StageTimer("pipeline"):
            # ── Step 0: Database Discovery ─────────────────────────
            logger.info("Step 0: Database Discovery")
            discovery = SchemaDiscovery(self._engine)
            db_metadata = discovery.discover(self._config.source_schema)

            if not db_metadata.all_tables:
                msg = "No tables discovered — aborting pipeline"
                logger.error(msg)
                errors.append(msg)
                return self._build_result(
                    db_metadata, {}, {}, {}, {}, {},
                    started_at, errors,
                )

            # ── Step 1: Extract ────────────────────────────────────
            logger.info("Step 1: Extract")
            extractor = DataExtractor(self._engine, db_metadata, self._config)
            raw_dataframes = extractor.extract_all()

            if not raw_dataframes:
                msg = "No tables extracted — aborting pipeline"
                logger.error(msg)
                errors.append(msg)
                return self._build_result(
                    db_metadata, {}, {}, {}, {}, {},
                    started_at, errors,
                )

            # ── Step 2: Profile ────────────────────────────────────
            logger.info("Step 2: Profile")
            profiler = DataProfiler(db_metadata, self._config)
            profile_reports = profiler.profile_all(raw_dataframes)

            # ── Step 3 & 4: Clean + Transform ──────────────────────
            logger.info("Step 3 & 4: Clean + Transform")
            clean_dataframes = self._clean_and_transform(
                raw_dataframes, db_metadata, errors,
            )

            # ── Step 5: Validate ───────────────────────────────────
            logger.info("Step 5: Validate")
            validator = DataValidator(db_metadata, self._config)
            validation_reports = validator.validate_all(clean_dataframes)

            # ── Step 6: Load ───────────────────────────────────────
            logger.info("Step 6: Load")
            loader = DataLoader(self._engine, db_metadata, self._config)
            load_results = loader.load_all(clean_dataframes)

        # ── Build result ───────────────────────────────────────────
        result = self._build_result(
            db_metadata, raw_dataframes, clean_dataframes,
            profile_reports, validation_reports, load_results,
            started_at, errors,
        )

        # Save pipeline summary
        self._save_summary(result)
        self._last_result = result

        logger.info("=" * 60)
        logger.info(f"ETL PIPELINE COMPLETE: {result.summary()['status']}")
        logger.info(f"Duration: {result.duration_seconds:.2f}s")
        logger.info(f"Tables loaded: {len(load_results)}")
        logger.info(f"Total rows: {sum(load_results.values())}")
        if errors:
            logger.warning(f"Errors: {len(errors)}")
        logger.info("=" * 60)

        return result

    def _clean_and_transform(
        self,
        raw_dataframes: dict[str, pd.DataFrame],
        db_metadata: DatabaseMetadata,
        errors: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Clean and transform each table, isolating per-table errors."""
        clean_dataframes: dict[str, pd.DataFrame] = {}

        for table_name, df in raw_dataframes.items():
            try:
                logger.info(f"Cleaning {table_name}...")
                table_meta = db_metadata.get_table(table_name)

                # Clone to avoid mutating the raw DataFrame
                working_df = df.copy()

                # Clean
                working_df = self._cleaning.clean(
                    working_df, table_meta, self._config,
                )

                # Transform
                working_df = self._transformation.transform(
                    working_df, table_meta, self._config,
                )

                clean_dataframes[table_name] = working_df

                logger.info(
                    f"Cleaned+Transformed '{table_name}': "
                    f"{len(df)}→{len(working_df)} rows, "
                    f"{len(df.columns)}→{len(working_df.columns)} cols",
                    extra={
                        "stage": "clean_transform",
                        "table": table_name,
                        "rows": len(working_df),
                    },
                )

            except Exception as exc:
                logger.warning(f"WARNING: Skipping table {table_name} because {exc}")
                msg = f"Failed to clean/transform '{table_name}': {exc}"
                logger.error(
                    msg,
                    extra={"stage": "clean_transform", "table": table_name, "errors": 1},
                    exc_info=True,
                )
                errors.append(msg)
                raise RuntimeError(msg) from exc

        return clean_dataframes

    def _build_result(
        self,
        db_metadata: DatabaseMetadata,
        raw_dataframes: dict[str, pd.DataFrame],
        clean_dataframes: dict[str, pd.DataFrame],
        profile_reports: dict[str, dict[str, Any]],
        validation_reports: dict[str, dict[str, Any]],
        load_results: dict[str, int],
        started_at: datetime,
        errors: list[str],
    ) -> PipelineResult:
        return PipelineResult(
            db_metadata=db_metadata,
            raw_dataframes=raw_dataframes,
            clean_dataframes=clean_dataframes,
            profile_reports=profile_reports,
            validation_reports=validation_reports,
            load_results=load_results,
            started_at=started_at,
            completed_at=now_utc(),
            errors=errors,
        )

    def _save_summary(self, result: PipelineResult) -> None:
        """Save the pipeline summary report."""
        report_path = Path(self._config.report_dir) / "pipeline_summary.json"
        save_json_report(result.summary(), report_path)
        logger.info(f"Saved pipeline summary: {report_path}")
