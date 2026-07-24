# Crime Intelligence Copilot — Docker Deployment Guide

This guide covers running the complete **Karnataka Police Crime Intelligence Platform** using Docker Compose.

The stack includes:

| Container | Image | Host Port | Purpose |
|-----------|-------|-----------|---------|
| `crime_bot_backend` | Custom FastAPI image | `8000` | API, ETL, RAG, LLM |
| `crime_bot_postgres` | `postgres:16-alpine` | `5433` | Relational data (raw + clean) |
| `crime_bot_neo4j` | `neo4j:5-community` | `7475` (HTTP) / `7688` (Bolt) | Knowledge graph |
| `crime_bot_qdrant` | `qdrant/qdrant:latest` | `6333–6334` | Vector database |

> **Note:** Host ports are offset from defaults (5433 instead of 5432, 7475/7688 instead of 7474/7687) to avoid conflicts with local database installations.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) v24.0+ (Windows / macOS) or Docker Engine v24+ (Linux)
- [Docker Compose](https://docs.docker.com/compose/install/) v2.20+
- A [Groq API key](https://console.groq.com/) for the LLM layer

---

## First-Time Setup

### 1. Configure Environment

Copy the example env file to `.env`:

```bash
cp .env.example .env
```

Then open `.env` and set your `GROQ_API_KEY`:

```env
GROQ_API_KEY=your_groq_api_key_here
```

> All other defaults (DB passwords, model names, etc.) are pre-configured and work out of the box for local development.

### 2. Build & Start the Cluster

From the repository root:

```bash
docker compose up -d
```

On the **first boot**, Docker will:
1. Pull all base images (~1–2 GB total)
2. Build the FastAPI backend image
3. Download the embedding model (`BAAI/bge-small-en-v1.5`) into the container cache

This can take **2–5 minutes** on first run. Subsequent starts take ~15–30 seconds.

### 3. Verify All Services Are Healthy

```bash
docker compose ps
```

All containers should show `healthy` or `running`. Then verify the backend:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok", "version": "0.1.0"}
```

---

## Accessing the Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Backend API** | http://localhost:8000 | — |
| **Swagger UI** | http://localhost:8000/docs | — |
| **Neo4j Browser** | http://localhost:7475 | `neo4j` / `supersecret_neo4j_password` |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | — |
| **Streamlit UI** | http://localhost:8501 | *(run separately — see below)* |

---

## Running the Streamlit Frontend

The frontend is a separate Streamlit app and is **not** part of the Docker Compose stack. Run it locally:

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

The sidebar will show **"Backend: Online"** once the Docker containers are healthy.

---

## Development Workflow

The `docker-compose.override.yml` file is automatically applied in development:

- `./backend/app` is **bind-mounted** into the container — code changes are reflected immediately
- Uvicorn runs with `--reload` — the server restarts on any Python file change
- The `./backend` directory is excluded from the file watcher to avoid reloading on generated JSON files

To rebuild after adding a new Python dependency:

```bash
docker compose up -d --build backend
```

---

## Common Commands

| Action | Command |
|--------|---------|
| Start all services | `docker compose up -d` |
| Stop all services | `docker compose stop` |
| View all logs | `docker compose logs -f` |
| View backend logs | `docker compose logs -f backend` |
| Restart backend | `docker compose restart backend` |
| Rebuild backend image | `docker compose up -d --build backend` |
| Destroy containers (keep data) | `docker compose down` |
| Destroy containers + data | `docker compose down -v` |

---

## Data Persistence

All data is stored in Docker **named volumes**, surviving container restarts and `docker compose down`:

| Volume | Contains |
|--------|----------|
| `postgres_data` | Raw + clean relational crime data |
| `neo4j_data` | Knowledge graph nodes and relationships |
| `qdrant_storage` | Vector embeddings |
| `backend_hf_cache` | Downloaded HuggingFace model weights |

> ⚠️ **Only `docker compose down -v` will delete this data.** Normal restarts preserve everything.

---

## Troubleshooting

**Backend crashes on startup with `Neo4j connection refused`**

This is expected if Neo4j is still initializing. The backend logs the error but continues running. The Chat API does not require Neo4j — semantic search via Qdrant will work immediately.

**Backend crashes with `WatchfilesRustInternalError`**

This occurs when `uvicorn --reload` tries to watch the large document generation store. It is handled by excluding the `document_generation/store` directory from the watcher in the override file. If it recurs, restart the backend:

```bash
docker compose restart backend
```

**`GROQ_API_KEY` is missing or invalid**

Check your `.env` file exists in the repo root and contains a valid key. Then restart the backend:

```bash
docker compose restart backend
```

**Port conflict (e.g., `5433 already in use`)**

A local PostgreSQL instance may be using the same port. Edit `docker-compose.override.yml` to change the host port mapping, e.g., `"5434:5432"`.

**How do I rebuild after adding a pip package?**

Add the package to `backend/requirements.txt`, then:

```bash
docker compose up -d --build backend
```

---

## Production Deployment

1. **Remove the override file** — rename or delete `docker-compose.override.yml` so bind-mounts and `--reload` are not applied
2. **Harden secrets** — change all default passwords in `.env` and use Docker secrets or a secrets manager
3. **Add a reverse proxy** — place NGINX or Traefik in front of port 8000 to handle SSL/TLS termination
4. **Restrict ports** — expose only ports 80/443 externally; keep 5433, 7475, 7688, and 6333 internal-only
5. **Set `DEBUG=False`** in `.env` (already the default)

---

## Qdrant Storage & Automated Backups

Vector embeddings can be expensive to generate. To prevent data loss, Qdrant storage is configured as a **local bind mount** (`./qdrant_storage`) rather than a Docker volume.

### How Storage Works
- The `qdrant` container maps its internal `/qdrant/storage` to the `./qdrant_storage` directory in the repository root.
- All collections and embeddings are saved directly to your host disk.
- **Vectors survive `docker compose down -v`**, as well as container deletion and recreation.

### How to Create a New Snapshot (Backup)
Use the provided backup scripts to compress the storage directory safely.
- **Linux/macOS:** `./scripts/backup_qdrant.sh`
- **Windows:** `.\scripts\backup_qdrant.ps1`

This will output an archive (`qdrant_storage.tar.gz` or `qdrant_storage.zip`) containing all vector data.

### How Restore Works
If you have a backup archive in the root directory, the restore script will replace the current local storage with the backup.
- **Linux/macOS:** `./scripts/restore_qdrant.sh`
- **Windows:** `.\scripts\restore_qdrant.ps1`

### How to Migrate to Another Server
1. Generate vectors and create a backup archive on Server A.
2. Upload the archive to cloud storage (e.g., S3, Google Drive, Azure Blob).
3. Clone this repository on Server B.
4. Set `QDRANT_BACKUP_URL=https://your-cloud-storage/qdrant_storage.zip` in your `.env` file.
5. Run the deployment script (`./scripts/deploy.sh` or `.\scripts\deploy.ps1`).

The deployment script will automatically download the backup, extract it, and start the Docker containers. Qdrant will immediately contain all vectors without needing to regenerate them.

### How to Update Vectors
If you need to re-embed data or update vectors, you must clear the Qdrant storage before running the ingestion pipeline:
1. Stop the cluster: `docker compose stop`
2. Delete the storage directory: `rm -rf qdrant_storage` (Linux) or `Remove-Item qdrant_storage -Recurse -Force` (Windows).
3. Start the cluster: `docker compose up -d`
4. Run the ETL and Graph generation pipelines to re-ingest all vectors.
