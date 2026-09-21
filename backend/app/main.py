"""
FastAPI Application Entry Point.

Crime-Bot Backend with integrated ETL Pipeline.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
import multiprocessing
import time
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.neo4j_db import init_neo4j_driver, close_neo4j_driver
from app.embeddings.config import build_embedding_config
from app.embeddings.model_manager import ModelManager


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
        
    # Database Initialization (PostgreSQL, Neo4j, Qdrant)
    try:
        if settings.auto_initialize_database:
            from app.database_initializer.initializer import DatabaseInitializer
            initializer = DatabaseInitializer(settings)
            # Database initializer is synchronous because it uses synchronous SQLAlchemy/psycopg2
            initializer.initialize_all()
    except Exception as e:
        logging.getLogger("crime_bot").error(f"Database Initialization failed: {e}", exc_info=True)

    # Initialize ColumnMapper
    try:
        from app.services.tools.mapper import ColumnMapper
        mapper = ColumnMapper.get_instance()
        mapper.initialize()
    except Exception as e:
        logging.getLogger("crime_bot").error(f"ColumnMapper Initialization failed: {e}", exc_info=True)
        raise RuntimeError(f"Startup validation failed: {e}")

        
    # Validate and Init Embedding Model
    logger = logging.getLogger("crime_bot")
    try:
        cache_dir = os.environ.get("HF_HOME", os.path.join(os.path.expanduser("~"), ".cache", "huggingface"))
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir, exist_ok=True)
                logger.info(f"Created cache directory at {cache_dir}")
            except Exception as e:
                raise RuntimeError(f"Failed to create cache directory {cache_dir}: {e}")
                
        if not os.path.exists(cache_dir):
            raise RuntimeError(f"Cache directory {cache_dir} does not exist even after creation attempt.")
            
        if not os.access(cache_dir, os.W_OK):
            raise RuntimeError(f"Cache directory {cache_dir} is not writable.")
            
        emb_config = build_embedding_config(settings)
        mgr = ModelManager.get_instance(emb_config)
        
        start_time = time.perf_counter()
        mgr.load_model()
        load_time = time.perf_counter() - start_time
        
        if mgr.dimensions != 384:
            raise RuntimeError(f"Invalid embedding dimension: {mgr.dimensions}. Expected 384.")
            
        logger.info(
            "Embedding Model Initialization Complete:\n"
            f"  Model: {mgr.model_name}\n"
            f"  Dimension: {mgr.dimensions}\n"
            f"  Cache Directory: {cache_dir}\n"
            f"  HF_HOME: {os.environ.get('HF_HOME')}\n"
            f"  TRANSFORMERS_CACHE: {os.environ.get('TRANSFORMERS_CACHE')}\n"
            f"  Device: {emb_config.embedding_device}\n"
            f"  CPU Threads: {multiprocessing.cpu_count()}\n"
            f"  Load Time: {load_time:.2f}s\n"
            f"  Qdrant Host: {emb_config.qdrant_host}:{emb_config.qdrant_port}"
        )
    except Exception as e:
        logger.error(f"Failed to initialize embedding model: {e}", exc_info=True)
        raise RuntimeError(f"Startup validation failed: {e}")

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
    from app.api.v1.chat_routes import router as chat_router
    
    app.include_router(etl_router)
    app.include_router(graph_router)
    app.include_router(document_router)
    app.include_router(embedding_router)
    app.include_router(retrieval_router)
    app.include_router(chat_router)

    # ── Health Check ───────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": settings.app_version}

    return app


# Module-level app instance for uvicorn
app = create_app()
