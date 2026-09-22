# Crime Intelligence Copilot — Project Status & Architecture

This document provides a complete technical reference for the Karnataka Police Crime Intelligence Platform, covering all phases, architecture, processing flows, and module details.

Last updated: **2026-09-16**

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
│  │  /embeddings/*  /health                                                │ │
│  └────────────────────────────────┬────────────────────────────────────────┘ │
│                                   │                                          │
│  ┌────────────────────────────────▼────────────────────────────────────────┐ │
│  │                    Query Processing Layer                               │ │
│  │                                                                         │ │
│  │  QueryRouter → IntentDetector → QueryPlanner → ContextBuilder          │ │
│  │       │              │               │               │                  │ │
│  │       │         Regex+Keyword    Deterministic    Tool Aggregation      │ │
│  │       │         Classification   Tool Execution                         │ │
│  │       │                                                                 │ │
│  │       ├── Factual Path (0 LLM calls) → TemplateEngine → Response      │ │
│  │       └── Reasoning Path (1 LLM call) → Groq LLM → Response           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     Data Processing Layer                               │ │
│  │                                                                         │ │
│  │  ETL Pipeline         Document Generation      Knowledge Graph          │ │
│  │  (11 cleaners,        (6 builders: Case,       (11 node types,          │ │
│  │   10 transforms)       Accused, Victim,         17 relationship types)  │ │
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
│  │  Groq API (llama-3.3-70b-versatile) — cloud LLM inference             │ │
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
     │   • identifier_lookup (e.g., "case 123")
     │   • factual_query (e.g., "who is the officer for case 123?")
     │   • semantic_search (e.g., "robbery cases in Bangalore")
     │   • graph_query (e.g., "who is related to accused X?")
     │   • reasoning (e.g., "summarize case 123")
     │
     ├─► Resolve history identifiers (if "that case" referenced)
     │
     ├─► QueryPlanner.execute(intent)
     │   Deterministic tool execution (no LLM decision-making):
     │   • postgres_tools: get_case_lookup, get_officer_compact,
     │     get_case_victims_list, get_case_accused_list, get_chargesheet_status
     │   • neo4j_tools: find_case_network, find_co_accused, get_case_timeline
     │   • qdrant_tools: search_similar_cases
     │   Returns → PlannerContext with all fetched data
     │
     ├─► Decision Engine:
     │   ├── Factual/Identifier → TemplateEngine (0 LLM calls, instant response)
     │   └── Reasoning/Graph   → Groq LLM (1 LLM call with pre-fetched context)
     │
     └─► ResponseBuilder.build(query, answer, citations, sources, metrics)
              │
              ▼
         ChatResponse { answer, citations, sources, retrieval_metrics }
              │
              ▼
         Streamed to Streamlit via SSE or returned as JSON
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
     │   • CleaningPipeline (11 composable cleaners):
     │     NullNormalizer, DateNormalizer, GenderNormalizer,
     │     TextCleaner, NumericCleaner, AddressCleaner, etc.
     │   • TransformationPipeline (10 derived columns):
     │     CrimeYear, IsNightCrime, SearchText, AgeGroup, etc.
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
Trigger: POST /api/v1/documents/build → POST /api/v1/graph/build → POST /api/v1/embeddings/build
     │
     ├─► Document Generation (DocumentOrchestrator)
     │   │
     │   ├── 6 Specialized Builders:
     │   │   CaseSummaryBuilder, AccusedProfileBuilder, VictimProfileBuilder,
     │   │   OfficerProfileBuilder, DistrictSummaryBuilder, CourtSummaryBuilder
     │   │
     │   ├── Each builder reads from PostgreSQL `clean` schema
     │   ├── Generates rich natural-language AI Documents (structured JSON)
     │   ├── DocumentValidator checks quality (length, completeness)
     │   └── Saves to DocumentStore (file-based JSON storage)
     │
     ├─► Neo4j Knowledge Graph (GraphBuilder)
     │   │
     │   ├── Pass 1: Load Nodes (11 types)
     │   │   Case, Accused, Employee (Officer), Court, Victim,
     │   │   Offence, District, PoliceStation, Vehicle, MobileNumber, BankAccount
     │   │
     │   ├── Pass 2: Load Relationships (17 types)
     │   │   INVESTIGATED_BY, ACCUSED_IN, VICTIM_OF, CHARGED_WITH,
     │   │   OCCURRED_AT, REGISTERED_AT, USES_VEHICLE, HAS_PHONE,
     │   │   HAS_ACCOUNT, TRIED_AT, BELONGS_TO, etc.
     │   │
     │   ├── Server-side cursors for memory-efficient batch processing
     │   ├── Idempotent MERGE operations (fully restartable)
     │   └── Automatic constraint & index management via SchemaManager
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
| Cleaning Pipeline | `cleaning.py` | 11 composable cleaners (NullNormalizer, DateNormalizer, etc.) |
| Transformation | `transform.py` | 10 derived analytical columns (CrimeYear, IsNightCrime, etc.) |
| Validation | `validation.py` | PK/FK integrity, range validation |
| Data Loading | `load.py` | Transactional TRUNCATE+INSERT into `clean` schema |
| Pipeline Orchestrator | `pipeline.py` | Full pipeline: Discovery → Extract → Profile → Clean → Transform → Validate → Load |
| Configuration | `config.py` | ETLConfig with batch size, workers, schema settings |
| Metadata Models | `metadata.py` | DatabaseMetadata, TableMetadata, RelationshipMetadata |
| Interfaces | `interfaces.py` | DataProvider protocol for downstream consumption |

**API Endpoints:**
- `POST /api/v1/etl/run` — Run full ETL pipeline
- `GET /api/v1/etl/status` — Last pipeline run status
- `GET /api/v1/etl/schema` — Discover database schema

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

**11 Node Types:**
`Case`, `Accused`, `Employee`, `Court`, `Victim`, `Offence`, `District`, `PoliceStation`, `Vehicle`, `MobileNumber`, `BankAccount`

**17 Relationship Types:**
`INVESTIGATED_BY`, `ACCUSED_IN`, `VICTIM_OF`, `CHARGED_WITH`, `OCCURRED_AT`, `REGISTERED_AT`, `USES_VEHICLE`, `HAS_PHONE`, `HAS_ACCOUNT`, `TRIED_AT`, `BELONGS_TO`, and more investigative linkages.

| Module | File | Responsibility |
|--------|------|----------------|
| Graph Builder | `builder.py` | 2-pass orchestration (Nodes → Relationships) |
| Schema Manager | `schema_manager.py` | Constraints, indexes, schema initialization |
| Node Queries | `queries/nodes.py` | Cypher MERGE queries for all 11 node types |
| Relationship Queries | `queries/relationships.py` | Cypher MERGE queries for 17 relationship types |
| Config | `config.py` | Batch size, source schema settings |

**API Endpoints:**
- `POST /api/v1/graph/build` — Build Neo4j knowledge graph
- `GET /api/v1/graph/statistics` — Node/edge counts by type

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

**API Endpoints:**
- `POST /api/v1/embeddings/build` — Full vector build
- `POST /api/v1/embeddings/update` — Incremental sync
- `GET /api/v1/embeddings/statistics` — Collection stats

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
- `POST /api/v1/retrieval/search` — Semantic search
- `POST /api/v1/retrieval/hybrid` — Hybrid (semantic + graph) search
- `GET /api/v1/retrieval/statistics` — Retrieval analytics
- `GET /api/v1/retrieval/health` — Engine health status
- `GET /api/v1/retrieval/config` — Current configuration

---

## ✅ Phase 4 — GraphRAG + LLM Integration
**Status: COMPLETE**

### Modules (backend/app/llm/ & backend/app/rag/)

| Module | File | Responsibility |
|--------|------|----------------|
| LLM Client | `llm/client.py` | Abstract LLM client interface |
| Groq Provider | `llm/providers/groq_provider.py` | Groq API integration (llama-3.3-70b-versatile) |
| Prompt Builder | `llm/prompt_builder.py` | Structured system + user prompts with context |
| Schemas | `llm/schemas.py` | ChatRequest, ChatResponse, RetrievalMetrics, Citation |
| Citation Builder | `rag/citation_builder.py` | Extracts document references, scores, formats |
| Response Builder | `rag/response_builder.py` | Validates & structures LLM responses |
| Validator | `rag/validator.py` | Quality and completeness checks |

**API Endpoints:**
- `POST /api/v1/chat` — Synchronous RAG chat (full JSON response)
- `POST /api/v1/chat/stream` — SSE streaming RAG chat

---

## ✅ Phase 5 — Streamlit Frontend (AI Copilot UI)
**Status: COMPLETE**

### Modules (frontend/)

| Module | File | Responsibility |
|--------|------|----------------|
| Entry Point | `app.py` | Page config, global CSS, health check, routing |
| Chat Page | `pages/Chat.py` | Real-time SSE streaming, citation cards, retrieval metrics |
| Dashboard | `pages/Dashboard.py` | System health, score distributions, Plotly analytics |
| About Page | `pages/About.py` | Architecture overview, technology stack docs |
| Sidebar | `components/sidebar.py` | Live health indicator, model info, query settings |
| Backend Client | `api/client.py` | httpx REST client (no direct DB access) |
| Utilities | `utils/` | Helpers, constants, formatters |

**Design Features:**
- Inter font family, gradient sidebar, rounded inputs
- Metric cards with hover effects
- Hidden Streamlit branding for professional appearance
- Error handling with retry connection button

---

## ✅ Phase 6 — Hybrid Architecture & Reliability
**Status: COMPLETE**

### Modules (backend/app/services/tools/)

| Module | File | Responsibility |
|--------|------|----------------|
| Query Router | `router.py` | Hybrid pipeline orchestrator (factual vs reasoning paths) |
| Intent Detector | `intent_detector.py` | Regex + keyword query classifier (5 intent categories) |
| Query Planner | `planner.py` | Deterministic tool execution (no LLM decision-making) |
| Planner Context | `planner_context.py` | Shared state container for tool execution results |
| Column Mapper | `mapper.py` | Dynamic PostgreSQL schema → logical identifier mapping |
| Template Engine | `template_engine.py` | Zero-LLM response templates for factual queries |
| Tool Registry | `tool_registry.py` | Centralized tool registration and discovery |
| Context Builder | `context_builder.py` | Aggregates tool results into LLM-ready context |
| PostgreSQL Tools | `postgres_tools.py` | Direct DB lookups (cases, officers, victims, accused, chargesheets) |
| Neo4j Tools | `neo4j_tools.py` | Graph traversal tools (networks, co-accused, timelines) |
| Qdrant Tools | `qdrant_tools.py` | Semantic search tool wrapper |
| DTOs | `dtos.py` | Data Transfer Objects for tool results |
| Schemas | `schemas.py` | ToolCall, ToolResult data models |

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
│   │   │   ├── embedding_routes.py    #   /embeddings/build, /embeddings/update
│   │   │   └── retrieval_routes.py    #   /retrieval/search, /retrieval/hybrid
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
│   │   │   ├── cleaning.py            #   11 composable cleaners
│   │   │   ├── transform.py           #   10 derived columns
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
│   │   │   ├── builder.py             #   2-pass builder (Nodes → Rels)
│   │   │   ├── schema_manager.py      #   Constraints & indexes
│   │   │   ├── config.py              #   Graph build config
│   │   │   └── queries/               #   Cypher query definitions
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
│   │   │   ├── mapper.py              #   Dynamic column mapper
│   │   │   ├── template_engine.py     #   Zero-LLM response templates
│   │   │   ├── tool_registry.py       #   Tool registration system
│   │   │   ├── context_builder.py     #   Tool result aggregator
│   │   │   ├── postgres_tools.py      #   Direct DB lookup tools
│   │   │   ├── neo4j_tools.py         #   Graph traversal tools
│   │   │   ├── qdrant_tools.py        #   Semantic search tools
│   │   │   ├── dtos.py                #   Data Transfer Objects
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
│   ├── tests/                         # Unit & integration tests
│   └── requirements.txt               # Python dependencies
├── frontend/
│   ├── app.py                         # Streamlit entry point
│   ├── api/client.py                  # httpx REST client
│   ├── pages/
│   │   ├── Chat.py                    # SSE streaming chat UI
│   │   ├── Dashboard.py               # Analytics dashboard (Plotly)
│   │   └── About.py                   # Architecture docs
│   ├── components/
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
6. **Auto-Initialization**: On first startup, system auto-bootstraps all databases if they're empty
7. **Dynamic Column Mapper**: Resolves logical identifiers (e.g., "CrimeNumber") to physical schema columns at startup

---

## 📈 Performance Characteristics

| Metric | Value |
|--------|-------|
| Factual query latency | < 50ms (0 LLM calls) |
| Semantic search latency | < 200ms |
| LLM reasoning latency | 2-5s (depends on Groq load) |
| Embedding generation | ~384 dimensions, batch 256 |
| Vector similarity threshold | 0.5 (configurable) |
| Query cache TTL | 300s |
| Query cache size | 256 entries |
| Max context tokens | 4000 |
