"""
API routes for the Chat interface (Hybrid Retrieval + Tool Planning).
"""

import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.config import Settings, get_settings
from app.llm.schemas import ChatRequest, ChatResponse
from app.services.tools.router import QueryRouter
from app.llm.exceptions import LLMError

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

def get_query_router(settings: Settings = Depends(get_settings)) -> QueryRouter:
    """Dependency injector for the Query Router."""
    return QueryRouter(settings)

@router.post("", response_model=ChatResponse)
async def chat_sync(
    request: ChatRequest,
    query_router: QueryRouter = Depends(get_query_router)
) -> ChatResponse:
    """Synchronous chat endpoint that returns a full response with citations."""
    try:
        response = await query_router.route(request)
        if not response:
            raise HTTPException(status_code=500, detail="Failed to generate a response.")
        return response
    except LLMError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

async def stream_generator(request: ChatRequest, query_router: QueryRouter) -> AsyncGenerator[str, None]:
    """Helper to stream the response."""
    response = await query_router.route(request)
    
    if not response:
        yield json.dumps({'event': 'token', 'data': "I'm sorry, I couldn't generate a response."})
        yield "[DONE]"
        return
        
    # Send the answer as a single token for now (could be split if needed)
    yield json.dumps({'event': 'token', 'data': response.answer})
    
    final_data = {
        "event": "complete",
        "citations": [c.model_dump() for c in response.citations],
        "sources": response.sources,
    }
    yield json.dumps(final_data)
    yield "[DONE]"

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    query_router: QueryRouter = Depends(get_query_router)
) -> EventSourceResponse:
    """Streaming chat endpoint using Server-Sent Events."""
    try:
        return EventSourceResponse(stream_generator(request, query_router))
    except LLMError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
