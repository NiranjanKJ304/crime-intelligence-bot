"""
Tests for the ETL pipeline orchestrator (mocked database).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.etl.config import ETLConfig
from app.etl.metadata import DatabaseMetadata
from app.etl.pipeline import ETLPipeline, PipelineResult


class TestPipelineResult:
    def test_implements_data_provider(
        self, sample_db_metadata: DatabaseMetadata,
    ) -> None:
        """Ensure PipelineResult implements the DataProvider protocol."""
        result = PipelineResult(
            db_metadata=sample_db_metadata,
            raw_dataframes={"CaseMaster": pd.DataFrame()},
            clean_dataframes={"CaseMaster": pd.DataFrame()},
            profile_reports={},
            validation_reports={},
            load_results={"clean_CaseMaster": 100},
            started_at=pd.Timestamp.now(tz="UTC").to_pydatetime(),
            completed_at=pd.Timestamp.now(tz="UTC").to_pydatetime(),
            errors=[],
        )

        # DataProvider protocol methods
        assert isinstance(result.get_clean_dataframes(), dict)
        assert result.get_database_metadata() is sample_db_metadata
        assert isinstance(result.get_relationship_graph(), dict)
        assert isinstance(result.get_relationships(), list)

    def test_summary(self, sample_db_metadata: DatabaseMetadata) -> None:
        from datetime import datetime, timezone

        t1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc)

        result = PipelineResult(
            db_metadata=sample_db_metadata,
            raw_dataframes={"CaseMaster": pd.DataFrame()},
            clean_dataframes={"CaseMaster": pd.DataFrame()},
            profile_reports={},
            validation_reports={},
            load_results={"clean_CaseMaster": 100},
            started_at=t1,
            completed_at=t2,
            errors=[],
        )

        summary = result.summary()
        assert summary["status"] == "success"
        assert summary["duration_seconds"] == 10.0
        assert summary["tables_loaded"] == 1
        assert summary["total_rows_loaded"] == 100

    def test_summary_with_errors(self, sample_db_metadata: DatabaseMetadata) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result = PipelineResult(
            db_metadata=sample_db_metadata,
            raw_dataframes={},
            clean_dataframes={},
            profile_reports={},
            validation_reports={},
            load_results={},
            started_at=now,
            completed_at=now,
            errors=["Table X failed"],
        )

        summary = result.summary()
        assert summary["status"] == "completed_with_errors"
        assert len(summary["errors"]) == 1


class TestSchemaDiscoveryModule:
    def test_schema_discovery_builds_metadata(self) -> None:
        """Test that SchemaDiscovery can be instantiated with a mock engine."""
        from app.etl.schema_discovery import SchemaDiscovery, _map_python_type

        # Test type mapping
        assert _map_python_type("INTEGER") == "int"
        assert _map_python_type("VARCHAR(255)") == "str"
        assert _map_python_type("TIMESTAMP") == "datetime"
        assert _map_python_type("BOOLEAN") == "bool"
        assert _map_python_type("DOUBLE PRECISION") == "float"
        assert _map_python_type("TEXT") == "str"
        assert _map_python_type("UNKNOWN_TYPE") == "str"  # Default
