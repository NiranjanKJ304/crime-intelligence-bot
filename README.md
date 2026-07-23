# Karnataka Police Crime Intelligence Platform

> An end-to-end AI-powered crime investigation assistant built with FastAPI, Qdrant, Groq, and Streamlit.

---

## 🏛️ What is this?

The **Crime Intelligence Copilot** is a full-stack RAG (Retrieval-Augmented Generation) platform for the Karnataka Police that allows investigators to ask natural language questions against a corpus of crime records and receive grounded, citation-backed answers from a large language model.

The platform covers the entire ML engineering pipeline — from raw PostgreSQL data through ETL, Neo4j knowledge graph construction, vector embedding, semantic retrieval, LLM-based question answering, and a professional Streamlit UI.

---

## 🗺️ Architecture

```
User (Browser)
    │
    ▼
Streamlit Frontend  ← REST / SSE →  FastAPI Backend
                                         │
                    ┌────────────────────┤
                    │                    │
                    ▼                    ▼
              PostgreSQL           Groq LLM API
              (Crime Data)     (llama-3.3-70b-versatile)
                    │
                    ├──► ETL Pipeline → clean schema
                    ├──► Document Generation
                    ├──► Knowledge Graph → Neo4j
                    └──► Embeddings → Qdrant
                                   ▲
                              Semantic Search
                             (Retrieval Engine)
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI + Uvicorn |
| LLM Provider | Groq (`llama-3.3-70b-versatile`) |
| Embedding Model | `BAAI/bge-small-en-v1.5` (384-dim) |
| Vector Store | Qdrant |
| Graph Database | Neo4j 5 |
| Relational DB | PostgreSQL 16 |
| Frontend | Streamlit |
| Streaming | Server-Sent Events (SSE via `sse-starlette`) |
| Containerization | Docker + Docker Compose |

---

## 🚀 Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+)
- A [Groq API key](https://console.groq.com/) (free tier available)

### 1. Clone the repo

```bash
git clone https://github.com/NiranjanKJ304/crime-intelligence-bot.git
cd crime-intelligence-bot
```

### 2. Configure environment

```bash
cp .env.example .env
# Open .env and set your GROQ_API_KEY
```

### 3. Start the backend

```bash
docker compose up -d
```

Wait ~30 seconds for all services to become healthy. Check with:

```bash
docker compose ps
```

### 4. Start the Streamlit frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

---

## 📡 Backend API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Overall system health |
| `POST` | `/api/v1/chat` | Synchronous RAG chat |
| `POST` | `/api/v1/chat/stream` | Streaming SSE RAG chat |
| `POST` | `/api/v1/etl/run` | Run full ETL pipeline |
| `GET` | `/api/v1/etl/status` | Last pipeline status |
| `GET` | `/api/v1/etl/schema` | Discover DB schema |
| `POST` | `/api/v1/graph/build` | Build Neo4j graph |
| `GET` | `/api/v1/graph/statistics` | Graph node/edge counts |
| `POST` | `/api/v1/retrieval/search` | Semantic search |
| `GET` | `/api/v1/retrieval/statistics` | Retrieval analytics |
| `GET` | `/api/v1/retrieval/health` | Retrieval engine health |

Full interactive docs available at **http://localhost:8000/docs** (Swagger UI).

---

## 📁 Project Structure

```
crime-bot/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # FastAPI route handlers
│   │   ├── core/             # Config, settings
│   │   ├── etl/              # ETL pipeline modules
│   │   ├── document_generation/  # AI document builder
│   │   ├── graph/            # Neo4j graph builder
│   │   ├── embeddings/       # Embedding + Qdrant loader
│   │   ├── retrieval/        # Retrieval engine + ranking
│   │   ├── llm/              # LLM client + prompt builder
│   │   └── rag/              # RAG orchestrator + citations
│   ├── tests/                # Unit test suites
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── api/client.py         # httpx REST client
│   ├── pages/                # Chat, Dashboard, About
│   ├── components/           # Sidebar, Cards, Metrics
│   ├── utils/                # Helpers, constants
│   ├── app.py                # Streamlit entry point
│   └── requirements.txt
├── docker-compose.yml
├── docker-compose.override.yml  # Dev: bind-mount + reload
├── .env.example              # Environment template
└── PROJECT_STATUS.md         # Phase-by-phase status
```

---

## 🔒 Security Notes

- **Never commit `.env`** — it is listed in `.gitignore`
- Use `.env.example` as a template; fill in real values locally
- Change all default passwords before any production deployment
- Place NGINX or Traefik in front of port 8000 for SSL termination in production

---

## 📄 License

Internal project — Karnataka Police Crime Intelligence Platform.
