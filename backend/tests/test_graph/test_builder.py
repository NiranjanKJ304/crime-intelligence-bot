"""
GraphBuilder source resolution: logical tables -> physical schema.table via
the shared mapper policy; honest failure reporting when nothing can load.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.graph import builder as builder_module
from app.graph.builder import GraphBuildError, GraphBuilder
from app.graph.config import GraphConfig
from app.graph.queries.nodes import NODE_QUERIES
from app.graph.queries.relationships import RELATIONSHIP_QUERIES
from tests.test_services.conftest import PUBLIC_SCHEMA, build_catalog, make_mapper

GRAPH_TABLES = {**PUBLIC_SCHEMA, "District": [("DistrictID", "bigint"), ("DistrictName", "text")],
                "Unit": [("UnitID", "bigint"), ("UnitName", "text"), ("DistrictID", "bigint")],
                "Court": [("CourtID", "bigint"), ("CourtName", "text"), ("DistrictID", "bigint")]}


class FakeResult:
    def __init__(self, rows):
        self._rows = rows
        self._done = False

    def keys(self):
        return list(self._rows[0].keys()) if self._rows else []

    def fetchmany(self, _n):
        if self._done:
            return []
        self._done = True
        return [tuple(r.values()) for r in self._rows]


class FakeEngine:
    def __init__(self):
        self.sql: list[str] = []

    @contextmanager
    def connect(self):
        engine = self

        class Conn:
            def execution_options(self, **_):
                return self

            def execute(self, stmt):
                engine.sql.append(str(stmt))
                return FakeResult([{"ID": 1}])

        yield Conn()


class FakeNeoSession:
    def __init__(self):
        self.runs = 0

    def run(self, *_a, **_k):
        self.runs += 1
        return SimpleNamespace(consume=lambda: SimpleNamespace(counters=SimpleNamespace(nodes_created=1, relationships_created=1)))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def config():
    return GraphConfig(source_schema="public", clean_schema="clean", require_clean_schema=False,
                       neo4j_uri="bolt://x", neo4j_username="u", neo4j_password="p", batch_size=100)


@pytest.fixture(autouse=True)
def fake_neo4j(monkeypatch):
    session = FakeNeoSession()
    monkeypatch.setattr(builder_module, "get_neo4j_driver", lambda: SimpleNamespace(session=lambda: session))
    monkeypatch.setattr(builder_module, "init_graph_schema", lambda _s: None)
    return session


def _builder(monkeypatch, catalog, config, **mapper_kwargs):
    mapper = make_mapper(monkeypatch, catalog, **mapper_kwargs)
    engine = FakeEngine()
    return GraphBuilder(engine, config, mapper=mapper), engine


def test_query_keys_are_logical_not_physical():
    assert all(not key.startswith("clean_") for key in NODE_QUERIES)
    assert all(not key.startswith("clean_") for key in RELATIONSHIP_QUERIES)
    assert {"CaseMaster", "Employee", "Accused", "Victim", "District", "Unit", "Court"} <= set(NODE_QUERIES)


def test_resolves_public_tables_when_clean_missing(monkeypatch, config):
    graph_builder, engine = _builder(monkeypatch, build_catalog("public", GRAPH_TABLES), config)
    stats = graph_builder.build()

    assert stats["status"] == "success"
    assert stats["errors"] == []
    assert stats["tables_processed"] == len(NODE_QUERIES)
    assert stats["source_tables"]["CaseMaster"] == "public.CaseMaster"
    assert stats["source_tables"]["District"] == "public.District"
    assert 'SELECT * FROM "public"."CaseMaster"' in engine.sql
    assert not any("clean_" in sql for sql in engine.sql)


def test_prefers_clean_tables_when_etl_populated_them(monkeypatch, config):
    catalog = build_catalog("public", GRAPH_TABLES)
    catalog.update(build_catalog("clean", GRAPH_TABLES, prefix="clean_"))
    graph_builder, engine = _builder(monkeypatch, catalog, config)
    stats = graph_builder.build()

    assert stats["status"] == "success"
    assert stats["source_tables"]["CaseMaster"] == "clean.clean_CaseMaster"
    assert all('"clean"."clean_' in sql for sql in engine.sql)


def test_no_tables_anywhere_is_a_hard_failure(monkeypatch, config):
    graph_builder, engine = _builder(monkeypatch, {}, config)
    with pytest.raises(GraphBuildError) as exc:
        graph_builder.build()

    stats = exc.value.stats
    assert stats["status"] == "failed"
    assert stats["tables_processed"] == 0 and stats["nodes_created"] == 0
    assert stats["tables_failed"] == len(NODE_QUERIES)
    assert engine.sql == []  # nothing was queried
    first = stats["errors"][0]
    assert "clean.clean_District" in first and "public.District" in first
    assert "POST /api/v1/etl/run" in first


def test_require_clean_schema_reports_etl_error(monkeypatch, config):
    strict = GraphConfig(**{**config.__dict__, "require_clean_schema": True})
    graph_builder, _ = _builder(monkeypatch, build_catalog("public", GRAPH_TABLES), strict, require_clean=True)
    with pytest.raises(GraphBuildError) as exc:
        graph_builder.build()
    assert "REQUIRE_CLEAN_SCHEMA" in exc.value.stats["errors"][0]


def test_partial_missing_table_is_reported_not_hidden(monkeypatch, config):
    tables = {k: v for k, v in GRAPH_TABLES.items() if k != "Court"}
    graph_builder, _ = _builder(monkeypatch, build_catalog("public", tables), config)
    stats = graph_builder.build()

    assert stats["status"] == "completed_with_errors"
    assert stats["tables_failed"] == 1
    assert stats["tables_processed"] == len(NODE_QUERIES) - 1
    assert any("'Court'" in e and "public.Court" in e for e in stats["errors"])
