#!/bin/bash
set -e

# Change to the root of the repository
cd "$(dirname "$0")/.."

echo "Stopping Qdrant container safely..."
docker stop crime_bot_qdrant || echo "Qdrant container is not running."

echo "Archiving Qdrant storage..."
tar -czvf qdrant_storage.tar.gz qdrant_storage/

echo "Starting Qdrant container again..."
docker start crime_bot_qdrant || echo "Could not start Qdrant. Maybe it wasn't running via 'docker start'."

echo "Backup complete! Archive saved to qdrant_storage.tar.gz"
