# Crime Intelligence Copilot - Docker Deployment

This repository contains the complete, production-ready Docker infrastructure for the Karnataka Police Crime Intelligence Copilot.

With a single command, you can spin up the entire backend ecosystem, including:
- **FastAPI Backend** (ETL, Document Generation, Semantic Search)
- **PostgreSQL** (Raw & Clean Relational Data)
- **Neo4j** (Knowledge Graph)
- **Qdrant** (Vector Database)

## Prerequisites

- [Docker Engine](https://docs.docker.com/engine/install/) (v24.0+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.20+)

## First Startup

1. **Configure the Environment**
   Copy the example environment file to `.env`:
   ```bash
   cp .env.docker.example .env
   ```
   *(Optional)* Edit `.env` to change default passwords or model parameters.

2. **Start the Cluster**
   Run the following command from the root of the repository:
   ```bash
   docker compose up -d
   ```

   **Note on Startup Sequence**: 
   The `backend` container will remain in a `Wait` state until PostgreSQL, Neo4j, and Qdrant have fully initialized and reported as `healthy`. This may take 10-30 seconds on the first boot.

## Accessing the Services

Once all containers are running, you can access the services at the following URLs:

| Service | URL | Description |
|---------|-----|-------------|
| **Backend API** | [http://localhost:8000](http://localhost:8000) | Root API endpoint |
| **Swagger UI** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API documentation |
| **Neo4j Browser** | [http://localhost:7474](http://localhost:7474) | Graph visualization UI |
| **Qdrant Dashboard** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Vector DB UI |

## Development Workflow

This setup includes a `docker-compose.override.yml` file tailored for local development:
- The `./backend/app` directory is bind-mounted directly into the container.
- The FastAPI server runs with `uvicorn --reload`.
- Any changes you make to the Python code on your local machine will automatically restart the server inside the container.

## Managing the Cluster

**View Logs (All Services)**
```bash
docker compose logs -f
```

**View Logs (Backend Only)**
```bash
docker compose logs -f backend
```

**Stop the Cluster**
```bash
docker compose stop
```

**Tear Down the Cluster** (Leaves persistent volumes intact)
```bash
docker compose down
```

**Tear Down the Cluster AND Delete Data** (Destroys all databases!)
```bash
docker compose down -v
```

## Database Persistence

All data is stored in Docker Named Volumes, meaning your data survives container restarts and teardowns (unless you use the `-v` flag).

- `postgres_data`: Relational data
- `neo4j_data`: Graph data
- `qdrant_storage`: Vector embeddings

## Troubleshooting

**Q: The backend container keeps crashing or restarting.**
A: Check the logs: `docker compose logs backend`. Ensure your `.env` file exists and the database URLs point to the service names (`postgres`, `neo4j`, `qdrant`), not `localhost`.

**Q: Neo4j APOC plugins aren't loading.**
A: The `docker-compose.yml` handles this automatically via the `NEO4J_PLUGINS='["apoc"]'` environment variable. Give the container a moment to download the plugin on the very first boot.

**Q: How do I rebuild the backend image after adding a new pip package?**
A: Run: `docker compose up -d --build backend`

## Production Deployment

When deploying to a remote production server:
1. Delete or rename `docker-compose.override.yml` so it isn't applied.
2. Change the default passwords in your `.env` file.
3. Place a reverse proxy (like NGINX or Traefik) in front of port 8000 to handle SSL/TLS termination.
