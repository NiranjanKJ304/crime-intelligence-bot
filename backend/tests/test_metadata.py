"""
Tests for ETL metadata Pydantic models.
"""

from __future__ import annotations

from app.etl.metadata import (
    ColumnMetadata,
    DatabaseMetadata,
    ForeignKeyMetadata,
    RelationshipMetadata,
    SchemaMetadata,
    TableMetadata,
)


class TestColumnMetadata:
    def test_basic_column(self) -> None:
        col = ColumnMetadata(name="id", data_type="INTEGER", python_type="int")
        assert col.name == "id"
        assert col.data_type == "INTEGER"
        assert col.nullable is True
        assert col.is_primary_key is False

    def test_pk_column(self) -> None:
        col = ColumnMetadata(
            name="id", data_type="INTEGER", python_type="int",
            is_primary_key=True, nullable=False,
        )
        assert col.is_primary_key is True
        assert col.nullable is False


class TestTableMetadata:
    def test_column_names(self, sample_table_metadata: TableMetadata) -> None:
        names = sample_table_metadata.column_names
        assert "case_id" in names
        assert "fir_no" in names

    def test_column_map(self, sample_table_metadata: TableMetadata) -> None:
        col_map = sample_table_metadata.column_map
        assert "case_id" in col_map
        assert col_map["case_id"].is_primary_key is True

    def test_has_column(self, sample_table_metadata: TableMetadata) -> None:
        assert sample_table_metadata.has_column("case_id") is True
        assert sample_table_metadata.has_column("nonexistent") is False

    def test_get_column(self, sample_table_metadata: TableMetadata) -> None:
        col = sample_table_metadata.get_column("case_id")
        assert col is not None
        assert col.python_type == "int"

        assert sample_table_metadata.get_column("nonexistent") is None

    def test_text_columns(self, sample_table_metadata: TableMetadata) -> None:
        text_cols = sample_table_metadata.text_columns
        text_names = [c.name for c in text_cols]
        assert "narrative" in text_names
        assert "fir_no" in text_names

    def test_numeric_columns(self, sample_table_metadata: TableMetadata) -> None:
        num_cols = sample_table_metadata.numeric_columns
        num_names = [c.name for c in num_cols]
        assert "case_id" in num_names

    def test_datetime_columns(self, sample_table_metadata: TableMetadata) -> None:
        dt_cols = sample_table_metadata.datetime_columns
        dt_names = [c.name for c in dt_cols]
        assert "crime_date" in dt_names


class TestDatabaseMetadata:
    def test_all_tables(self, sample_db_metadata: DatabaseMetadata) -> None:
        tables = sample_db_metadata.all_tables
        assert "CaseMaster" in tables
        assert "Accused" in tables

    def test_relationship_graph(self, sample_db_metadata: DatabaseMetadata) -> None:
        graph = sample_db_metadata.relationship_graph
        assert "Accused" in graph
        assert "CaseMaster" in graph["Accused"]

    def test_get_related_tables(self, sample_db_metadata: DatabaseMetadata) -> None:
        related = sample_db_metadata.get_related_tables("Accused")
        assert "CaseMaster" in related

    def test_get_table(self, sample_db_metadata: DatabaseMetadata) -> None:
        table = sample_db_metadata.get_table("CaseMaster")
        assert table is not None
        assert table.name == "CaseMaster"

    def test_model_dump_summary(self, sample_db_metadata: DatabaseMetadata) -> None:
        summary = sample_db_metadata.model_dump_summary()
        assert summary["total_tables"] == 2
        assert summary["total_relationships"] == 1
        assert "CaseMaster" in summary["tables"]
