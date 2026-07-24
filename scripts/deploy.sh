#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "Starting Deployment Process..."

if [ -d "qdrant_storage" ] && [ "$(ls -A qdrant_storage 2>/dev/null)" ]; then
    echo "Qdrant storage exists locally. Starting normally..."
    docker compose up -d
else
    echo "Qdrant storage not found locally."
    
    if [ -n "$QDRANT_BACKUP_URL" ]; then
        echo "Downloading backup from $QDRANT_BACKUP_URL..."
        wget -qO qdrant_storage.tar.gz "$QDRANT_BACKUP_URL" || curl -sL "$QDRANT_BACKUP_URL" -o qdrant_storage.tar.gz
        
        if [ -f "qdrant_storage.tar.gz" ]; then
            echo "Extracting backup..."
            ./scripts/restore_qdrant.sh
        else
            echo "Failed to download backup! Ensure QDRANT_BACKUP_URL is correct."
            exit 1
        fi
    else
        echo "No QDRANT_BACKUP_URL configured. Qdrant will start empty, and you must regenerate embeddings."
        docker compose up -d
    fi
fi
