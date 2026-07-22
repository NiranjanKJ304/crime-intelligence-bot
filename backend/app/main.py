"""
FastAPI Application Entry Point.

Crime-Bot Backend with integrated ETL Pipeline.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.neo4j_db import init_neo4j_driver, close_neo4j_driver


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — setup and teardown."""
    # Startup
    setup_logging()
    settings = get_settings()

    # Ensure report/log directories exist
    settings.log_path  # noqa: B018 — triggers directory creation
    settings.report_path  # noqa: B018

    # Init Neo4j Driver
    try:
        init_neo4j_driver()
    except Exception as e:
        # We don't want the app to crash if Neo4j is down during startup, 
        # but we should log it.
        logging.getLogger("crime_bot").error(f"Failed to initialize Neo4j: {e}")

    yield

    # Shutdown
    close_neo4j_driver()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Crime Analytics Backend with ETL Pipeline. "
            "Automatically discovers, profiles, cleans, transforms, "
            "validates, and loads crime data from PostgreSQL."
        ),
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────
    from app.api.v1.etl_routes import router as etl_router
    from app.api.v1.graph_routes import router as graph_router
    from app.api.v1.document_routes import router as document_router
    from app.api.v1.embedding_routes import router as embedding_router
    from app.api.v1.retrieval_routes import router as retrieval_router
    
    app.include_router(etl_router)
    app.include_router(graph_router)
    app.include_router(document_router)
    app.include_router(embedding_router)
    app.include_router(retrieval_router)

    # ── Health Check ───────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": settings.app_version}

    return app


# Module-level app instance for uvicorn
app = create_app()
