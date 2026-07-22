# Crime Intelligence Copilot — Project Status

This document tracks the high-level progress of the Crime Intelligence Copilot implementation.

## Phase 1: Automated ETL Pipeline
**Status:** ✅ Completed

- Auto-discovers PostgreSQL Schema metadata
- Maps relationships dynamically
- Extracts all data via chunked processing into Pandas
- Profiles data quality
- Cleans and transforms strings, dates, coordinates
- Generates 7 derived analytical columns
- Performs PK/FK validation
- Loads securely using transactional TRUNCATE+INSERT into `clean` schema

## Phase 2: Neo4j Knowledge Graph Generation
**Status:** ✅ Completed

- Extracts data from `clean` schema via server-side cursors
- Generates 11 unique node types (Case, Accused, Employee, Court, etc.)
- Builds 17 highly specific relationship types mapping real-world investigative linkages
- Idempotent `MERGE` loader ensures restart-ability
- Handles Unique Constraints and Property Indexes automatically
- Exposed securely via `/api/v1/graph` FastAPI endpoints

## Phase 3: Text Embeddings & Qdrant Vector Store
**Status:** ⏳ Not Started

- Generate robust search texts from nodes
- Convert descriptions and texts into dense vector embeddings using an LLM embedding model
- Store and index vectors into Qdrant for semantic search functionality

## Phase 4: Hybrid Retrieval Engine
**Status:** ⏳ Not Started

- Combine Graph traversal (Neo4j) with semantic similarity (Qdrant)
- Support complex natural language queries (e.g., "Find cases matching this MO that were investigated by Officer X")

## Phase 5: LLM Agent Copilot
**Status:** ⏳ Not Started

- Integrate a conversational agent
- Wire the agent up to the Hybrid Retrieval Engine to answer investigative questions seamlessly.
