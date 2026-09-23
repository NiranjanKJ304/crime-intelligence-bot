# Karnataka Police Crime Intelligence Platform

> An end-to-end AI-powered crime investigation assistant built with FastAPI, Qdrant, Neo4j, Groq, and Streamlit — configured for native local execution with a hybrid retrieval architecture.

---

## 🏛️ What is this?

The **Crime Intelligence Copilot** is a full-stack **Hybrid AI Retrieval Platform** for the Karnataka Police that allows investigators to ask natural language questions against a corpus of crime records and receive grounded, citation-backed answers.

Unlike pure RAG systems, this platform uses a **deterministic intent detector** to route queries through the optimal execution path:
- **Factual queries** (e.g., "Who is the investigating officer for CaseNo 202300001?") → Parameterised PostgreSQL lookup with **zero LLM calls** (a few ms)
- **Reasoning queries** (e.g., "Summarize CaseNo 202300001") → Pre-fetched compact context + **single LLM call** (~2-5s)
- **Semantic queries** (e.g., "Robbery cases in Bangalore") → **Vector similarity search** via Qdrant

PostgreSQL is the source of truth for factual records and Neo4j for relationships; the LLM never generates SQL or Cypher and is only used for natural-language reasoning over data the planner already retrieved.

The platform covers the entire ML engineering pipeline — from raw PostgreSQL data through automated ETL, Neo4j knowledge graph construction, vector embedding generation, multi-path retrieval, LLM-based question answering, and a Streamlit UI that renders database results as structured cards and tables.

---

## 🗺️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER (Web Browser)                           │
│                 http://localhost:8501                           │
└───────────────────────┬─────────────────────────────────────────┘
                        │ REST / SSE
┌───────────────────────▼─────────────────────────────────────────┐
│              STREAMLIT FRONTEND (Port 8501)                     │
│   Chat (SSE streaming + citations)  │  Dashboard (Plotly)       │
│   About (Architecture)              │  Sidebar (Health)         │
│   ── api/client.py (httpx, no direct DB) ──                     │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTP
┌───────────────────────▼─────────────────────────────────────────┐
│               FASTAPI BACKEND (Port 8000)                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Query Router → Intent Detector → Query Planner            │  │
│  │       │                                                    │  │
│  │  ┌────┴────────────────┐    ┌──────────────────────────┐   │  │
│  │  │  Factual Path       │    │  Reasoning Path          │   │  │
│  │  │  (0 LLM calls)      │    │  (1 LLM call)            │   │  │
│  │  │  TemplateEngine +   │    │  Groq (MODEL_NAME)       │   │  │
│  │  │  structured payload │    │                          │   │  │
│  │  └─────────────────────┘    └──────────────────────────┘   │  │
│  │  ColumnMapper: logical table/column → physical schema      │  │
│  │  (clean.clean_<T> if ETL ran, else public.<T>)             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ ETL Pipeline  │  │ Doc Generator │  │ Retrieval Engine     │   │
│  │ (7-stage)     │  │ (6 builders)  │  │ (Query→Rank→Context) │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │              │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────────▼───────────┐   │
│  │ PostgreSQL   │  │ Neo4j 5      │  │ Qdrant (Embedded)    │   │
│  │ (5432)       │  │ (7687)       │  │ ./qdrant_storage     │   │
│  │ public+clean │  │ 11 labels    │  │ 384-dim vectors      │   │
│  │ schemas      │  │ 17 rel types │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                 │
│  External: Groq API (cloud LLM) │ HuggingFace (model download)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Tech Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| **API Framework** | FastAPI + Uvicorn | Async ASGI server |
| **LLM Provider** | Groq | Model set by `MODEL_NAME` (default `llama-3.3-70b-versatile`) |
| **Query Routing** | Deterministic Planner | Regex intent + tool orchestration; `ColumnMapper` resolves logical → physical schema |
| **Embedding Model** | `BAAI/bge-small-en-v1.5` | 384-dim, local CPU inference |
| **Vector Store** | Qdrant | Local embedded directory mode |
| **Graph Database** | Neo4j 5 | 11 node types, 17 relationships |
| **Relational DB** | PostgreSQL 16 | Dynamic schema mapper |
| **Frontend** | Streamlit | SSE streaming + Plotly charts |
| **Streaming** | SSE | `sse-starlette` for token streaming |
| **Configuration** | Pydantic Settings | `.env` file based |

---

## 🚀 Quick Start (Native Local Run)

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11 or 3.12 | Runtime |
| PostgreSQL | 16+ | Crime data storage |
| Neo4j | 5.x (Desktop or Community) | Knowledge graph |
| Groq API Key | Free tier | LLM inference |

> **Note:** Qdrant runs in embedded mode (no installation required).

---

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```env
# Required
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/crime_db
GROQ_API_KEY=gsk_your_groq_api_key_here

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Optional — enable auto database initialization
AUTO_INITIALIZE_DATABASE=true
```

---

### 2. Create PostgreSQL Database

```sql
-- Connect to PostgreSQL and create the database
CREATE DATABASE crime_db;

-- Connect to crime_db, then create the clean schema
\c crime_db
CREATE SCHEMA IF NOT EXISTS clean;
```

Load crime data from CSV files:
```bash
python load_datafiles_to_postgres.py
```

---

### 3. Set Up Neo4j

1. Install [Neo4j Desktop](https://neo4j.com/download/) or Neo4j Community Edition
2. Create a new database
3. Set the password to match `NEO4J_PASSWORD` in your `.env`
4. Ensure it's running on `bolt://localhost:7687`

---

### 4. Create Virtual Environment & Install Dependencies

```bash
python -m venv .venv

# Activate:
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows CMD:        .venv\Scripts\activate.bat
# Linux/macOS:        source .venv/bin/activate

pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

---

### 5. Start the Backend

#### Windows (PowerShell):
```powershell
.\run_backend.ps1
```

#### Windows (Command Prompt):
```cmd
run_backend.bat
```

#### Manual:
```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

On first startup with `AUTO_INITIALIZE_DATABASE=true`, the system will:
1. Check if PostgreSQL has data → populate from schema/CSV if empty
2. Check if Neo4j has nodes → build knowledge graph if empty
3. Check if Qdrant has vectors → restore from local storage if empty

Interactive Swagger documentation: **http://localhost:8000/docs**

---

### 6. Start the Frontend (new terminal)

#### Windows (PowerShell):
```powershell
.\run_frontend.ps1
```

#### Windows (Command Prompt):
```cmd
run_frontend.bat
```

#### Manual:
```bash
cd frontend
streamlit run app.py --server.port 8501
```

Open **http://localhost:8501** in your browser.

---

### 7. Build Data Pipelines (First Time Only)

The chat works as soon as `public` is loaded: factual lookups resolve to `public.<Table>` until the ETL has produced `clean.clean_<Table>`, after which the clean tables are preferred automatically (set `REQUIRE_CLEAN_SCHEMA=true` to insist on clean and fail fast instead).

To build the full knowledge layer, trigger the pipelines via the API once the backend is running:

```bash
# Step 1: Run ETL pipeline (public → clean schema; ~20s for the sample data)
curl -X POST http://localhost:8000/api/v1/etl/run

# Step 2: Generate AI documents (reads clean schema)
curl -X POST http://localhost:8000/api/v1/documents/build

# Step 3: Build Neo4j knowledge graph (reads clean if present, else public)
curl -X POST http://localhost:8000/api/v1/graph/build

# Step 4: Generate embeddings & load into Qdrant
curl -X POST http://localhost:8000/api/v1/embedding/build
```

Or use the Swagger UI at **http://localhost:8000/docs** to trigger these endpoints interactively.

Sample queries to try in the chat once data is loaded:

```
Find CaseNo 202300001
Find officer EmployeeID 5313
Who is the investigating officer for CaseNo 202300001?
Fiyaz Saran                      # returns every matching accused record — a name is not an identity
Summarize CaseNo 202300001       # reasoning path, 1 LLM call
```

---

## 📡 Backend API Reference

### Chat & Query

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat` | Synchronous chat — full JSON response |
| `POST` | `/api/v1/chat/stream` | Streaming SSE chat |

`ChatResponse` carries the answer twice: `answer` (Markdown, universal fallback) and `response_type` + `data` (structured, for rich clients):

| `response_type` | `data` |
|---|---|
| `answer` | `null` — plain / LLM text |
| `case_details` | `{"case": {...}, "chargesheet": {...} \| null}` |
| `officer_details` | `{"officer": {...}, "case": {...} \| null}` |
| `person_details` | `{"role": "victim" \| "accused", "persons": [...], "case": {...} \| null}` |
| `search_results` | `{"entity", "query", "total", "results": [...], "note"}` |
| `statistics` | `{"title", "metrics": {label: value}}` |

SSE protocol (one JSON object per `data:` line): `{"event":"token","data":"…"}` → `{"event":"complete","response_type","data","citations","sources","confidence","retrieval"}` → `[DONE]`. Any backend failure is emitted as `{"event":"error","data":"<user-safe message>"}` followed by `[DONE]` — the stream is never dropped and tracebacks are never exposed. The sync endpoint returns HTTP 500 with the same safe message.

### ETL Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/etl/run` | Run full ETL pipeline (discover → clean → load); refreshes the ColumnMapper afterwards |
| `GET` | `/api/v1/etl/status` | Last pipeline run status |
| `GET` | `/api/v1/etl/schema` | Discover database schema |
| `GET` | `/api/v1/etl/tables` | Discovered tables with row counts |
| `GET` | `/api/v1/etl/relationships` | Discovered FK relationship graph |
| `GET` | `/api/v1/etl/reports/profile/{table}` | Profiling report for a table |
| `GET` | `/api/v1/etl/reports/validation/{table}` | Validation report for a table |
| `GET` | `/api/v1/etl/reports/summary` | Last pipeline summary |

### Knowledge Graph

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/graph/build` | Build Neo4j graph; returns `status`, `tables_processed`, `nodes_created`, `relationships_created`, `source_tables`, `errors`. HTTP 500 if no source table could be resolved |
| `POST` | `/api/v1/graph/update` | Same as build (MERGE = idempotent upsert) |
| `GET` | `/api/v1/graph/statistics` | Live node counts per label and relationship counts per type |

### AI Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/documents/build` | Generate all AI documents (6 types, reads clean schema) |
| `POST` | `/api/v1/documents/update` | Regenerate (idempotent) |
| `DELETE` | `/api/v1/documents/rebuild` | Delete store and regenerate |
| `GET` | `/api/v1/documents/statistics` | Document store statistics |
| `GET` | `/api/v1/documents/{document_id}` | Single document |

### Embeddings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/embedding/build` | Full vector embedding build |
| `POST` | `/api/v1/embedding/update` | Incremental sync (new/modified/deleted only) |
| `DELETE` | `/api/v1/embedding/rebuild` | Drop collection and rebuild |
| `POST` | `/api/v1/embedding/search` | Semantic search over the collection |
| `GET` | `/api/v1/embedding/statistics` | Qdrant collection statistics |
| `GET` | `/api/v1/embedding/models` | Loaded embedding model info |
| `GET` | `/api/v1/embedding/health` | Embedding subsystem health |

### Retrieval

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/retrieval/statistics` | Retrieval analytics + cache stats |
| `GET` | `/api/v1/retrieval/health` | Qdrant / Neo4j / cache health |
| `GET` | `/api/v1/retrieval/config` | Current retrieval configuration |

The `RetrievalEngine.search()/hybrid()` pipeline is used internally by the chat planner (`search_similar_cases`); it is not exposed as its own HTTP endpoint.

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Overall system health check |

Full interactive docs: **http://localhost:8000/docs** (Swagger UI)

---

## 🔄 Processing Flows

### Chat Query Flow

```
User Question → IntentDetector (regex) → QueryPlanner (deterministic tools)
     │                                        │
     │                    ColumnMapper: CaseMaster.case_number → "clean"."clean_CaseMaster"."CaseNo"
     │                                        │  (or "public"."CaseMaster" before the ETL has run)
     ├── Factual → PostgreSQL lookup → TemplateEngine → Response (0 LLM calls)
     ├── Reasoning → Pre-fetched context → Groq LLM → Response (1 LLM call)
     └── Semantic → Qdrant ANN search → Groq LLM → Response (1 LLM call)
```

Identifiers are kept distinct end to end: `CaseNo`, `CrimeNo` (FIR) and `CaseMasterID` are different columns; `EmployeeID`/`PolicePersonID` identify officers; accused are identified by `AccusedMasterID`/`PersonID` — a name such as "Fiyaz Saran" appears on many records and is never treated as unique. Values are validated against the physical column type before any SQL runs.

Example — *"Who is the investigating officer for CaseNo 202300001?"*:

```
CaseNo 202300001 → CaseMaster (CaseMasterID=1, PolicePersonID=5313) → Employee 5313 → "Oliver (KG10313)"
```

Set `DEBUG=true` to get `[TRACE]` log records for every stage (query, intent, identifier type, logical/physical table & column, SQL, parameters, row count, `GROQ CALLED: YES/NO`).

### ETL Pipeline Flow

```
PostgreSQL (public) → Discovery → Extract → Profile → Clean → Transform → Validate → Load → PostgreSQL (clean)
```

### Knowledge Build Flow

```
PostgreSQL (clean) → AI Document Generation → Qdrant (vectors)
PostgreSQL (clean, or public if the ETL has not run) → Neo4j Graph Builder → Neo4j (11 labels, 17 relationship types)
```

---

## 📁 Project Structure

```
crime-intelligence-bot/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory + lifespan
│   │   ├── api/v1/                    # REST API routes (6 route files)
│   │   ├── core/                      # Config, DB connections, logging
│   │   ├── database_initializer/      # Auto DB bootstrapping (PG, Neo4j, Qdrant)
│   │   ├── etl/                       # 7-stage ETL pipeline (13 modules)
│   │   ├── document_generation/       # 6 AI document builders
│   │   ├── graph/                     # Neo4j graph builder (11 nodes, 17 rels)
│   │   ├── embeddings/                # Vector embedding platform (10 modules)
│   │   ├── retrieval/                 # Enterprise retrieval engine (11 modules)
│   │   ├── services/tools/            # Deterministic tool system
│   │   │   ├── mapper.py              #   ColumnMapper: logical → physical schema/table/column
│   │   │   ├── intent_detector.py     #   Regex intent + identifier-kind extraction
│   │   │   ├── planner.py             #   Deterministic tool execution
│   │   │   ├── router.py              #   Factual vs reasoning routing, trace logging
│   │   │   ├── postgres_tools.py      #   Parameterised SQL tools (no SELECT *)
│   │   │   ├── neo4j_tools.py / qdrant_tools.py
│   │   │   ├── template_engine.py     #   Zero-LLM Markdown answers
│   │   │   ├── exceptions.py          #   MappingError, DatabaseQueryError, IdentifierValidationError
│   │   │   └── tracing.py             #   [TRACE] structured debug logging
│   │   ├── llm/                       # LLM client + Groq provider
│   │   ├── rag/                       # Response builder
│   │   └── models/                    # (placeholder)
│   ├── tests/                         # Unit tests (no DB needed) + tests/integration (live DB)
│   └── requirements.txt
├── frontend/
│   ├── app.py                         # Streamlit entry point + global CSS
│   ├── api/client.py                  # httpx REST client
│   ├── api/schemas.py                 # Typed schemas for response_type/data payloads
│   ├── pages/                         # Chat, Dashboard, About
│   ├── components/
│   │   ├── response_renderer.py       #   Cards/tables per response_type, Markdown fallback
│   │   ├── chat_message.py            #   Native chat containers
│   │   └── sidebar.py, citation_card.py, metrics.py
│   ├── utils/                         # Helpers, constants
│   └── requirements.txt
├── datafiles/                         # Raw CSV crime data
├── qdrant_storage/                    # Persistent vector storage
├── load_datafiles_to_postgres.py      # Standalone data loader
├── run_backend.ps1 / .bat             # Backend launchers
├── run_frontend.ps1 / .bat            # Frontend launchers
├── test_api.py                        # API test script
├── .env.example                       # Configuration template
├── .env                               # Active config (gitignored)
└── PROJECT_STATUS.md                  # Detailed architecture & phase docs
```

---

## 🔒 Security Notes

- **Never commit `.env`** — it is listed in `.gitignore`
- Use `.env.example` as a template; fill in real values locally
- Change all default passwords before any production deployment
- CORS is configured as `allow_origins=["*"]` — restrict in production

---

## 🔑 Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:password@localhost:5432/crime_db` | PostgreSQL connection string |
| `SOURCE_SCHEMA` | `public` | Schema holding the raw imported tables |
| `CLEAN_SCHEMA` | `clean` | Schema the ETL writes `clean_<Table>` tables into |
| `REQUIRE_CLEAN_SCHEMA` | `false` | `false`: prefer clean tables, fall back to source tables. `true`: fail startup / graph build with an ETL error when clean tables are missing |
| `DEBUG` | `false` | Enables `[TRACE]` stage logging for chat queries |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt connection |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `password` | Neo4j password |
| `GROQ_API_KEY` | *(required)* | Groq API key for LLM |
| `MODEL_NAME` | `llama-3.3-70b-versatile` | LLM model name |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model (384-dim) |
| `QDRANT_PATH` | `./qdrant_storage` | Local Qdrant storage path |
| `AUTO_INITIALIZE_DATABASE` | `false` | Auto-bootstrap DBs on startup |
| `TOP_K` | `10` | Default retrieval results count |
| `DEFAULT_SCORE_THRESHOLD` | `0.5` | Minimum similarity score |
| `TEMPERATURE` | `0.2` | LLM temperature |
| `MAX_TOKENS` | `4096` | Max LLM response tokens |

See [`.env.example`](.env.example) for the complete list.

---

## 🧪 Testing

```bash
cd backend
..\.venv\Scripts\python -m pytest tests -q                 # unit tests, no services required
..\.venv\Scripts\python -m pytest tests/integration -q     # needs live PostgreSQL (skips otherwise)
```

The tools layer is tested against an in-memory replica of the real `public` schema (`tests/test_services/conftest.py`), so mapper resolution, typed SQL parameters, the CaseNo → officer chain, not-found handling, the multi-record name search and the SSE error protocol are all covered without a database.

---

## ⚠️ Known Issues

- `backend/app/services/tools/neo4j_tools.py` and `retrieval/graph_search.py` query graph properties named `CrimeNumber`, `Age`, `Sex`, `EmployeeName`, `FIRNo`, but nodes carry the physical column names (`CrimeNo`, `AgeYear`, `GenderID`, `FirstName`). Network / co-accused / timeline answers therefore return nulls for those fields until the property names are aligned.
- `ActSectionAssociation` in the sample data contains a single distinct `(ActID, SectionID)`, so the graph has one `ActSection` node.

---

## 📄 License

Internal project — Karnataka Police Crime Intelligence Platform.
