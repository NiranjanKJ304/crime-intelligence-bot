"""
API routes for the Chat interface (Hybrid Retrieval + Tool Planning).

SSE protocol (consumed by frontend/api/client.py):
    data: {"event": "token",    "data": "<text>"}
    data: {"event": "complete", "response_type": "...", "data": {...} | null,
           "citations": [...], "sources": [...], "confidence": float, "retrieval": {...}}
    data: {"event": "error",    "data": "<user-safe message>"}
    data: [DONE]
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.config import Settings, get_settings
from app.llm.exceptions import LLMError
from app.llm.schemas import ChatRequest, ChatResponse
from app.services.tools.exceptions import ToolError
from app.services.tools.router import QueryRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

GENERIC_ERROR = "The request could not be completed due to an internal error."
LLM_UNAVAILABLE = "The language model did not return a response. Please try again."


def get_query_router(settings: Settings = Depends(get_settings)) -> QueryRouter:
    """Dependency injector for the Query Router."""
    return QueryRouter(settings)


@router.post("", response_model=ChatResponse)
async def chat_sync(
    request: ChatRequest,
    query_router: QueryRouter = Depends(get_query_router),
) -> ChatResponse:
    """Synchronous chat endpoint that returns a full response with citations."""
    try:
        response = await query_router.route(request)
    except ToolError as exc:
        logger.exception("Tool-layer failure for query=%r", request.query[:80])
        raise HTTPException(status_code=500, detail=exc.user_message)
    except LLMError as exc:
        logger.exception("LLM failure for query=%r", request.query[:80])
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception:
        logger.exception("Unhandled failure for query=%r", request.query[:80])
        raise HTTPException(status_code=500, detail=GENERIC_ERROR)

    if not response:
        raise HTTPException(status_code=502, detail=LLM_UNAVAILABLE)
    return response


def _sse(payload: dict) -> str:
    return json.dumps(payload, default=str)


async def stream_generator(request: ChatRequest, query_router: QueryRouter) -> AsyncGenerator[str, None]:
    """Stream the response; any failure becomes a structured error event, never a dropped connection."""
    try:
        response = await query_router.route(request)
    except ToolError as exc:
        logger.exception("Tool-layer failure during stream for query=%r", request.query[:80])
        yield _sse({"event": "error", "data": exc.user_message})
        yield "[DONE]"
        return
    except LLMError as exc:
        logger.exception("LLM failure during stream for query=%r", request.query[:80])
        yield _sse({"event": "error", "data": str(exc)})
        yield "[DONE]"
        return
    except Exception:
        logger.exception("Unhandled failure during stream for query=%r", request.query[:80])
        yield _sse({"event": "error", "data": GENERIC_ERROR})
        yield "[DONE]"
        return

    if not response:
        yield _sse({"event": "error", "data": LLM_UNAVAILABLE})
        yield "[DONE]"
        return

    # The answer is produced in full by the deterministic/LLM pipeline; emit it as one token.
    yield _sse({"event": "token", "data": response.answer})
    yield _sse({
        "event": "complete",
        "response_type": response.response_type,
        "data": response.data,
        "citations": [c.model_dump() for c in response.citations],
        "sources": response.sources,
        "confidence": response.confidence,
        "retrieval": response.retrieval.model_dump(),
    })
    yield "[DONE]"


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    query_router: QueryRouter = Depends(get_query_router),
) -> EventSourceResponse:
    """Streaming chat endpoint using Server-Sent Events."""
    return EventSourceResponse(stream_generator(request, query_router))
