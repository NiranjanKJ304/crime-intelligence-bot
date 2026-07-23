"""
API routes for the GraphRAG Chat interface.
"""

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.config import Settings, get_settings
from app.llm.schemas import ChatRequest, ChatResponse
from app.llm.client import LLMClient
from app.retrieval.retrieval_engine import RetrievalEngine
from app.rag.orchestrator import RAGOrchestrator
from app.llm.exceptions import LLMError

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

def get_orchestrator(settings: Settings = Depends(get_settings)) -> RAGOrchestrator:
    """Dependency injector for the RAG Orchestrator."""
    engine = RetrievalEngine(settings)
    llm_client = LLMClient(settings)
    return RAGOrchestrator(engine, llm_client, settings)

@router.post("", response_model=ChatResponse)
async def chat_sync(
    request: ChatRequest,
    orchestrator: RAGOrchestrator = Depends(get_orchestrator)
) -> ChatResponse:
    """Synchronous chat endpoint that returns a full response with citations."""
    try:
        return await orchestrator.chat(request)
    except LLMError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    orchestrator: RAGOrchestrator = Depends(get_orchestrator)
) -> EventSourceResponse:
    """Streaming chat endpoint using Server-Sent Events."""
    try:
        return EventSourceResponse(orchestrator.chat_stream(request))
    except LLMError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
