"""
Tests for schema discovery module.
"""

from __future__ import annotations

from app.etl.schema_discovery import _map_python_type


class TestPythonTypeMapping:
    def test_integer_types(self) -> None:
        assert _map_python_type("INTEGER") == "int"
        assert _map_python_type("BIGINT") == "int"
        assert _map_python_type("SMALLINT") == "int"
        assert _map_python_type("SERIAL") == "int"

    def test_float_types(self) -> None:
        assert _map_python_type("NUMERIC(10,2)") == "float"
        assert _map_python_type("DECIMAL") == "float"
        assert _map_python_type("REAL") == "float"
        assert _map_python_type("DOUBLE PRECISION") == "float"

    def test_string_types(self) -> None:
        assert _map_python_type("TEXT") == "str"
        assert _map_python_type("VARCHAR(255)") == "str"
        assert _map_python_type("CHARACTER VARYING(100)") == "str"
        assert _map_python_type("CHAR(10)") == "str"

    def test_datetime_types(self) -> None:
        assert _map_python_type("TIMESTAMP") == "datetime"
        assert _map_python_type("TIMESTAMP WITHOUT TIME ZONE") == "datetime"
        assert _map_python_type("TIMESTAMP WITH TIME ZONE") == "datetime"
        assert _map_python_type("DATE") == "date"

    def test_boolean_types(self) -> None:
        assert _map_python_type("BOOLEAN") == "bool"
        assert _map_python_type("BOOL") == "bool"

    def test_json_types(self) -> None:
        assert _map_python_type("JSON") == "dict"
        assert _map_python_type("JSONB") == "dict"

    def test_unknown_defaults_to_str(self) -> None:
        assert _map_python_type("CUSTOM_TYPE") == "str"
        assert _map_python_type("UNKNOWN") == "str"
