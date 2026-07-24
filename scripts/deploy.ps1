$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$RepoRoot\.."

# Load environment variables
if (Test-Path ".env") {
    foreach ($line in Get-Content ".env") {
        if ($line -match '^(?!#)(.+?)=(.*)$') {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
        }
    }
}

Write-Host "Starting Deployment Process..."

if ((Test-Path "qdrant_storage") -and ((Get-ChildItem "qdrant_storage" | Measure-Object).Count -gt 0)) {
    Write-Host "Qdrant storage exists locally. Starting normally..."
    docker compose up -d
} else {
    Write-Host "Qdrant storage not found locally."
    
    $BackupUrl = $env:QDRANT_BACKUP_URL
    if ([string]::IsNullOrWhiteSpace($BackupUrl) -eq $false) {
        Write-Host "Downloading backup from $BackupUrl..."
        Invoke-WebRequest -Uri $BackupUrl -OutFile "qdrant_storage.zip"
        
        if (Test-Path "qdrant_storage.zip") {
            Write-Host "Extracting backup..."
            & .\scripts\restore_qdrant.ps1
        } else {
            Write-Host "Failed to download backup! Ensure QDRANT_BACKUP_URL is correct." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "No QDRANT_BACKUP_URL configured. Qdrant will start empty, and you must regenerate embeddings." -ForegroundColor Yellow
        docker compose up -d
    }
}
