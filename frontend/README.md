# 🔍 Crime Intelligence Copilot — Frontend

Professional Streamlit interface for the Karnataka Police Crime Intelligence Platform.

## Quick Start

```bash
# 1. Install dependencies
cd frontend
pip install -r requirements.txt

# 2. Make sure the backend is running
#    (Docker container on localhost:8000)

# 3. Launch the app
streamlit run app.py
```

The app opens at **http://localhost:8501**.

## Pages

| Page | Description |
|------|-------------|
| **Chat** | AI investigation assistant — ask questions, get RAG‑grounded answers with citations |
| **Dashboard** | Backend health, retrieval analytics, configuration overview |
| **About** | System architecture, technology stack, pipeline phases |

## Project Structure

```
frontend/
├── app.py                   # Entry point
├── requirements.txt         # Python dependencies
├── api/
│   └── client.py            # REST client (httpx) for the FastAPI backend
├── components/
│   ├── sidebar.py           # Navigation, status, settings
│   ├── chat_message.py      # User / assistant message bubbles
│   ├── citation_card.py     # Citation cards with type badges
│   └── metrics.py           # Performance metrics panel
├── pages/
│   ├── Chat.py              # Main chat interface
│   ├── Dashboard.py         # System dashboard
│   └── About.py             # Architecture overview
└── utils/
    ├── constants.py          # URLs, colours, defaults
    └── helpers.py            # Formatting utilities
```

## Backend API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/chat` | Synchronous RAG chat |
| POST | `/api/v1/chat/stream` | Streaming SSE chat |
| GET | `/health` | Backend health check |
| GET | `/api/v1/retrieval/health` | Retrieval subsystem health |
| GET | `/api/v1/retrieval/statistics` | Query analytics |
| GET | `/api/v1/retrieval/config` | Engine configuration |

## Configuration

Edit `utils/constants.py` to change:

- `BACKEND_BASE_URL` — default `http://localhost:8000`
- `DEFAULT_TOP_K` — number of documents to retrieve
- `REQUEST_TIMEOUT` / `STREAM_TIMEOUT` — HTTP timeouts

## Features

- ✅ Chat with session history
- ✅ Streaming token‑by‑token display
- ✅ Citation cards with document type badges
- ✅ Performance metrics panel
- ✅ Backend health monitoring
- ✅ Retrieval analytics with Plotly charts
- ✅ Error handling for offline/timeout scenarios
- ✅ Clean, professional police‑themed UI
