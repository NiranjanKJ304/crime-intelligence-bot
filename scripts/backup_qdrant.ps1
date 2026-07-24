# Change to the root of the repository
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$RepoRoot\.."

Write-Host "Stopping Qdrant container safely..."
$qdrantRunning = (docker ps -q -f name=crime_bot_qdrant)
if ($qdrantRunning) {
    docker stop crime_bot_qdrant
} else {
    Write-Host "Qdrant container is not currently running."
}

Write-Host "Archiving Qdrant storage to qdrant_storage.zip..."
if (Test-Path "qdrant_storage.zip") {
    Remove-Item "qdrant_storage.zip" -Force
}
Compress-Archive -Path "qdrant_storage" -DestinationPath "qdrant_storage.zip"

Write-Host "Starting Qdrant container again..."
if ($qdrantRunning) {
    docker start crime_bot_qdrant
}

Write-Host "Backup complete! Archive saved to qdrant_storage.zip"
