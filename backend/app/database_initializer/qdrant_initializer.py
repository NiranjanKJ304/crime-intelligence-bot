"""
Qdrant Initialization Module.
Checks if Qdrant collection is populated, and restores from snapshot if needed.
"""

from __future__ import annotations

import logging
import os
import httpx

from qdrant_client import QdrantClient

from app.core.config import Settings
from app.embeddings.config import build_embedding_config

logger = logging.getLogger("crime_bot")


class QdrantInitializer:
    """Initializes Qdrant with backup if empty."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.config = build_embedding_config(settings)
        self.client = QdrantClient(host=self.config.qdrant_host, port=self.config.qdrant_port)

    def is_empty(self) -> bool:
        """Check if Qdrant collection is empty."""
        try:
            collection = self.client.get_collection(self.config.qdrant_collection)
            return collection.points_count == 0
        except Exception:
            # Collection might not exist
            return True

    def initialize(self) -> bool:
        """Run the Qdrant initialization process."""
        logger.info("[INIT] Checking Qdrant...")
        
        if not self.is_empty():
            logger.info("[INIT] Qdrant collection is already populated. Skipping initialization.")
            return True

        logger.info("[INIT] Qdrant collection empty")
        
        backup_path = self.settings.qdrant_backup_path
        if backup_path and os.path.exists(backup_path):
            logger.info(f"[INIT] Restoring Qdrant from snapshot {backup_path}")
            try:
                # Assuming backup_path is a snapshot file (.snapshot)
                url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{self.config.qdrant_collection}/snapshots/recover"
                
                # Qdrant snapshot recovery requires uploading the file or specifying a local path 
                # (which must be accessible to the Qdrant server, not the backend).
                # The easiest robust way is to use the python client if it supports it, 
                # or just log it since the previous implementation had a script for this.
                logger.warning(
                    f"[INIT] Snapshot restore via API requires Qdrant server access to the file. "
                    f"Please run the Qdrant restore script manually if this fails."
                )
                # Client snapshot recover (file must exist on the qdrant server path)
                self.client.recover_snapshot(
                    collection_name=self.config.qdrant_collection,
                    location=backup_path
                )
                logger.info("[INIT] Qdrant snapshot restored successfully.")
                return True
            except Exception as e:
                logger.error(f"[INIT] Failed to restore Qdrant snapshot: {e}")
                return False
        else:
            logger.warning(
                "[INIT] No Qdrant backup path provided or file does not exist. "
                "Embeddings will need to be generated manually via the API."
            )
            return True # It's not a hard failure, just empty.
