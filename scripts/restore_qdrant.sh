#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "Stopping docker containers before restore..."
docker compose stop qdrant || true

if [ -f "qdrant_storage.tar.gz" ]; then
    echo "Found qdrant_storage.tar.gz! Extracting..."
    rm -rf qdrant_storage/
    tar -xzvf qdrant_storage.tar.gz
    echo "Restore completed."
else
    echo "Error: qdrant_storage.tar.gz not found in the root directory!"
    exit 1
fi

echo "Starting Docker containers..."
docker compose up -d
