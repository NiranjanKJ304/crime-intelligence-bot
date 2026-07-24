# Crime Intelligence Copilot — Project Status

This document tracks the high-level progress of the Karnataka Police Crime Intelligence Platform.

Last updated: **2026-07-23**

---

## ✅ Phase 1 — Automated ETL Pipeline
**Status: COMPLETE**

- Auto-discovers PostgreSQL schema metadata (zero hardcoded table/column names)
- Maps all relationships dynamically via SQLAlchemy Inspector
- Extracts all data via chunked processing into Pandas DataFrames
- Profiles data quality (nulls, duplicates, outliers, type mismatches)
- Applies 11 composable cleaners (NullNormalizer, DateNormalizer, GenderNormalizer, etc.)
- Generates 10 derived analytical columns (CrimeYear, IsNightCrime, SearchText, etc.)
- Performs PK/FK integrity and range validation
- Loads securely using transactional TRUNCATE+INSERT into the `clean` schema
- Exposes pipeline via `/api/v1/etl/*` FastAPI routes

---

## ✅ Phase 2 — Knowledge Layer
**Status: COMPLETE**

### 2a — AI Document Generation
- Generates rich natural-language summaries for each entity (cases, accused, victims, officers)
- Documents stored as structured JSON in the document store
- Exposed via `/api/v1/documents/*` endpoints

### 2b — Neo4j Knowledge Graph
- Extracts data from `clean` schema via server-side cursors
- Creates 11 unique node types: Case, Accused, Employee, Court, Victim, Offence, District, PoliceStation, Vehicle, MobileNumber, BankAccount
- Builds 17 highly specific relationship types mapping real-world investigative linkages
- Idempotent `MERGE` loader ensures full restart-ability
- Unique Constraints and Property Indexes managed automatically
- Exposed via `/api/v1/graph/*` endpoints

### 2c — Embedding Generation & Qdrant Vector Store
- Generates dense vector embeddings using `BAAI/bge-small-en-v1.5` (384-dim)
- Stores and indexes all document vectors in Qdrant for sub-second semantic search
- Collection: `crime_intelligence`

---

## ✅ Phase 3 — Enterprise Retrieval Engine
**Status: COMPLETE**

- **Query Processor** — Cleans and normalises incoming natural language queries
- **Entity Extractor** — Extracts named entities (persons, locations, dates) from queries
- **Semantic Search** — Qdrant ANN search with configurable `top_k` and score threshold
- **Graph Search** — Optional Neo4j traversal enrichment (decoupled from runtime)
- **Hybrid Engine** — Merges semantic + graph hits with deduplication
- **Ranking Engine** — Multi-factor scoring: semantic similarity + freshness + type priority + metadata richness
- **Explainability Builder** — Per-result score breakdown with human-readable ranking reasons
- **Context Builder** — Assembles ranked documents into an LLM-ready context window
- **Retrieval API** — Full REST API (`/api/v1/retrieval/*`): search, statistics, health, config
- **Query Result Cache** — LRU cache (configurable TTL) for repeated queries
- **Analytics** — Top documents, score distributions, type breakdowns

---

## ✅ Phase 4 — GraphRAG + LLM Integration
**Status: COMPLETE**

- **LLM Client** — Groq provider (`llama-3.3-70b-versatile`) with streaming support
- **Prompt Builder** — Structured system + user prompts with injected retrieval context
- **RAG Orchestrator** — End-to-end pipeline: query → retrieval → prompt → LLM → citations
- **Citation Builder** — Extracts document references from answers, scores, and formats them
- **Response Builder & Validator** — Validates LLM responses for quality and completeness
- **Chat API (Sync)** — `POST /api/v1/chat` — full JSON response with citations
- **Chat API (Streaming)** — `POST /api/v1/chat/stream` — Server-Sent Events (SSE) token streaming
- **Neo4j Decoupled** — Graph code retained but runtime query flow uses semantic search only; Chat API remains functional even if Neo4j is offline

---

## ✅ Phase 6 — Hybrid Architecture & Reliability
**Status: COMPLETE**

- **Tool Calling (SQL Router)** — Upgraded from pure Semantic RAG to Hybrid AI Retrieval Platform
- **Dynamic Postgres Schema Mapping** — Added a dynamic mapper to resolve logical identifiers (e.g. `CrimeNumber`) to physical schema columns (e.g. `CrimeNo`), adapting to ETL schema changes automatically
- **Database Initializer** — Implemented an automatic database initialization system that runs during backend startup if the PostgreSQL/Neo4j databases are empty (executes `schema.sql` securely)
- **Qdrant Persistence** — Permanently stores vectors outside the Docker container with automatic restore during deployment via volume mapping (`./qdrant_storage:/qdrant/storage`)
- **Resilient Startup Validation** — Validates dynamic column bindings at startup to ensure API integrity

---

## ✅ Phase 5 — Streamlit Frontend (AI Copilot UI)
**Status: COMPLETE**

- **Chat Page** — Real-time SSE streaming chat interface with citation cards and retrieval metrics
- **Dashboard Page** — System health monitoring, score distributions, and analytics charts (Plotly)
- **About Page** — Architecture overview and technology stack documentation
- **Sidebar** — Live backend health status indicator, model info, query settings
- **REST-only** — Frontend communicates exclusively via backend REST APIs (no direct DB access)

---

## 🏗️ Infrastructure
**Status: COMPLETE**

| Service | Image | Port |
|---------|-------|------|
| FastAPI Backend | Custom (`crime-bot-backend`) | 8000 |
| PostgreSQL | `postgres:16-alpine` | 5433 (host) |
| Neo4j | `neo4j:5-community` | 7475/7688 (host) |
| Qdrant | `qdrant/qdrant:latest` | 6333–6334 |
| Streamlit Frontend | Custom (`crime-bot-streamlit`) | 8501 |

---

## 📊 System Architecture

```
User (Browser)
    │
    ▼
Streamlit Frontend (Port 8501)
    │  REST / SSE
    ▼
FastAPI Backend (Port 8000)
    ├── ETL Pipeline ──────────────────► PostgreSQL (5433)
    ├── Document Generation
    ├── Graph Builder ─────────────────► Neo4j (7688)
    ├── Embedding Engine ───────────────► Qdrant (6333)
    ├── Retrieval Engine (Semantic Search)
    └── RAG Orchestrator ──────────────► Groq LLM (llama-3.3-70b)
```
