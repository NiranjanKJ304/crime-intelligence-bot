"""
Dynamic logical → physical schema mapping for the PostgreSQL tools.

Tool code only ever refers to *logical* tables ("CaseMaster") and *logical*
columns ("case_number"). At startup the mapper reads ``information_schema``
for the configured schemas and resolves every logical name to the physical
``"schema"."table"`` / ``"Column"`` that actually exists in the database.

Resolution order for a logical table ``T``:
  1. ``<clean_schema>.clean_T``  (ETL output, preferred when present)
  2. ``<source_schema>.T``       (raw imported data)

If ``require_clean_schema`` is enabled, step 2 is not attempted and a
missing clean table is reported as a configuration / ETL error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_engine
from app.services.tools.exceptions import IdentifierValidationError, MappingError

logger = logging.getLogger(__name__)

_INTEGER_TYPES = {"bigint", "integer", "smallint", "int", "int2", "int4", "int8"}
_NUMERIC_TYPES = {"numeric", "decimal", "real", "double precision", "float", "float4", "float8"}


@dataclass
class ColumnSpec:
    """Candidate physical names (lowercased) for one logical column."""

    candidates: list[str]
    required: bool = True


@dataclass
class PhysicalColumn:
    name: str
    data_type: str


@dataclass
class ResolvedTable:
    logical_name: str
    schema: str
    table: str
    columns: dict[str, PhysicalColumn] = field(default_factory=dict)  # logical -> physical
    physical_columns: dict[str, PhysicalColumn] = field(default_factory=dict)  # lower(physical) -> physical

    @property
    def qualified(self) -> str:
        return f'"{self.schema}"."{self.table}"'


# Logical schema used by the tools layer. Candidate names are matched
# case-insensitively against the physical columns discovered at runtime.
TABLE_SPECS: dict[str, dict[str, ColumnSpec]] = {
    "CaseMaster": {
        "case_id": ColumnSpec(["casemasterid", "case_id", "caseid", "id"]),
        "case_number": ColumnSpec(["caseno", "case_no", "casenumber", "case_number"]),
        "crime_number": ColumnSpec(["crimeno", "crime_no", "firno", "fir_no", "crimenumber", "crime_number", "fir_number"]),
        "police_person_id": ColumnSpec(["policepersonid", "police_person_id", "employeeid", "officerid", "io_id"]),
        "station_id": ColumnSpec(["policestationid", "stationid", "station_id", "unitid"]),
        "status": ColumnSpec(["casestatusid", "status", "casestatus"], required=False),
    },
    "Employee": {
        "employee_id": ColumnSpec(["employeeid", "employee_id", "officerid", "policepersonid", "id"]),
        "first_name": ColumnSpec(["firstname", "first_name", "name", "employeename", "officername"]),
        "kgid": ColumnSpec(["kgid", "kgid_no"], required=False),
        "designation": ColumnSpec(["designationid", "designation"], required=False),
        "rank": ColumnSpec(["rankid", "rank"], required=False),
    },
    "Victim": {
        "victim_id": ColumnSpec(["victimmasterid", "victimid", "victim_id", "id"]),
        "case_master_id": ColumnSpec(["casemasterid", "case_master_id", "case_id"]),
        "victim_name": ColumnSpec(["victimname", "victim_name", "name"]),
        "age": ColumnSpec(["ageyear", "age"], required=False),
        "gender": ColumnSpec(["genderid", "gender", "sex"], required=False),
    },
    "Accused": {
        "accused_id": ColumnSpec(["accusedmasterid", "accusedid", "accused_id", "id"]),
        "case_master_id": ColumnSpec(["casemasterid", "case_master_id", "case_id"]),
        "accused_name": ColumnSpec(["accusedname", "accused_name", "name"]),
        "age": ColumnSpec(["ageyear", "age"], required=False),
        "gender": ColumnSpec(["genderid", "gender", "sex"], required=False),
        "person_id": ColumnSpec(["personid", "person_id"], required=False),
    },
    "ComplainantDetails": {
        "complainant_id": ColumnSpec(["complainantid", "complainant_id", "id"]),
        "case_master_id": ColumnSpec(["casemasterid", "case_master_id", "case_id"]),
    },
    "ArrestSurrender": {
        "arrest_id": ColumnSpec(["arrestsurrenderid", "arrest_id", "id"]),
        "case_master_id": ColumnSpec(["casemasterid", "case_master_id", "case_id"]),
    },
    "ChargesheetDetails": {
        "chargesheet_id": ColumnSpec(["csid", "chargesheetid", "chargesheet_id", "id"]),
        "case_master_id": ColumnSpec(["casemasterid", "case_master_id", "case_id"]),
        "date": ColumnSpec(["csdate", "chargesheetdate", "date"], required=False),
        "court_name": ColumnSpec(["courtname", "court_name"], required=False),
    },
    "ActSectionAssociation": {
        "case_master_id": ColumnSpec(["casemasterid", "case_master_id", "case_id"]),
    },
}


class ColumnMapper:
    """Resolves logical tables/columns to the physical PostgreSQL schema."""

    _instance: ColumnMapper | None = None

    def __init__(self):
        self.settings = get_settings()
        self.source_schema = self.settings.source_schema
        self.clean_schema = self.settings.clean_schema
        self.require_clean_schema = self.settings.require_clean_schema
        self.engine = get_engine()
        self.specs = TABLE_SPECS
        self._tables: dict[str, ResolvedTable] = {}
        self._catalog: dict[tuple[str, str], dict[str, PhysicalColumn]] = {}
        self._initialized = False

    @classmethod
    def get_instance(cls) -> ColumnMapper:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ── Discovery ─────────────────────────────────────────────────────

    def _load_catalog(self) -> None:
        """Read information_schema for the configured schemas."""
        query = text(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = ANY(:schemas)
            ORDER BY table_schema, table_name, ordinal_position
            """
        )
        schemas = sorted({self.source_schema, self.clean_schema})
        catalog: dict[tuple[str, str], dict[str, PhysicalColumn]] = {}
        try:
            with self.engine.connect() as conn:
                for schema, table, column, data_type in conn.execute(query, {"schemas": schemas}):
                    catalog.setdefault((schema, table), {})[column.lower()] = PhysicalColumn(column, data_type)
        except Exception as exc:
            logger.error("[MAPPER] Failed to read information_schema: %s", exc)
            raise MappingError(f"Database error during mapper initialization: {exc}") from exc
        self._catalog = catalog

    def _candidate_tables(self, logical: str) -> list[tuple[str, str]]:
        candidates = [(self.clean_schema, f"clean_{logical}")]
        if not self.require_clean_schema:
            candidates.append((self.source_schema, logical))
        return candidates

    def _resolve_table(self, logical: str) -> ResolvedTable:
        for schema, table in self._candidate_tables(logical):
            physical_cols = self._catalog.get((schema, table))
            if physical_cols:
                return ResolvedTable(
                    logical_name=logical,
                    schema=schema,
                    table=table,
                    physical_columns=physical_cols,
                )

        diagnostics = self._table_diagnostics(logical)
        if self.require_clean_schema:
            msg = (
                f"Clean schema table '{self.clean_schema}.clean_{logical}' is required "
                f"(REQUIRE_CLEAN_SCHEMA=true) but does not exist. Run the ETL pipeline "
                f"(POST /api/v1/etl/run) or disable REQUIRE_CLEAN_SCHEMA."
            )
        else:
            msg = (
                f"Logical table '{logical}' could not be resolved. Looked for "
                f"{', '.join(f'{s}.{t}' for s, t in self._candidate_tables(logical))}."
            )
        logger.error("[MAPPER] %s\n%s", msg, self._format_diagnostics(diagnostics))
        raise MappingError(msg, diagnostics)

    def _resolve_columns(self, resolved: ResolvedTable, spec: dict[str, ColumnSpec]) -> None:
        for logical_col, col_spec in spec.items():
            for candidate in col_spec.candidates:
                physical = resolved.physical_columns.get(candidate)
                if physical:
                    resolved.columns[logical_col] = physical
                    logger.debug(
                        "[MAPPER] %s.%s -> %s.%s (%s)",
                        resolved.logical_name, logical_col, resolved.qualified, physical.name, physical.data_type,
                    )
                    break
            else:
                if col_spec.required:
                    diagnostics = self._column_diagnostics(resolved, logical_col, col_spec)
                    msg = (
                        f"Required logical column '{logical_col}' of table '{resolved.logical_name}' "
                        f"was not found in {resolved.qualified}."
                    )
                    logger.error("[MAPPER] %s\n%s", msg, self._format_diagnostics(diagnostics))
                    raise MappingError(msg, diagnostics)
                logger.debug(
                    "[MAPPER] Optional column %s.%s not present in %s",
                    resolved.logical_name, logical_col, resolved.qualified,
                )

    def initialize(self) -> None:
        """Discover the physical schema and build all logical mappings."""
        logger.info(
            "[MAPPER] Initializing. source_schema=%s clean_schema=%s require_clean_schema=%s",
            self.source_schema, self.clean_schema, self.require_clean_schema,
        )
        self._load_catalog()
        self._tables = {}

        for logical, spec in self.specs.items():
            resolved = self._resolve_table(logical)
            self._resolve_columns(resolved, spec)
            self._tables[logical] = resolved
            logger.info("[MAPPER] %s -> %s", logical, resolved.qualified)

        self._initialized = True
        logger.info("[MAPPER] Initialization complete: %d logical tables mapped.", len(self._tables))

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def refresh(self) -> None:
        """Re-read information_schema (e.g. after the ETL created clean tables)."""
        self.initialize()

    def resolve_physical_table(self, logical_table: str, *, refresh: bool = False) -> tuple[str, str]:
        """
        Resolve ANY source table (not only the tools-layer TABLE_SPECS) with the
        same policy: <clean_schema>.clean_<T> if the ETL produced it, otherwise
        <source_schema>.<T>; strict clean-only when require_clean_schema is set.
        Raises MappingError with diagnostics when the table exists in neither.
        """
        if refresh or not self._catalog:
            self._load_catalog()
        resolved = self._resolve_table(logical_table)
        return resolved.schema, resolved.table

    # ── Lookups ───────────────────────────────────────────────────────

    def get_resolved_table(self, logical_table: str) -> ResolvedTable:
        self._ensure_initialized()
        resolved = self._tables.get(logical_table)
        if resolved is None:
            diagnostics = self._table_diagnostics(logical_table)
            msg = f"Unknown logical table '{logical_table}'."
            logger.error("[MAPPER] %s\n%s", msg, self._format_diagnostics(diagnostics))
            raise MappingError(msg, diagnostics)
        return resolved

    def get_physical_table(self, logical_table: str) -> tuple[str, str]:
        """Return (schema, table) for a logical table."""
        resolved = self.get_resolved_table(logical_table)
        return resolved.schema, resolved.table

    def get_table(self, logical_table: str) -> str:
        """Return the quoted, schema-qualified physical table name."""
        return self.get_resolved_table(logical_table).qualified

    def has_column(self, logical_table: str, logical_column: str) -> bool:
        return logical_column in self.get_resolved_table(logical_table).columns

    def get_column(self, logical_table: str, logical_column: str) -> str:
        """Return the physical column name for a logical column."""
        resolved = self.get_resolved_table(logical_table)
        physical = resolved.columns.get(logical_column)
        if physical is None:
            spec = self.specs.get(logical_table, {}).get(logical_column)
            diagnostics = self._column_diagnostics(resolved, logical_column, spec)
            msg = f"Mapping not found for {logical_table}.{logical_column}."
            logger.error("[MAPPER] %s\n%s", msg, self._format_diagnostics(diagnostics))
            raise MappingError(msg, diagnostics)
        return physical.name

    def get_column_type(self, logical_table: str, logical_column: str) -> str:
        resolved = self.get_resolved_table(logical_table)
        physical = resolved.columns.get(logical_column)
        if physical is None:
            self.get_column(logical_table, logical_column)  # raises with diagnostics
        return physical.data_type  # type: ignore[union-attr]

    def get_all_columns(self, logical_table: str) -> list[str]:
        """All physical column names of the resolved table (explicit alternative to SELECT *)."""
        resolved = self.get_resolved_table(logical_table)
        return [c.name for c in resolved.physical_columns.values()]

    def coerce_value(self, logical_table: str, logical_column: str, value: Any) -> Any:
        """
        Validate and convert a user-supplied value to the physical column type.

        Raises IdentifierValidationError when the value cannot be represented in
        the column type (e.g. non-numeric text for a bigint column).
        """
        data_type = self.get_column_type(logical_table, logical_column).lower()
        physical = self.get_column(logical_table, logical_column)

        if data_type in _INTEGER_TYPES:
            if isinstance(value, bool):
                raise IdentifierValidationError(f"'{value}' is not a valid {physical}.")
            if isinstance(value, int):
                return value
            text_value = str(value).strip()
            if not text_value.lstrip("-").isdigit():
                raise IdentifierValidationError(f"'{value}' is not a valid numeric {physical}.")
            return int(text_value)

        if data_type in _NUMERIC_TYPES:
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise IdentifierValidationError(f"'{value}' is not a valid numeric {physical}.") from exc

        return str(value).strip()

    # ── Diagnostics ───────────────────────────────────────────────────

    def describe(self) -> dict[str, Any]:
        """Current mapping state, safe to log or expose on an admin endpoint."""
        return {
            "source_schema": self.source_schema,
            "clean_schema": self.clean_schema,
            "require_clean_schema": self.require_clean_schema,
            "tables": {
                logical: {
                    "physical": f"{r.schema}.{r.table}",
                    "columns": {lc: pc.name for lc, pc in r.columns.items()},
                }
                for logical, r in self._tables.items()
            },
        }

    def _table_diagnostics(self, logical: str) -> dict[str, Any]:
        return {
            "logical_table": logical,
            "configured_schemas": {
                "source_schema": self.source_schema,
                "clean_schema": self.clean_schema,
                "require_clean_schema": self.require_clean_schema,
            },
            "expected_physical_tables": [f"{s}.{t}" for s, t in self._candidate_tables(logical)],
            "available_physical_tables": sorted(f"{s}.{t}" for s, t in self._catalog),
        }

    def _column_diagnostics(self, resolved: ResolvedTable, logical_column: str, spec: ColumnSpec | None) -> dict[str, Any]:
        return {
            "logical_table": resolved.logical_name,
            "requested_logical_column": logical_column,
            "configured_schemas": {
                "source_schema": self.source_schema,
                "clean_schema": self.clean_schema,
                "require_clean_schema": self.require_clean_schema,
            },
            "resolved_physical_table": f"{resolved.schema}.{resolved.table}",
            "expected_candidates": list(spec.candidates) if spec else [],
            "available_columns": [c.name for c in resolved.physical_columns.values()],
            "mapped_columns": {lc: pc.name for lc, pc in resolved.columns.items()},
        }

    @staticmethod
    def _format_diagnostics(diagnostics: dict[str, Any]) -> str:
        lines = []
        for key, value in diagnostics.items():
            label = key.replace("_", " ").capitalize()
            if isinstance(value, dict):
                lines.append(f"  {label}:")
                for k, v in value.items():
                    lines.append(f"    {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"  {label}: {', '.join(map(str, value)) or '(none)'}")
            else:
                lines.append(f"  {label}: {value}")
        return "\n".join(lines)
