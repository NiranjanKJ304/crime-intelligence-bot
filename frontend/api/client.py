"""
REST API client for the Crime Intelligence Backend.

All backend communication is centralised here.
No direct database, Qdrant, or LLM access — only HTTP calls.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Generator

import httpx

from utils.constants import (
    API_CHAT,
    API_CHAT_STREAM,
    API_HEALTH,
    API_RETRIEVAL_HEALTH,
    API_RETRIEVAL_STATS,
    API_RETRIEVAL_CONFIG,
    REQUEST_TIMEOUT,
    STREAM_TIMEOUT,
)

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────
@dataclass
class Citation:
    document_id: str = ""
    document_type: str = ""
    score: float = 0.0
    text_snippet: str | None = None


@dataclass
class RetrievalMetrics:
    documents_used: int = 0
    retrieval_time_ms: float = 0.0
    prompt_build_time_ms: float = 0.0
    llm_time_ms: float = 0.0
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResult:
    query: str = ""
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    retrieval: RetrievalMetrics | None = None
    error: str | None = None


@dataclass
class StreamResult:
    """Accumulated result while streaming tokens."""
    tokens: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def answer(self) -> str:
        return "".join(self.tokens)


@dataclass
class HealthResult:
    online: bool = False
    status: str = "unknown"
    version: str = ""
    qdrant: str = "unknown"
    neo4j: str = "unknown"
    embedding_model: str = ""
    error: str | None = None


# ── Client ─────────────────────────────────────────────────────────
class BackendClient:
    """Thin wrapper around httpx for the FastAPI backend."""

    def __init__(self, timeout: float = REQUEST_TIMEOUT):
        self._timeout = timeout

    # ── Chat (synchronous response) ────────────────────────────────
    def chat(self, query: str, top_k: int = 5, filters: dict | None = None) -> ChatResult:
        """POST /api/v1/chat — full response in one shot."""
        payload: dict[str, Any] = {"query": query, "top_k": top_k, "stream": False}
        if filters:
            payload["filters"] = filters

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(API_CHAT, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError:
            return ChatResult(query=query, error="Backend is offline. Please start the server.")
        except httpx.TimeoutException:
            return ChatResult(query=query, error="Request timed out. Try a shorter query.")
        except httpx.HTTPStatusError as exc:
            return ChatResult(query=query, error=f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:
            return ChatResult(query=query, error=str(exc))

        citations = [
            Citation(
                document_id=c.get("document_id", ""),
                document_type=c.get("document_type", ""),
                score=c.get("score", 0.0),
                text_snippet=c.get("text_snippet"),
            )
            for c in data.get("citations", [])
        ]

        ret = data.get("retrieval", {})
        metrics = RetrievalMetrics(
            documents_used=ret.get("documents_used", 0),
            retrieval_time_ms=ret.get("retrieval_time_ms", 0),
            prompt_build_time_ms=ret.get("prompt_build_time_ms", 0),
            llm_time_ms=ret.get("llm_time_ms", 0),
            model=ret.get("model", ""),
            prompt_tokens=ret.get("prompt_tokens", 0),
            completion_tokens=ret.get("completion_tokens", 0),
            total_tokens=ret.get("total_tokens", 0),
        )

        return ChatResult(
            query=data.get("query", query),
            answer=data.get("answer", ""),
            citations=citations,
            sources=data.get("sources", []),
            confidence=data.get("confidence", 0.0),
            retrieval=metrics,
        )

    # ── Chat (streaming) ──────────────────────────────────────────
    def chat_stream(self, query: str, top_k: int = 5, filters: dict | None = None) -> Generator[dict, None, None]:
        """POST /api/v1/chat/stream — yields SSE events as dicts.

        Each yielded dict has:
            {"event": "token", "data": "..."}
            {"event": "complete", "citations": [...], "sources": [...]}
            {"event": "done"}
            {"event": "error", "data": "..."}
        """
        payload: dict[str, Any] = {"query": query, "top_k": top_k, "stream": True}
        if filters:
            payload["filters"] = filters

        try:
            with httpx.Client(timeout=STREAM_TIMEOUT) as client:
                with client.stream("POST", API_CHAT_STREAM, json=payload) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        # Lines come as  "data: {json}" or "data: [DONE]"
                        if line.startswith("data: "):
                            payload_str = line[6:]
                            if payload_str == "[DONE]":
                                yield {"event": "done"}
                                return
                            try:
                                event = json.loads(payload_str)
                                yield event
                            except json.JSONDecodeError:
                                continue
        except httpx.ConnectError:
            yield {"event": "error", "data": "Backend is offline."}
        except httpx.TimeoutException:
            yield {"event": "error", "data": "Streaming request timed out."}
        except Exception as exc:
            yield {"event": "error", "data": str(exc)}

    # ── Health ─────────────────────────────────────────────────────
    def health(self) -> HealthResult:
        """GET /health + GET /api/v1/retrieval/health."""
        result = HealthResult()
        try:
            with httpx.Client(timeout=5) as client:
                # Root health
                r = client.get(API_HEALTH)
                r.raise_for_status()
                data = r.json()
                result.online = True
                result.status = data.get("status", "healthy")
                result.version = data.get("version", "")

                # Retrieval subsystem health
                try:
                    r2 = client.get(API_RETRIEVAL_HEALTH)
                    r2.raise_for_status()
                    rdata = r2.json()
                    result.qdrant = rdata.get("qdrant", "unknown")
                    result.neo4j = rdata.get("neo4j", "unknown")
                    result.embedding_model = rdata.get("embedding_model", "")
                except Exception:
                    pass  # non‑critical
        except httpx.ConnectError:
            result.error = "Backend is offline."
        except Exception as exc:
            result.error = str(exc)
        return result

    # ── Statistics ─────────────────────────────────────────────────
    def statistics(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(API_RETRIEVAL_STATS)
                r.raise_for_status()
                return r.json()
        except Exception:
            return {}

    # ── Config ─────────────────────────────────────────────────────
    def config(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(API_RETRIEVAL_CONFIG)
                r.raise_for_status()
                return r.json()
        except Exception:
            return {}
