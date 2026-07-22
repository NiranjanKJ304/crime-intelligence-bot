"""
Document Orchestrator.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.engine import Engine

from app.document_generation.accused_builder import AccusedProfileBuilder
from app.document_generation.case_builder import CaseSummaryBuilder
from app.document_generation.config import DocumentConfig
from app.document_generation.court_builder import CourtSummaryBuilder
from app.document_generation.district_builder import DistrictSummaryBuilder
from app.document_generation.document_store import DocumentStore
from app.document_generation.officer_builder import OfficerProfileBuilder
from app.document_generation.schemas import BuildResult
from app.document_generation.statistics import StatisticsTracker
from app.document_generation.validation import DocumentValidator
from app.document_generation.victim_builder import VictimProfileBuilder

logger = logging.getLogger(__name__)


class DocumentOrchestrator:
    """Coordinates the generation of all AI Documents."""

    def __init__(self, engine: Engine, config: DocumentConfig):
        self.engine = engine
        self.config = config
        self.store = DocumentStore(config.document_store_path)
        self.validator = DocumentValidator(config)
        self.stats = StatisticsTracker()
        
        self.builders = [
            DistrictSummaryBuilder(engine, config),
            CourtSummaryBuilder(engine, config),
            OfficerProfileBuilder(engine, config),
            CaseSummaryBuilder(engine, config),
            AccusedProfileBuilder(engine, config),
            VictimProfileBuilder(engine, config),
        ]

    def build_all(self) -> BuildResult:
        """Generate all documents from scratch."""
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()
        
        self.stats.reset()
        logger.info("Starting full AI Document Generation")
        
        for builder in self.builders:
            doc_type = builder.document_type
            logger.info(f"Building {doc_type} documents...")
            
            for batch in builder.build_all():
                if not batch:
                    continue
                    
                # Validate
                validation_results = self.validator.validate_batch(batch)
                
                valid_docs = []
                for doc, res in zip(batch, validation_results):
                    self.stats.record_validation(res.is_valid, res.issues)
                    if res.is_valid:
                        valid_docs.append(doc)
                    else:
                        for issue in res.issues:
                            self.stats.record_error(
                                doc_type, 
                                doc.metadata.entity_id, 
                                f"Validation {issue.severity}: {issue.message}"
                            )
                
                # Save
                if valid_docs:
                    self.store.save_batch(valid_docs)
                    self.stats.record_generated(doc_type, len(valid_docs))
                    
        # Finalize
        self.store.rebuild_index()
        duration = time.time() - start_time
        
        stats_summary = self.stats.summary()
        
        return BuildResult(
            status="success" if not self.stats.errors else "completed_with_errors",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(duration, 2),
            documents_generated=stats_summary["documents_generated"],
            total_documents=stats_summary["total_documents"],
            validation=stats_summary["validation"],
            errors=stats_summary["errors"]
        )
        
    def rebuild(self) -> BuildResult:
        """Delete all documents and rebuild."""
        self.store.delete_all()
        return self.build_all()
