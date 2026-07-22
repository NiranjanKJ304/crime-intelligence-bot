"""
ETL API Routes.

REST endpoints for triggering, monitoring, and inspecting the
ETL pipeline and its outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.core.database import get_engine
from app.etl.config import ETLConfig, build_etl_config
from app.etl.pipeline import ETLPipeline, PipelineResult
from app.etl.schema_discovery import SchemaDiscovery

router = APIRouter(prefix="/api/v1/etl", tags=["ETL"])

# ── Module-level state ─────────────────────────────────────────────
_pipeline_instance: ETLPipeline | None = None
_last_result: PipelineResult | None = None


def _get_pipeline() -> ETLPipeline:
    """Get or create the pipeline singleton."""
    global _pipeline_instance
    if _pipeline_instance is None:
        engine = get_engine()
        config = build_etl_config()
        _pipeline_instance = ETLPipeline(engine, config)
    return _pipeline_instance


# ══════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════


@router.post("/run", summary="Run the full ETL pipeline")
def run_pipeline() -> dict[str, Any]:
    """
    Trigger a full ETL pipeline run.

    Executes: Discovery → Extract → Profile → Clean → Transform → Validate → Load
    """
    global _last_result
    pipeline = _get_pipeline()

    try:
        result = pipeline.run()
        _last_result = result
        return result.summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")


@router.get("/status", summary="Get last pipeline run status")
def get_status() -> dict[str, Any]:
    """Return the status and summary of the last pipeline run."""
    pipeline = _get_pipeline()
    result = pipeline.last_result or _last_result

    if result is None:
        return {
            "status": "no_runs",
            "message": "No pipeline runs have been executed yet.",
        }

    return result.summary()


@router.get("/schema", summary="Discover and return database schema")
def get_schema() -> dict[str, Any]:
    """
    Run database discovery and return the full schema metadata.
    Does NOT trigger the full pipeline — only the discovery step.
    """
    engine = get_engine()
    config = build_etl_config()
    discovery = SchemaDiscovery(engine)

    try:
        db_metadata = discovery.discover(config.source_schema)
        return db_metadata.model_dump_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {exc}")


@router.get("/tables", summary="List all discovered tables")
def list_tables() -> dict[str, Any]:
    """List all tables discovered in the source schema."""
    engine = get_engine()
    config = build_etl_config()
    discovery = SchemaDiscovery(engine)

    try:
        db_metadata = discovery.discover(config.source_schema)
        return {
            "schema": config.source_schema,
            "tables": [
                {
                    "name": t.name,
                    "columns": len(t.columns),
                    "primary_keys": t.primary_keys,
                    "foreign_keys": len(t.foreign_keys),
                    "row_count": t.row_count,
                }
                for t in db_metadata.all_tables.values()
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {exc}")


@router.get("/relationships", summary="Get relationship graph")
def get_relationships() -> dict[str, Any]:
    """Return the discovered table relationship graph."""
    engine = get_engine()
    config = build_etl_config()
    discovery = SchemaDiscovery(engine)

    try:
        db_metadata = discovery.discover(config.source_schema)
        return {
            "relationships": [
                rel.model_dump() for rel in db_metadata.all_relationships
            ],
            "graph": db_metadata.relationship_graph,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get relationships: {exc}")


@router.get(
    "/reports/profile/{table_name}",
    summary="Get profiling report for a table",
)
def get_profile_report(table_name: str) -> dict[str, Any]:
    """Return the data profiling report for a specific table."""
    settings = get_settings()
    report_path = Path(settings.report_dir) / "profile" / f"{table_name}_profile.json"

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Profile report for '{table_name}' not found. Run the pipeline first.",
        )

    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get(
    "/reports/validation/{table_name}",
    summary="Get validation report for a table",
)
def get_validation_report(table_name: str) -> dict[str, Any]:
    """Return the validation report for a specific table."""
    settings = get_settings()
    report_path = Path(settings.report_dir) / "validation" / f"{table_name}_validation.json"

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Validation report for '{table_name}' not found. Run the pipeline first.",
        )

    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/reports/summary", summary="Get pipeline summary report")
def get_summary_report() -> dict[str, Any]:
    """Return the overall pipeline summary report."""
    settings = get_settings()
    report_path = Path(settings.report_dir) / "pipeline_summary.json"

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Pipeline summary not found. Run the pipeline first.",
        )

    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)
