"""
Constants used across the Streamlit frontend.
"""

import os

# ── Backend ────────────────────────────────────────────────────────
BACKEND_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_CHAT = f"{BACKEND_BASE_URL}/api/v1/chat"
API_CHAT_STREAM = f"{BACKEND_BASE_URL}/api/v1/chat/stream"
API_HEALTH = f"{BACKEND_BASE_URL}/health"
API_RETRIEVAL_HEALTH = f"{BACKEND_BASE_URL}/api/v1/retrieval/health"
API_RETRIEVAL_STATS = f"{BACKEND_BASE_URL}/api/v1/retrieval/statistics"
API_RETRIEVAL_CONFIG = f"{BACKEND_BASE_URL}/api/v1/retrieval/config"

# ── UI ─────────────────────────────────────────────────────────────
APP_TITLE = "Crime Intelligence Copilot"
APP_SUBTITLE = "Semantic RAG‑powered investigation assistant"
APP_ICON = "🔍"

# ── Architecture Info ──────────────────────────────────────────────
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_DB = "Qdrant"
LLM_PROVIDER = "Groq"
LLM_MODEL = "Llama‑3.3‑70B Versatile"

# ── Defaults ───────────────────────────────────────────────────────
DEFAULT_TOP_K = 5
REQUEST_TIMEOUT = 60
STREAM_TIMEOUT = 120

# ── Theme Colours ──────────────────────────────────────────────────
COLOR_PRIMARY = "#1B3A5C"       # Police navy
COLOR_SECONDARY = "#2A5F9E"    # Badge blue
COLOR_ACCENT = "#4A90D9"       # Light badge
COLOR_SUCCESS = "#27AE60"
COLOR_WARNING = "#F39C12"
COLOR_DANGER = "#E74C3C"
COLOR_BG_CARD = "#F8F9FA"
COLOR_BG_DARK = "#0E1117"
COLOR_TEXT_MUTED = "#6C757D"
