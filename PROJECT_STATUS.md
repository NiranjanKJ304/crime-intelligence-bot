# Crime Intelligence Copilot — Project Status & Architecture

This document provides a complete technical reference for the Karnataka Police Crime Intelligence Platform, covering all phases, architecture, processing flows, and module details.

Last updated: **2026-09-22**

## 📝 Recent Changes (2026-09-22)

| Area | Change |
|------|--------|
| Schema mapping | `ColumnMapper` rewritten: logical tables/columns (`CaseMaster.case_number`) resolve at startup from `information_schema` to `clean.clean_<T>` when the ETL produced it, else `<SOURCE_SCHEMA>.<T>`. New `REQUIRE_CLEAN_SCHEMA` flag. Column types are recorded and identifiers are validated/coerced before SQL. Missing mappings raise `MappingError` with full diagnostics (configured schemas, expected vs available tables/columns) instead of a bare `ValueError`. |
| PostgreSQL tools | Rewritten on logical names; explicit column lists (no `SELECT *` on the chat path); `CaseNo`, `CrimeNo`, `CaseMasterID`, `EmployeeID` kept distinct; `find_accused_by_name` returns every matching record. Fixed `get_case_lookup()` referencing `rows` before assignment. |
| Intent detection | Handles `CaseNo 202300001`, `EmployeeID 5313`, `case id` (= CaseMasterID) vs `case number`, `crime no` (= CrimeNo), officer-for-case chains, accused lookup by name. |
| Error handling | Tool/DB failures surface as `ToolError` → HTTP 500 with a user-safe message (sync) or an SSE `{"event":"error"}` + `[DONE]` (stream). No tracebacks, no dropped connections. |
| Structured responses | `ChatResponse.response_type` + `data` (case_details, officer_details, person_details, search_results, statistics, answer) alongside the Markdown `answer`; SSE `complete` event carries the same. |
| Frontend | `components/response_renderer.py` renders cards/tables per `response_type`; native chat containers so Markdown renders; typed payload schemas in `api/schemas.py`. |
| Graph build | `GraphBuilder` resolves logical source tables through `ColumnMapper`; returns `status`/`source_tables`/`tables_failed`; HTTP 500 with exact schema.table errors when nothing can be loaded. Query dicts keyed by logical table names. |
| ETL | `POST /etl/run` refreshes the `ColumnMapper` afterwards. Fixed indentation bug in `PostgresInitializer` that ran the ETL unconditionally. |
| Logging | `app.*` module loggers now attached to the JSON handlers (they were silently dropped). `DEBUG=true` emits `[TRACE]` records per pipeline stage. Fixed a double Groq call per reasoning query. |
| Data state (local) | `public` (11 raw tables) **and** `clean` (ETL run 2026-09-22, 45,100 rows). Neo4j built from clean: 40,101 nodes / 86,160 relationships. |

---

## 📊 System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         USER (Web Browser)                                   │
│                    http://localhost:8501                                      │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                    REST API / SSE Streaming
                               │
┌──────────────────────────────▼───────────────────────────────────────────────┐
│                  STREAMLIT FRONTEND (Port 8501)                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Chat Page   │  │  Dashboard   │  │  About Page  │  │   Sidebar   │       │
│  │ (SSE Stream) │  │  (Plotly)    │  │ (Architecture│  │ (Health +   │       │
│  │ + Citations  │  │  + Metrics   │  │  + Tech)     │  │  Settings)  │       │
│  └─────────────┘  └──────────────┘  └─────────────┘  └─────────────┘       │
│                                                                              │
│  api/client.py (httpx REST Client — no direct DB access)                    │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
                    REST / SSE via HTTP
                               │
┌──────────────────────────────▼───────────────────────────────────────────────┐
│                   FASTAPI BACKEND (Port 8000)                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        API Layer (app/api/v1/)                          │ │
│  │  /chat  /chat/stream  /etl/*  /graph/*  /documents/*  /retrieval/*     │ │
│  │  /embedding/*  /health                                                 │ │
│  └────────────────────────────────┬────────────────────────────────────────┘ │
│                                   │                                          │
│  ┌────────────────────────────────▼────────────────────────────────────────┐ │
│  │                    Query Processing Layer                               │ │
│  │                                                                         │ │
│  │  QueryRouter → IntentDetector → QueryPlanner → ContextBuilder          │ │
│  │       │              │               │               │                  │ │
│  │       │         Regex+Keyword    Deterministic    Tool Aggregation      │ │
│  │       │         Classification   Tool Execution                         │ │
│  │       │                              │                                  │ │
│  │       │                        ColumnMapper (logical → physical)        │ │
│  │       │                                                                 │ │
│  │       ├── Factual Path (0 LLM calls) → TemplateEngine + data → Response │ │
│  │       └── Reasoning Path (1 LLM call) → Groq LLM → Response           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     Data Processing Layer                               │ │
│  │                                                                         │ │
│  │  ETL Pipeline         Document Generation      Knowledge Graph          │ │
│  │  (10 cleaners,        (6 builders: Case,       (11 node labels,         │ │
│  │   7 transformers)      Accused, Victim,         17 relationship types)  │ │
│  │                        Officer, District,                                │ │
│  │  Embedding Pipeline    Court)                   Graph Builder            │ │
│  │  (BAAI/bge-small)                              (2-pass MERGE loader)    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     Storage Layer                                       │ │
│  │                                                                         │ │
│  │  PostgreSQL 16         Neo4j 5                Qdrant (Local Embedded)   │ │
│  │  localhost:5432        bolt://localhost:7687   ./qdrant_storage          │ │
│  │  (public + clean       (Knowledge Graph)      (384-dim vectors)         │ │
│  │   schemas)                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     External Services                                   │ │
│  │  Groq API (model = MODEL_NAME) — cloud LLM inference, reasoning only   │ │
│  │  HuggingFace Hub — embedding model download (BAAI/bge-small-en-v1.5)  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 End-to-End Processing Flows

### Flow 1: Chat Query Processing (User → Answer)

```
User types question in Streamlit Chat
     │
     ▼
POST /api/v1/chat or /api/v1/chat/stream
     │
     ▼
QueryRouter.route(request)
     │
     ├─► IntentDetector.detect(query)
     │   Uses regex + keyword patterns to classify into:
     │   • identifier_lookup (e.g., "Find CaseNo 202300001", "officer EmployeeID 5313",
     │                       "accused Fiyaz Saran")
     │   • factual_query (e.g., "who is the investigating officer for CaseNo 202300001?")
     │   • semantic_search (e.g., "robbery cases in Bangalore")
     │   • graph_query (e.g., "who is related to accused X?")
     │   • reasoning (e.g., "summarize CaseNo 202300001")
     │   Identifier kinds are typed and kept distinct:
     │     case_number (CaseNo) ≠ crime_number (CrimeNo/FIR) ≠ case_id (CaseMasterID)
     │     officer_id (EmployeeID) · victim_id · accused_id · accused_name (never unique)
     │
     ├─► Resolve history identifiers (if "that case" referenced)
     │
     ├─► QueryPlanner.execute(intent)
     │   Deterministic tool execution (no LLM decision-making):
     │   • postgres_tools: get_case_lookup, get_officer_compact,
     │     get_case_victims_list, get_case_accused_list, get_chargesheet_status,
     │     find_accused_by_name
     │   • neo4j_tools: find_case_network, find_co_accused, get_case_timeline
     │   • qdrant_tools: search_similar_cases
     │   Every PostgreSQL tool goes through ColumnMapper:
     │     logical table  "CaseMaster"  → "clean"."clean_CaseMaster" | "public"."CaseMaster"
     │     logical column "case_number" → "CaseNo"  (value coerced to the column's bigint type)
     │   Invalid identifiers → IdentifierValidationError → clean message, no SQL executed
     │   Missing rows → ctx.errors ("No case was found for CaseNo 999999999.")
     │   Returns → PlannerContext with all fetched DTOs
     │
     ├─► Decision Engine:
     │   ├── Factual/Identifier → TemplateEngine (0 LLM calls) + structured payload
     │   └── Reasoning/Graph   → Groq LLM (1 LLM call with pre-fetched compact context)
     │
     └─► ResponseBuilder.build(query, answer, citations, sources, metrics, response_type, data)
              │
              ▼
         ChatResponse { answer (Markdown), response_type, data, citations, sources, retrieval }
              │
              ▼
         Returned as JSON, or streamed via SSE:
           {"event":"token"} → {"event":"complete", response_type, data, citations, ...} → [DONE]
           on failure: {"event":"error","data":"Database query failed."} → [DONE]
```

Example chain for *"Who is the investigating officer for CaseNo 202300001?"*:

```
SELECT "CaseMasterID","CaseNo","CrimeNo","PolicePersonID","PoliceStationID","CaseStatusID"
  FROM "clean"."clean_CaseMaster" WHERE "CaseNo" = :val LIMIT 1        -- {'val': 202300001}
SELECT "EmployeeID","FirstName","KGID","DesignationID","RankID"
  FROM "clean"."clean_Employee" WHERE "EmployeeID" = :val LIMIT 1       -- {'val': 5313}
→ "The investigating officer for CaseNo 202300001 is Oliver (EmployeeID 5313, KGID: KG10313)."
→ response_type = officer_details, GROQ CALLED: NO
```

### Flow 2: ETL Pipeline (Raw Data → Clean Schema)

```
Trigger: POST /api/v1/etl/run
     │
     ▼
ETLPipeline.run()
     │
     ├─► Step 0: Schema Discovery (SchemaDiscovery)
     │   • SQLAlchemy Inspector auto-discovers tables, columns, PKs, FKs
     │   • Zero hardcoded table/column names
     │   • Builds DatabaseMetadata with RelationshipMetadata
     │
     ├─► Step 1: Extract (DataExtractor)
     │   • Chunked SELECT queries via SQLAlchemy
     │   • Loads into Pandas DataFrames
     │   • Per-table error isolation
     │
     ├─► Step 2: Profile (DataProfiler)
     │   • Null analysis, duplicate detection, outlier detection
     │   • Type mismatch identification
     │   • Generates per-table quality reports
     │
     ├─► Step 3 & 4: Clean + Transform
     │   • CleaningPipeline (10 composable cleaners):
     │     NullNormalizer, TrimSpaces, CollapseSpaces, GenderNormalizer,
     │     PhoneNormalizer, CrimeNumberNormalizer, DateNormalizer,
     │     DatetimeConverter, DuplicateRemover, NumericConverter
     │   • TransformationPipeline (7 transformers, derived columns):
     │     crime_year/month/week/weekday, crime_hour, is_weekend,
     │     is_night_crime, incident_duration_hours, canonical_address, search_text
     │
     ├─► Step 5: Validate (DataValidator)
     │   • PK/FK integrity checks
     │   • Range validation, referential integrity
     │   • Generates validation reports
     │
     └─► Step 6: Load (DataLoader)
         • Transactional TRUNCATE + INSERT into `clean` schema
         • Safe rollback on failure
         • Returns row counts per table
```

### Flow 3: Knowledge Layer Build (Clean Data → Graph + Vectors)

```
Trigger: POST /api/v1/etl/run → POST /api/v1/documents/build → POST /api/v1/graph/build → POST /api/v1/embedding/build
     │
     ├─► Document Generation (DocumentOrchestrator)
     │   │
     │   ├── 6 Specialized Builders:
     │   │   CaseSummaryBuilder, AccusedProfileBuilder, VictimProfileBuilder,
     │   │   OfficerProfileBuilder, DistrictSummaryBuilder, CourtSummaryBuilder
     │   │
     │   ├── Each builder reads from PostgreSQL `clean` schema (requires the ETL to have run)
     │   ├── Generates rich natural-language AI Documents (structured JSON)
     │   ├── DocumentValidator checks quality (length, completeness)
     │   └── Saves to DocumentStore (file-based JSON storage)
     │
     ├─► Neo4j Knowledge Graph (GraphBuilder)
     │   │
     │   ├── Source resolution via ColumnMapper, per logical table:
     │   │   clean.clean_<T> if the ETL produced it, else <SOURCE_SCHEMA>.<T>
     │   │   (REQUIRE_CLEAN_SCHEMA=true → clean only, hard ETL error otherwise)
     │   │   Unresolvable table → reported with both candidate names; if none
     │   │   resolve, build returns HTTP 500 — never a "success" with 0 nodes
     │   │
     │   ├── Pass 1: Load Nodes (11 labels, MERGE on the stable key, SET n += row)
     │   │   Case{CaseMasterID}  Accused{AccusedMasterID}  Victim{VictimMasterID}
     │   │   Complainant{ComplainantID}  Employee{EmployeeID}  Court{CourtID}
     │   │   District{DistrictID}  Unit{UnitID}  Arrest{ArrestSurrenderID}
     │   │   Chargesheet{CSID}  ActSection{ActID, SectionID}
     │   │   → an accused named "Fiyaz Saran" on 15 cases is 15 distinct nodes;
     │   │     PersonID / AccusedMasterID / CaseMasterID are the identity, never the name
     │   │
     │   ├── Pass 2: Load Relationships (17 types)
     │   │   (District)-[:HAS_UNIT]->(Unit)          (District)-[:HAS_COURT]->(Court)
     │   │   (Unit)-[:HAS_EMPLOYEE]->(Employee)      (Employee)-[:WORKS_IN]->(District)
     │   │   (Case)-[:REGISTERED_AT]->(Unit)         (Case)-[:HEARD_IN]->(Court)
     │   │   (Employee)-[:INVESTIGATES]->(Case)      (Case)-[:HAS_ACCUSED]->(Accused)
     │   │   (Case)-[:HAS_VICTIM]->(Victim)          (Case)-[:HAS_COMPLAINANT]->(Complainant)
     │   │   (Case)-[:HAS_SECTION]->(ActSection)     (Case)-[:HAS_CHARGESHEET]->(Chargesheet)
     │   │   (Employee)-[:FILES_CHARGESHEET]->(Chargesheet)
     │   │   (Case)-[:HAS_ARREST]->(Arrest)          (Arrest)-[:ARRESTED_PERSON]->(Accused)
     │   │   (Employee)-[:MADE_ARREST]->(Arrest)     (Arrest)-[:PRODUCED_IN]->(Court)
     │   │
     │   ├── Server-side cursors for memory-efficient batch processing
     │   ├── Idempotent MERGE operations (fully restartable)
     │   └── Automatic constraint & index management via SchemaManager
     │
     │   Last local build (2026-09-22, from clean): 11 tables, 40,101 nodes, 86,160 relationships,
     │   0 errors — Case 5000 · Accused 12392 · Victim 5000 · Complainant 5000 · Employee 500 ·
     │   Unit 250 · Court 80 · District 31 · Arrest 9372 · Chargesheet 2475 · ActSection 1
     │
     └─► Embedding Generation (EmbeddingPipeline)
         │
         ├── Reads AI Documents from DocumentStore
         ├── BAAI/bge-small-en-v1.5 model (384 dimensions)
         ├── BatchProcessor for efficient GPU/CPU encoding
         ├── VectorValidator checks dimension integrity
         ├── CollectionManager creates/rebuilds Qdrant collection
         ├── QdrantLoader upserts vectors with metadata payloads
         └── SyncManager tracks manifest for incremental updates
```

### Flow 4: Retrieval Pipeline (Query → Ranked Results)

```
Query Input
     │
     ▼
RetrievalEngine.query() / hybrid() / search()
     │
     ├─► QueryProcessor: Clean, normalize, lowercase, remove stop words
     │
     ├─► QueryEmbedding: Encode query with BAAI/bge-small-en-v1.5
     │
     ├─► CacheManager: Check LRU cache (configurable TTL=300s, size=256)
     │
     ├─► MetadataFilter: Build Qdrant filter conditions from request
     │
     ├─► SemanticSearch: Qdrant ANN search (configurable top_k, threshold)
     │
     ├─► GraphSearch (Hybrid only): Neo4j traversal by extracted entities
     │
     ├─► RankingEngine: Multi-factor scoring:
     │   • Semantic similarity (primary weight)
     │   • Freshness (recency boost)
     │   • Type priority (case_summary > accused_profile > etc.)
     │   • Metadata richness (more fields = higher score)
     │
     ├─► ExplainabilityBuilder: Per-result score breakdown
     │   Human-readable ranking reasons per document
     │
     └─► ContextBuilder: Assembles ranked docs into LLM-ready context window
         (Respects max_context_tokens=4000)
```

---

## ✅ Phase 1 — Automated ETL Pipeline
**Status: COMPLETE**

### Modules (backend/app/etl/)

| Module | File | Responsibility |
|--------|------|----------------|
| Schema Discovery | `schema_discovery.py` | Auto-discovers PostgreSQL schema via SQLAlchemy Inspector |
| Data Extraction | `extract.py` | Chunked data extraction into Pandas DataFrames |
| Data Profiling | `profile.py` | Quality analysis (nulls, duplicates, outliers, type mismatches) |
| Cleaning Pipeline | `cleaning.py` | 10 composable cleaners (NullNormalizer, DateNormalizer, etc.) |
| Transformation | `transform.py` | 7 transformers producing derived columns (crime_year, is_night_crime, search_text, etc.) |
| Validation | `validation.py` | PK/FK integrity, range validation |
| Data Loading | `load.py` | Transactional TRUNCATE+INSERT into `clean` schema |
| Pipeline Orchestrator | `pipeline.py` | Full pipeline: Discovery → Extract → Profile → Clean → Transform → Validate → Load |
| Configuration | `config.py` | ETLConfig with batch size, workers, schema settings |
| Metadata Models | `metadata.py` | DatabaseMetadata, TableMetadata, RelationshipMetadata |
| Interfaces | `interfaces.py` | DataProvider protocol for downstream consumption |

**API Endpoints:**
- `POST /api/v1/etl/run` — Run full ETL pipeline (then refreshes the ColumnMapper)
- `GET /api/v1/etl/status` — Last pipeline run status
- `GET /api/v1/etl/schema`, `/tables`, `/relationships` — Discovery output
- `GET /api/v1/etl/reports/profile/{table}`, `/reports/validation/{table}`, `/reports/summary` — Reports

**Local state:** run on 2026-09-22 — 11 tables, 45,100 rows loaded into `clean.clean_*` in 18.6s, 0 errors.

---

## ✅ Phase 2 — Knowledge Layer
**Status: COMPLETE**

### 2a — AI Document Generation (backend/app/document_generation/)

| Module | File | Responsibility |
|--------|------|----------------|
| Orchestrator | `document_builder.py` | Coordinates all 6 builders, validation, storage |
| Case Builder | `case_builder.py` | Rich case narrative summaries |
| Accused Builder | `accused_builder.py` | Accused person profiles |
| Victim Builder | `victim_builder.py` | Victim profiles |
| Officer Builder | `officer_builder.py` | Investigating officer profiles |
| District Builder | `district_builder.py` | District-level crime summaries |
| Court Builder | `court_builder.py` | Court proceeding summaries |
| Document Store | `document_store.py` | File-based JSON document storage |
| Validator | `validation.py` | Quality validation (length, completeness) |
| Statistics | `statistics.py` | Generation progress tracking |

**API Endpoints:**
- `POST /api/v1/documents/build` — Generate all AI documents
- `GET /api/v1/documents/statistics` — Document store stats

### 2b — Neo4j Knowledge Graph (backend/app/graph/)

**11 Node Labels** (MERGE key in braces):
`Case{CaseMasterID}`, `Accused{AccusedMasterID}`, `Victim{VictimMasterID}`, `Complainant{ComplainantID}`, `Employee{EmployeeID}`, `Court{CourtID}`, `District{DistrictID}`, `Unit{UnitID}`, `Arrest{ArrestSurrenderID}`, `Chargesheet{CSID}`, `ActSection{ActID, SectionID}`. Every source column becomes a node property (`SET n += row`), so properties carry the physical PostgreSQL names (`CaseNo`, `CrimeNo`, `AccusedName`, `PersonID`, `FirstName`, `KGID`, …).

**17 Relationship Types:**
`HAS_UNIT`, `HAS_COURT`, `HAS_EMPLOYEE`, `WORKS_IN`, `REGISTERED_AT`, `HEARD_IN`, `INVESTIGATES`, `HAS_ACCUSED`, `HAS_VICTIM`, `HAS_COMPLAINANT`, `HAS_SECTION`, `HAS_CHARGESHEET`, `FILES_CHARGESHEET`, `HAS_ARREST`, `ARRESTED_PERSON`, `MADE_ARREST`, `PRODUCED_IN`.

| Module | File | Responsibility |
|--------|------|----------------|
| Graph Builder | `builder.py` | Resolves logical source tables via `ColumnMapper`; 2-pass orchestration (Nodes → Relationships); `status` / `source_tables` / `tables_failed` reporting; `GraphBuildError` when nothing loads |
| Schema Manager | `schema_manager.py` | Unique constraints on every MERGE key, indexes on `CaseNo` / `CrimeNo` |
| Node Queries | `queries/nodes.py` | Cypher MERGE queries keyed by logical table (`"CaseMaster"`, not `"clean_CaseMaster"`) |
| Relationship Queries | `queries/relationships.py` | 17 MERGE queries keyed `"<LogicalTable>:<REL_TYPE>"` |
| Config | `config.py` | `source_schema`, `clean_schema`, `require_clean_schema`, batch size |

**API Endpoints:**
- `POST /api/v1/graph/build` / `POST /api/v1/graph/update` — Build (idempotent MERGE upsert); HTTP 500 with per-table `schema.table` errors when no source can be resolved
- `GET /api/v1/graph/statistics` — Live node counts per label and relationship counts per type

**Verification queries (pass on the local build):**
```cypher
MATCH (c:Case {CaseNo: 202300001}) RETURN c.CaseMasterID, c.CrimeNo, c.PolicePersonID   // 1, 100170200202300001, 5313
MATCH (a:Accused {PersonID: 'A1'}) RETURN a.AccusedMasterID, a.AccusedName, a.CaseMasterID   // 1, 'Fiyaz Saran', 1
MATCH (c:Case {CaseNo: 202300001})-[:HAS_ACCUSED]->(a:Accused {PersonID: 'A1'}) RETURN a.AccusedMasterID
MATCH (a:Accused {AccusedName: 'Fiyaz Saran'}) RETURN count(a), count(DISTINCT a.PersonID)    // 15, 15
```

### 2c — Embedding Generation & Qdrant (backend/app/embeddings/)

| Module | File | Responsibility |
|--------|------|----------------|
| Embedding Pipeline | `embedding_pipeline.py` | Full build, incremental sync, rebuild |
| Model Manager | `model_manager.py` | Singleton model loader (BAAI/bge-small-en-v1.5) |
| Batch Processor | `batch_processor.py` | Efficient batched encoding |
| Vector Validator | `vector_validator.py` | Dimension & integrity validation |
| Collection Manager | `collection_manager.py` | Qdrant collection create/rebuild |
| Qdrant Loader | `qdrant_loader.py` | Vector upsert with metadata |
| Qdrant Search | `qdrant_search.py` | ANN search with filters |
| Sync Manager | `sync_manager.py` | Manifest-based incremental updates |
| Embedding Manager | `embedding_manager.py` | Document stream processing |
| Statistics | `statistics.py` | Processing progress tracking |
| Config | `config.py` | Model, Qdrant, collection settings |

**API Endpoints** (prefix is singular `/api/v1/embedding`):
- `POST /api/v1/embedding/build` — Full vector build
- `POST /api/v1/embedding/update` — Incremental sync
- `DELETE /api/v1/embedding/rebuild` — Drop collection and rebuild
- `POST /api/v1/embedding/search` — Semantic search
- `GET /api/v1/embedding/statistics`, `/models`, `/health`

---

## ✅ Phase 3 — Enterprise Retrieval Engine
**Status: COMPLETE**

### Modules (backend/app/retrieval/)

| Module | File | Responsibility |
|--------|------|----------------|
| Retrieval Engine | `retrieval_engine.py` | Facade: query(), search(), hybrid(), context(), health() |
| Query Processor | `query_processor.py` | Cleans, normalizes, extracts entities from queries |
| Query Embedding | `query_embedding.py` | Encodes processed queries to vectors |
| Metadata Filter | `metadata_filter.py` | Builds Qdrant filter conditions |
| Semantic Search | `semantic_search.py` | Qdrant ANN search with configurable parameters |
| Graph Search | `graph_search.py` | Neo4j traversal enrichment (decoupled from runtime) |
| Ranking Engine | `ranking_engine.py` | Multi-factor scoring: similarity + freshness + type + richness |
| Explainability | `explainability.py` | Per-result score breakdown with human-readable reasons |
| Context Builder | `context_builder.py` | Assembles ranked docs into LLM context window |
| Cache Manager | `cache_manager.py` | LRU query cache (size=256, TTL=300s) |
| Analytics | `analytics.py` | Score distributions, type breakdowns, top documents |

**API Endpoints:**
- `GET /api/v1/retrieval/statistics` — Retrieval analytics
- `GET /api/v1/retrieval/health` — Engine health status
- `GET /api/v1/retrieval/config` — Current configuration

`RetrievalEngine.search()` / `hybrid()` / `context()` are consumed internally by the chat planner (`qdrant_tools.search_similar_cases`); they are not exposed over HTTP.

---

## ✅ Phase 4 — GraphRAG + LLM Integration
**Status: COMPLETE**

### Modules (backend/app/llm/ & backend/app/rag/)

| Module | File | Responsibility |
|--------|------|----------------|
| LLM Client | `llm/client.py` | Provider factory (Groq) |
| Groq Provider | `llm/providers/groq_provider.py` | Groq API integration; model from `MODEL_NAME` |
| Prompt Builder | `llm/prompt_builder.py` | Legacy GraphRAG prompt (the router builds its own compact prompt) |
| Schemas | `llm/schemas.py` | ChatRequest, ChatResponse (`answer` + `response_type` + `data`), RetrievalMetrics, Citation |
| Citation Builder | `rag/citation_builder.py` | Maps document IDs cited by the LLM back to sources |
| Response Builder | `rag/response_builder.py` | Assembles ChatResponse, computes confidence |
| Validator | `rag/validator.py` | Query validation |

**API Endpoints:**
- `POST /api/v1/chat` — Synchronous chat (full JSON response). Tool/DB failures → HTTP 500 with a user-safe message
- `POST /api/v1/chat/stream` — SSE chat. Events: `token` → `complete` (with `response_type`, `data`, `citations`, `sources`, `confidence`, `retrieval`) → `[DONE]`; failures → `error` event + `[DONE]`

**Groq usage:** factual/identifier queries make **0** LLM calls; reasoning queries make exactly **1** (a previous double call per request was removed).

---

## ✅ Phase 5 — Streamlit Frontend (AI Copilot UI)
**Status: COMPLETE**

### Modules (frontend/)

| Module | File | Responsibility |
|--------|------|----------------|
| Entry Point | `app.py` | Page config, global CSS (incl. `.ci-*` card/table styles), health check, routing |
| Chat Page | `pages/Chat.py` | SSE streaming, structured rendering via ResponseRenderer, Citations & Metrics expander |
| Response Renderer | `components/response_renderer.py` | `render_response()` dispatches on `response_type`: `case_details`, `officer_details`, `person_details`, `search_results`, `statistics`; Markdown `answer` fallback; HTML-escaped, never raw JSON/Markdown |
| Chat Message | `components/chat_message.py` | Native `st.chat_message` containers (Markdown renders; components nest inside bubbles) |
| Response Schemas | `api/schemas.py` | `TypedDict`s mirroring the backend `response_type`/`data` contract |
| Dashboard | `pages/Dashboard.py` | System health, score distributions, Plotly analytics |
| About Page | `pages/About.py` | Architecture overview, technology stack docs |
| Sidebar | `components/sidebar.py` | Live health indicator, model info, query settings |
| Backend Client | `api/client.py` | httpx REST client (no direct DB access); parses `response_type`/`data` from JSON and SSE `complete` |
| Utilities | `utils/` | Helpers, constants, formatters |

**Design Features:**
- Inter font family, gradient sidebar, rounded inputs
- Database results rendered as field-grid cards and scrollable tables (responsive grid, 2 columns on phones)
- Multi-record name searches show every record with `AccusedMasterID` / `CaseMasterID` / `PersonID` plus a disambiguation note
- Hidden Streamlit branding for professional appearance
- Error handling with retry connection button; backend `error` events shown inline, stream never hangs

---

## ✅ Phase 6 — Hybrid Architecture & Reliability
**Status: COMPLETE**

### Modules (backend/app/services/tools/)

| Module | File | Responsibility |
|--------|------|----------------|
| Query Router | `router.py` | Factual vs reasoning routing; attaches `response_type`/`data`; re-raises `ToolError` for the API boundary; `[TRACE]` logging |
| Intent Detector | `intent_detector.py` | Regex classifier; extracts typed identifiers and keeps `case_number` / `crime_number` / `case_id` / `officer_id` / `accused_name` distinct |
| Query Planner | `planner.py` | Deterministic tool execution (no LLM decision-making); CaseNo → CaseMasterID → PolicePersonID → Employee chains; clean not-found messages |
| Planner Context | `planner_context.py` | Shared state container (typed identifiers + DTO results) |
| Column Mapper | `mapper.py` | Logical table/column → physical `schema.table.column` from `information_schema`; clean-preferred with source-schema fallback; column types for identifier coercion; diagnostic `MappingError`s; `resolve_physical_table()` shared with the graph builder |
| Template Engine | `template_engine.py` | Zero-LLM Markdown answers from DTOs (incl. multi-record accused-by-name) |
| Tool Registry | `tool_registry.py` | Tool registration (kept for the LLM tool-calling schema) |
| Context Builder | `context_builder.py` | Compact case summary text for the reasoning path |
| PostgreSQL Tools | `postgres_tools.py` | Parameterised lookups with explicit column lists; values coerced to physical types; `DatabaseQueryError` on failure |
| Neo4j Tools | `neo4j_tools.py` | Graph traversal tools (networks, co-accused, timelines) — see Known Issues |
| Qdrant Tools | `qdrant_tools.py` | Semantic search tool wrapper |
| DTOs | `dtos.py` | `CaseLookupDTO`, `OfficerDTO`, `VictimDTO`, `AccusedDTO` (with `person_id`, `case_id`), `ChargesheetDTO` |
| Exceptions | `exceptions.py` | `ToolError` → `MappingError`, `DatabaseQueryError`, `IdentifierValidationError` (each with a user-safe message) |
| Tracing | `tracing.py` | `trace()` helper for structured DEBUG records (no secrets) |
| Schemas | `schemas.py` | ToolCall, ToolResult data models |

**Schema resolution policy** (`REQUIRE_CLEAN_SCHEMA`, default `false`): for each logical table `T`, use `<CLEAN_SCHEMA>.clean_T` if it exists, else `<SOURCE_SCHEMA>.T`. With `true`, only clean is accepted and a missing table fails startup / graph build with an explicit ETL error. The mapper is refreshed after `POST /etl/run` so newly created clean tables take effect without a restart.

### Database Initialization (backend/app/database_initializer/)

| Module | File | Responsibility |
|--------|------|----------------|
| Orchestrator | `initializer.py` | Coordinates PostgreSQL → Neo4j → Qdrant initialization |
| PostgreSQL Init | `postgres_initializer.py` | Schema bootstrapping, CSV data loading |
| Neo4j Init | `neo4j_initializer.py` | Graph population from clean schema |
| Qdrant Init | `qdrant_initializer.py` | Vector collection from local storage |

---

## 🏗️ Infrastructure & Local Runtime

| Service | Runtime | Default Port / Location |
|---------|---------|-------------------------|
| FastAPI Backend | Uvicorn (Native Python) | `http://127.0.0.1:8000` |
| Streamlit Frontend | Streamlit (Native Python) | `http://localhost:8501` |
| PostgreSQL | PostgreSQL 16 | `localhost:5432` |
| Neo4j | Neo4j 5 Community / Desktop | `bolt://localhost:7687` |
| Qdrant | Local Embedded (No Server) | `./qdrant_storage` |
| Groq LLM | Cloud API | `api.groq.com` |
| Embedding Model | Local CPU/GPU | HuggingFace cache |

---

## 📁 Complete Project Structure

```
crime-intelligence-bot/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory + lifespan handler
│   │   ├── api/v1/                    # REST API route handlers
│   │   │   ├── chat_routes.py         #   /chat, /chat/stream
│   │   │   ├── etl_routes.py          #   /etl/run, /etl/status, /etl/schema
│   │   │   ├── graph_routes.py        #   /graph/build, /graph/statistics
│   │   │   ├── document_routes.py     #   /documents/build, /documents/statistics
│   │   │   ├── embedding_routes.py    #   /embedding/build, /embedding/update, /embedding/search
│   │   │   └── retrieval_routes.py    #   /retrieval/statistics, /health, /config
│   │   ├── core/                      # Configuration & database connections
│   │   │   ├── config.py              #   Pydantic Settings (.env reader)
│   │   │   ├── database.py            #   SQLAlchemy engine singleton
│   │   │   ├── neo4j_db.py            #   Neo4j driver singleton
│   │   │   └── logging_config.py      #   Structured logging + stage timers
│   │   ├── database_initializer/      # Auto DB bootstrapping on startup
│   │   │   ├── initializer.py         #   Orchestrator (PG → Neo4j → Qdrant)
│   │   │   ├── postgres_initializer.py#   Schema + CSV data loading
│   │   │   ├── neo4j_initializer.py   #   Graph population
│   │   │   └── qdrant_initializer.py  #   Vector restoration
│   │   ├── etl/                       # ETL pipeline modules
│   │   │   ├── pipeline.py            #   Pipeline orchestrator
│   │   │   ├── schema_discovery.py    #   Auto schema inspection
│   │   │   ├── extract.py             #   Data extraction
│   │   │   ├── profile.py             #   Data quality profiling
│   │   │   ├── cleaning.py            #   10 composable cleaners
│   │   │   ├── transform.py           #   7 transformers (derived columns)
│   │   │   ├── validation.py          #   PK/FK integrity checks
│   │   │   ├── load.py                #   Transactional loader
│   │   │   ├── config.py              #   ETL configuration
│   │   │   ├── metadata.py            #   Schema metadata models
│   │   │   ├── interfaces.py          #   DataProvider protocol
│   │   │   └── utils.py               #   Helpers
│   │   ├── document_generation/       # AI document builder
│   │   │   ├── document_builder.py    #   Orchestrator (6 builders)
│   │   │   ├── case_builder.py        #   Case summaries
│   │   │   ├── accused_builder.py     #   Accused profiles
│   │   │   ├── victim_builder.py      #   Victim profiles
│   │   │   ├── officer_builder.py     #   Officer profiles
│   │   │   ├── district_builder.py    #   District summaries
│   │   │   ├── court_builder.py       #   Court summaries
│   │   │   ├── document_store.py      #   JSON file storage
│   │   │   ├── validation.py          #   Quality checks
│   │   │   └── statistics.py          #   Progress tracker
│   │   ├── graph/                     # Neo4j knowledge graph
│   │   │   ├── builder.py             #   2-pass builder (Nodes → Rels), mapper-based source resolution
│   │   │   ├── schema_manager.py      #   Constraints & indexes
│   │   │   ├── config.py              #   source/clean schema, require_clean_schema, batch size
│   │   │   └── queries/               #   Cypher query definitions keyed by LOGICAL table
│   │   │       ├── nodes.py           #     11 node MERGE queries
│   │   │       └── relationships.py   #     17 relationship MERGE queries
│   │   ├── embeddings/                # Vector embedding platform
│   │   │   ├── embedding_pipeline.py  #   Build, sync, rebuild
│   │   │   ├── model_manager.py       #   Singleton model loader
│   │   │   ├── batch_processor.py     #   Efficient batch encoding
│   │   │   ├── vector_validator.py    #   Dimension validation
│   │   │   ├── collection_manager.py  #   Qdrant collection management
│   │   │   ├── qdrant_loader.py       #   Vector upsert
│   │   │   ├── qdrant_search.py       #   ANN search
│   │   │   ├── sync_manager.py        #   Incremental updates
│   │   │   ├── embedding_manager.py   #   Stream processing
│   │   │   └── statistics.py          #   Processing stats
│   │   ├── retrieval/                 # Enterprise retrieval engine
│   │   │   ├── retrieval_engine.py    #   High-level facade
│   │   │   ├── query_processor.py     #   Query normalization
│   │   │   ├── query_embedding.py     #   Query vectorization
│   │   │   ├── metadata_filter.py     #   Qdrant filter builder
│   │   │   ├── semantic_search.py     #   ANN search executor
│   │   │   ├── graph_search.py        #   Neo4j enrichment
│   │   │   ├── ranking_engine.py      #   Multi-factor scorer
│   │   │   ├── explainability.py      #   Score breakdowns
│   │   │   ├── context_builder.py     #   LLM context assembly
│   │   │   ├── cache_manager.py       #   LRU query cache
│   │   │   └── analytics.py           #   Retrieval analytics
│   │   ├── services/tools/            # Hybrid AI tool system
│   │   │   ├── router.py              #   Query routing orchestrator
│   │   │   ├── intent_detector.py     #   Regex intent classifier
│   │   │   ├── planner.py             #   Deterministic tool planner
│   │   │   ├── planner_context.py     #   Shared state container
│   │   │   ├── mapper.py              #   ColumnMapper: logical → physical schema/table/column
│   │   │   ├── template_engine.py     #   Zero-LLM response templates
│   │   │   ├── tool_registry.py       #   Tool registration system
│   │   │   ├── context_builder.py     #   Tool result aggregator
│   │   │   ├── postgres_tools.py      #   Parameterised DB lookup tools
│   │   │   ├── neo4j_tools.py         #   Graph traversal tools
│   │   │   ├── qdrant_tools.py        #   Semantic search tools
│   │   │   ├── dtos.py                #   Data Transfer Objects
│   │   │   ├── exceptions.py          #   ToolError hierarchy (user-safe messages)
│   │   │   ├── tracing.py             #   [TRACE] debug logging helper
│   │   │   └── schemas.py             #   ToolCall/ToolResult models
│   │   ├── llm/                       # LLM client layer
│   │   │   ├── client.py              #   Abstract LLM interface
│   │   │   ├── prompt_builder.py      #   System/user prompt builder
│   │   │   ├── schemas.py             #   Request/Response models
│   │   │   ├── exceptions.py          #   LLM-specific errors
│   │   │   └── providers/
│   │   │       └── groq_provider.py   #   Groq API implementation
│   │   ├── rag/                       # RAG pipeline
│   │   │   ├── citation_builder.py    #   Citation extraction
│   │   │   ├── response_builder.py    #   Response structuring
│   │   │   └── validator.py           #   Quality validation
│   │   └── models/                    # SQLAlchemy ORM models
│   ├── tests/                         # Unit tests (273) + tests/integration (live DB)
│   │   ├── test_services/             #   mapper, postgres tools, router flows, intent detector
│   │   │   └── conftest.py            #   in-memory replica of the real public schema + fake DB
│   │   ├── test_graph/                #   graph builder source resolution & failure reporting
│   │   └── test_api/                  #   chat sync/SSE error contract
│   └── requirements.txt               # Python dependencies
├── frontend/
│   ├── app.py                         # Streamlit entry point + global CSS
│   ├── api/
│   │   ├── client.py                  # httpx REST client
│   │   └── schemas.py                 # Typed response_type/data schemas
│   ├── pages/
│   │   ├── Chat.py                    # SSE streaming chat UI with structured rendering
│   │   ├── Dashboard.py               # Analytics dashboard (Plotly)
│   │   └── About.py                   # Architecture docs
│   ├── components/
│   │   ├── response_renderer.py       # Cards/tables per response_type, Markdown fallback
│   │   ├── chat_message.py            # Native chat containers
│   │   ├── citation_card.py, metrics.py
│   │   └── sidebar.py                 # Navigation + health
│   ├── utils/                         # Helpers, constants
│   └── requirements.txt               # Frontend dependencies
├── datafiles/                         # Raw CSV crime data files
├── qdrant_storage/                    # Persistent Qdrant vector storage
├── load_datafiles_to_postgres.py      # Standalone data loader script
├── run_backend.ps1                    # PowerShell backend launcher
├── run_backend.bat                    # CMD backend launcher
├── run_frontend.ps1                   # PowerShell frontend launcher
├── run_frontend.bat                   # CMD frontend launcher
├── test_api.py                        # API test script
├── .env.example                       # Environment configuration template
├── .env                               # Active environment config (gitignored)
└── .gitignore                         # Git ignore rules
```

---

## 🔑 Key Design Decisions

1. **Hybrid AI Retrieval**: Not pure RAG — combines deterministic DB lookups (0 LLM calls for factual queries) with semantic search + LLM reasoning for complex questions
2. **Deterministic Planner**: Intent detection uses regex/keyword patterns (not LLM), making routing fast and predictable
3. **Zero-Hardcoded Schema**: ETL pipeline auto-discovers PostgreSQL schema via SQLAlchemy Inspector
4. **Decoupled Neo4j**: Chat API works even if Neo4j is offline; graph enrichment is optional
5. **Local-First Qdrant**: Uses embedded Qdrant (./qdrant_storage directory) — no server process required
6. **Auto-Initialization**: With `AUTO_INITIALIZE_DATABASE=true`, startup bootstraps PostgreSQL → ETL → Neo4j → Qdrant if they are empty (off by default locally)
7. **Dynamic Column Mapper**: Resolves logical tables/columns (e.g. `CaseMaster.case_number`) to the physical schema at startup from `information_schema`; prefers the ETL clean tables and falls back to the source schema (`REQUIRE_CLEAN_SCHEMA`). Never fabricates a mapping — missing tables/columns fail with a diagnostic
8. **Stable identifiers only**: `CaseNo`, `CrimeNo`, `CaseMasterID`, `EmployeeID`, `AccusedMasterID`, `PersonID` are distinct and typed; names are never treated as identity
9. **Database is the source of truth**: the LLM never answers factual record questions from memory — factual paths make 0 LLM calls, and tool/DB failures surface as structured errors rather than LLM fallbacks
10. **Dual response format**: every answer ships as Markdown (`answer`) and as structured data (`response_type` + `data`) so the UI can render cards/tables while any client still gets readable text

---

## ⚠️ Known Issues / Next Steps

1. **Neo4j tool property names** — `services/tools/neo4j_tools.py` and `retrieval/graph_search.py` reference `CrimeNumber`, `Age`, `Sex`, `EmployeeName`, `FIRNo`, but graph nodes carry the physical column names (`CrimeNo`, `AgeYear`, `GenderID`, `FirstName`). Case network / co-accused / timeline answers return nulls for those fields until aligned.
2. **`ActSection` has 1 node** — the sample `ActSectionAssociation` data has a single distinct `(ActID, SectionID)`.
3. **`prompt_builder.py` / `citation_builder.py`** are legacy GraphRAG components no longer on the chat path.
4. **Documents & embeddings** have not been (re)built locally since the ETL run; run `POST /documents/build` then `POST /embedding/build` to enable semantic search over current data.

---

## 📈 Performance Characteristics

| Metric | Value |
|--------|-------|
| Factual query latency | ~2–10 ms of SQL (0 LLM calls) |
| Semantic search latency | < 200ms |
| LLM reasoning latency | 2-5s (depends on Groq load) |
| Embedding generation | ~384 dimensions, batch 256 |
| Vector similarity threshold | 0.5 (configurable) |
| Query cache TTL | 300s |
| Query cache size | 256 entries |
| Max context tokens | 4000 |
