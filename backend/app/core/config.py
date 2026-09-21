"""
Application configuration using Pydantic Settings.

Reads all configuration from environment variables / .env file.
Provides a singleton accessor for the global settings instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings sourced from .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = "postgresql://user:password@localhost:5432/crime_db"

    # ── Neo4j Database ────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"

    # ── ETL Schema Configuration ──────────────────────────────────────
    source_schema: str = "public"
    clean_schema: str = "clean"

    # ── Directories ───────────────────────────────────────────────────
    log_dir: str = "app/etl/logs"
    report_dir: str = "app/etl/reports"

    # ── ETL Tuning ────────────────────────────────────────────────────
    batch_size: int = 10_000
    etl_workers: int = 4

    # ── Evidence Column Detection ─────────────────────────────────────
    # Columns whose names contain any of these substrings will NOT be
    # text-cleaned (preserves FIR narratives, evidence, etc.)
    evidence_column_patterns: str = (
        "narrative,evidence,description,remarks,statement,"
        "fir_content,complaint_text"
    )

    # ── Coordinate Column Detection ───────────────────────────────────
    latitude_patterns: str = "latitude,lat,coord_lat"
    longitude_patterns: str = "longitude,lon,lng,coord_lon"

    # ── Application ───────────────────────────────────────────────────
    app_name: str = "Crime-Bot Backend"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── AI Document Generation ────────────────────────────────────────
    document_store_path: str = "app/document_generation/store"
    document_batch_size: int = 5000
    max_document_length: int = 10000

    # ── Embedding Platform ────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_batch_size: int = 256
    embedding_device: str = "cpu"
    qdrant_path: str = "./qdrant_storage"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "crime_intelligence"
    top_k: int = 10

    # ── Retrieval Engine ──────────────────────────────────────────────
    default_score_threshold: float = 0.5
    query_cache_size: int = 256
    query_cache_ttl: int = 300
    max_context_tokens: int = 4000
    default_document_limit: int = 20

    # ── LLM / RAG ────────────────────────────────────────────────────
    llm_provider: str = "groq"
    groq_api_key: str = ""
    model_name: str = "llama-3.3-70b-versatile"
    temperature: float = 0.2
    max_tokens: int = 4096
    llm_timeout: int = 30
    llm_max_retries: int = 3
    max_context_documents: int = 10

    # ── Database Initialization ───────────────────────────────────────
    auto_initialize_database: bool = True
    postgres_backup_path: str = ""
    postgres_csv_path: str = ""
    postgres_schema_path: str = ""
    neo4j_backup_path: str = ""
    neo4j_cypher_path: str = ""
    qdrant_backup_path: str = ""

    # ── Helpers ────────────────────────────────────────────────────────

    @property
    def evidence_patterns_list(self) -> list[str]:
        """Return evidence column patterns as a list of lowercase strings."""
        return [p.strip().lower() for p in self.evidence_column_patterns.split(",") if p.strip()]

    @property
    def latitude_patterns_list(self) -> list[str]:
        return [p.strip().lower() for p in self.latitude_patterns.split(",") if p.strip()]

    @property
    def longitude_patterns_list(self) -> list[str]:
        return [p.strip().lower() for p in self.longitude_patterns.split(",") if p.strip()]

    @property
    def log_path(self) -> Path:
        path = Path(self.log_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def report_path(self) -> Path:
        path = Path(self.report_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
