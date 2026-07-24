$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$RepoRoot\.."

Write-Host "Stopping docker containers before restore..."
docker compose stop qdrant

if (Test-Path "qdrant_storage.zip") {
    Write-Host "Found qdrant_storage.zip! Extracting..."
    if (Test-Path "qdrant_storage") {
        Remove-Item "qdrant_storage" -Recurse -Force
    }
    Expand-Archive -Path "qdrant_storage.zip" -DestinationPath "." -Force
    Write-Host "Restore completed."
} else {
    Write-Host "Error: qdrant_storage.zip not found in the root directory!" -ForegroundColor Red
    exit 1
}

Write-Host "Starting Docker containers..."
docker compose up -d
