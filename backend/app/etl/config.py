"""
ETL-specific configuration.

Extends the core settings with ETL-specific helpers and
column classification logic driven entirely by metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class ETLConfig:
    """
    Immutable ETL configuration derived from application settings.

    This object is passed into every pipeline stage so that no stage
    needs to import Settings directly — enabling easy testing via
    constructor injection.
    """

    source_schema: str
    clean_schema: str
    batch_size: int
    evidence_patterns: list[str]
    latitude_patterns: list[str]
    longitude_patterns: list[str]
    report_dir: str
    log_dir: str

    # ── Date column detection patterns ────────────────────────────
    date_column_patterns: list[str] = field(
        default_factory=lambda: [
            "date", "dt", "datetime", "timestamp", "created_at",
            "updated_at", "registered_on", "occurred_on", "reported_on",
        ]
    )

    # ── Phone column detection patterns ───────────────────────────
    phone_column_patterns: list[str] = field(
        default_factory=lambda: ["phone", "mobile", "contact", "cell", "tel"]
    )

    # ── Gender column detection patterns ──────────────────────────
    gender_column_patterns: list[str] = field(
        default_factory=lambda: ["gender", "sex"]
    )

    # ── Address column detection patterns ─────────────────────────
    address_column_patterns: list[str] = field(
        default_factory=lambda: [
            "address", "addr", "street", "city", "district",
            "state", "pincode", "zip", "locality", "area",
        ]
    )

    # ── Crime/FIR number patterns ─────────────────────────────────
    crime_number_patterns: list[str] = field(
        default_factory=lambda: ["fir_no", "crime_no", "fir_number", "crime_number", "case_no"]
    )

    def is_evidence_column(self, column_name: str) -> bool:
        """Check if a column should be preserved (not text-cleaned)."""
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.evidence_patterns)

    def is_date_column(self, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.date_column_patterns)

    def is_phone_column(self, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.phone_column_patterns)

    def is_gender_column(self, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.gender_column_patterns)

    def is_latitude_column(self, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.latitude_patterns)

    def is_longitude_column(self, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.longitude_patterns)

    def is_coordinate_column(self, column_name: str) -> bool:
        return self.is_latitude_column(column_name) or self.is_longitude_column(column_name)

    def is_address_column(self, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.address_column_patterns)

    def is_crime_number_column(self, column_name: str) -> bool:
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in self.crime_number_patterns)


def build_etl_config(settings: Settings | None = None) -> ETLConfig:
    """Build an ETLConfig from application settings."""
    settings = settings or get_settings()
    return ETLConfig(
        source_schema=settings.source_schema,
        clean_schema=settings.clean_schema,
        batch_size=settings.batch_size,
        evidence_patterns=settings.evidence_patterns_list,
        latitude_patterns=settings.latitude_patterns_list,
        longitude_patterns=settings.longitude_patterns_list,
        report_dir=settings.report_dir,
        log_dir=settings.log_dir,
    )
