# Crime-Bot Backend — ETL Pipeline

Production-ready FastAPI backend with an integrated ETL (Extract, Transform, Load) pipeline that automatically discovers, profiles, cleans, transforms, validates, and loads crime data from PostgreSQL.

## Architecture

```
PostgreSQL (Raw) → ETL Pipeline → PostgreSQL (Clean) → Graph Builder → Neo4j (Knowledge Graph)
```

The pipeline is **zero-hardcoded**: it discovers all tables, columns, relationships, and data types automatically from PostgreSQL metadata. No table names or column names are hardcoded anywhere. Cleaned data is then used as the single source of truth to construct the Neo4j Knowledge Graph.

### Module Overview

| Module | Purpose |
|--------|---------|
| `schema_discovery.py` | Introspects PostgreSQL via SQLAlchemy Inspector |
| `metadata.py` | Pydantic models for the schema graph |
| `extract.py` | Loads every table into Pandas DataFrames |
| `profile.py` | Detects data quality issues (missing, duplicates, outliers, etc.) |
| `cleaning.py` | 11 reusable cleaners (Strategy pattern) |
| `transform.py` | 7 derived field generators (CrimeYear, NightCrime, SearchText, etc.) |
| `validation.py` | PK/FK integrity, type conformance, range checks |
| `load.py` | Transactional TRUNCATE+INSERT into clean schema |
| `pipeline.py` | Orchestrates the full flow with per-table error isolation |
| `graph/builder.py`| Two-pass Neo4j Graph loading (Nodes then Relationships) |
| `graph/schema_manager.py`| Manages Neo4j Constraints and Indexes |
| `interfaces.py` | Abstract interfaces for Neo4j, Qdrant, RAG, LLM Agent |

### Future Module Integration

The `PipelineResult` object implements the `DataProvider` protocol:

```python
from app.etl.interfaces import DataProvider

result: DataProvider = pipeline.run()
result.get_clean_dataframes()      # Dict[str, DataFrame]
result.get_table_metadata("table") # TableMetadata
result.get_relationship_graph()    # Dict[str, List[str]]
result.get_relationships()         # List[RelationshipMetadata]
```

## Setup

### 1. Clone & Install

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env
# Edit .env with your PostgreSQL connection details
```

Key variables:
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://user:password@localhost:5432/crime_db` | PostgreSQL connection |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Connection URI |
| `NEO4J_USERNAME` | `neo4j` | Neo4j Username |
| `NEO4J_PASSWORD` | `password` | Neo4j Password |
| `SOURCE_SCHEMA` | `public` | Schema to read from |
| `CLEAN_SCHEMA` | `clean` | Schema for cleaned tables |
| `BATCH_SIZE` | `10000` | Rows per batch for large tables |
| `EVIDENCE_COLUMN_PATTERNS` | `narrative,evidence,...` | Columns to preserve (not text-clean) |

### 3. Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test

```bash
pytest tests/ -v --tb=short
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/etl/run` | Run full ETL pipeline |
| `GET` | `/api/v1/etl/status` | Last pipeline run status |
| `GET` | `/api/v1/etl/schema` | Discover database schema |
| `GET` | `/api/v1/etl/tables` | List discovered tables |
| `GET` | `/api/v1/etl/relationships` | Table relationship graph |
| `GET` | `/api/v1/etl/reports/profile/{table}` | Profiling report |
| `GET` | `/api/v1/etl/reports/validation/{table}` | Validation report |
| `GET` | `/api/v1/etl/reports/summary` | Pipeline summary |
| `POST` | `/api/v1/graph/build` | Build Neo4j Knowledge Graph |
| `POST` | `/api/v1/graph/update`| Incrementally update Neo4j Graph |
| `GET`  | `/api/v1/graph/statistics`| Live Neo4j node/relationship stats |

## Clean Schema

The ETL **never modifies raw tables**. Cleaned data is written to the `clean` schema:

```
public.CaseMaster  →  clean.clean_casemaster
public.Accused     →  clean.clean_accused
public.Victim      →  clean.clean_victim
```

Loading uses transactional TRUNCATE + INSERT to preserve indexes and constraints.

## Data Cleaning

11 composable cleaners applied in order:

1. **NullNormalizer** — "NULL", "N/A", "" → `None`
2. **TrimSpaces** — Strip leading/trailing whitespace
3. **CollapseSpaces** — Multiple spaces → single
4. **GenderNormalizer** — M/Male/MALE → "Male"
5. **PhoneNormalizer** — Indian phone numbers (+91, 0-prefix)
6. **CrimeNumberNormalizer** — FIR/crime number standardization
7. **DateNormalizer** — Multiple formats → ISO 8601
8. **DatetimeConverter** — String → datetime64
9. **DuplicateRemover** — Exact row deduplication
10. **NumericConverter** — String → numeric types

**Evidence columns** (matching configurable patterns) are **never text-cleaned**.

## Derived Fields

Generated automatically from available columns:

| Field | Source | Logic |
|-------|--------|-------|
| `crime_year` | datetime | Year extraction |
| `crime_month` | datetime | Month extraction |
| `crime_week` | datetime | ISO week |
| `crime_hour` | datetime | Hour extraction |
| `crime_weekday` | datetime | Day name |
| `is_weekend` | datetime | Saturday/Sunday |
| `is_night_crime` | datetime | 22:00–06:00 |
| `incident_duration_hours` | start/end pair | Duration in hours |
| `canonical_address` | address columns | Normalized concatenation |
| `search_text` | text columns | RAG-ready concatenation |

If a source column doesn't exist, the transformation is **skipped gracefully**.

## Reports

Generated in `app/etl/reports/`:
- `profile/{table}_profile.json` — Data quality analysis
- `validation/{table}_validation.json` — Integrity checks
- `pipeline_summary.json` — Overall run summary

## License

Internal project.
