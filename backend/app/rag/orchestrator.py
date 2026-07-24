"""
RAG Orchestrator.
Coordinates retrieval, prompt building, LLM execution, and response building.
"""

import time
import logging
import json
from typing import AsyncGenerator

from app.core.config import Settings
from app.retrieval.retrieval_engine import RetrievalEngine
from app.retrieval.schemas import RetrievalRequest
from app.llm.client import LLMClient
from app.llm.schemas import ChatRequest, ChatResponse, RetrievalMetrics, StreamEvent
from app.llm.prompt_builder import PromptBuilder
from app.rag.validator import QueryValidator
from app.rag.citation_builder import CitationBuilder
from app.rag.response_builder import ResponseBuilder
from app.services.tools.router import QueryRouter

logger = logging.getLogger(__name__)

class RAGOrchestrator:
    """Orchestrates the GraphRAG pipeline."""
    
    def __init__(self, engine: RetrievalEngine, llm_client: LLMClient, settings: Settings):
        self.engine = engine
        self.llm = llm_client
        self.settings = settings
        
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Run the full GraphRAG pipeline synchronously."""
        # 0. Try tool-calling route first
        try:
            router = QueryRouter(self.settings)
            tool_response = await router.route(request)
            if tool_response is not None:
                logger.info("Chat handled via tool-calling pipeline")
                return tool_response
        except Exception as e:
            logger.warning(f"Tool-calling route failed, falling back to RAG: {e}")

        # 1. Validate
        cleaned_query = QueryValidator.validate(request.query)
        
        # 2. Retrieve
        retrieval_req = RetrievalRequest(
            query=cleaned_query,
            filters=request.filters,
            top_k=request.top_k,
            max_results=self.settings.max_context_documents,
            include_context=True,
            include_explanation=False  # We don't need explanations for the LLM context
        )
        
        retrieval_resp = self.engine.query(retrieval_req)
        
        if not retrieval_resp.results:
            # Short-circuit if no evidence found
            return ResponseBuilder.build(
                query=cleaned_query,
                answer="No supporting evidence was found.",
                citations=[],
                sources=[],
                retrieval_metrics=RetrievalMetrics(
                    documents_used=0,
                    retrieval_time_ms=retrieval_resp.search_time_ms,
                    prompt_build_time_ms=0,
                    llm_time_ms=0,
                    model=self.settings.model_name
                )
            )
            
        # 3. Build Prompt
        p_start = time.time()
        doc_ids = [d.document_id for d in retrieval_resp.results]
        sys_prompt, user_prompt = PromptBuilder.build(
            query=cleaned_query,
            context=retrieval_resp.context,
            document_ids=doc_ids
        )
        p_time_ms = (time.time() - p_start) * 1000
        
        # 4. Generate LLM Response
        llm_start = time.time()
        llm_resp = await self.llm.generate(sys_prompt, user_prompt)
        llm_time_ms = (time.time() - llm_start) * 1000
        
        # 5. Build Citations & Response
        citations, sources = CitationBuilder.build(retrieval_resp.results, llm_resp.content)
        
        metrics = RetrievalMetrics(
            documents_used=len(retrieval_resp.results),
            retrieval_time_ms=retrieval_resp.search_time_ms,
            prompt_build_time_ms=round(p_time_ms, 2),
            llm_time_ms=round(llm_time_ms, 2),
            model=self.settings.model_name,
            prompt_tokens=llm_resp.prompt_tokens,
            completion_tokens=llm_resp.completion_tokens,
            total_tokens=llm_resp.total_tokens
        )
        
        return ResponseBuilder.build(
            query=cleaned_query,
            answer=llm_resp.content,
            citations=citations,
            sources=sources,
            retrieval_metrics=metrics
        )
        
    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Run the full GraphRAG pipeline and stream the LLM response (SSE format)."""
        # 0. Try tool-calling route first (non-streaming — send full result)
        try:
            router = QueryRouter(self.settings)
            tool_response = await router.route(request)
            if tool_response is not None:
                logger.info("Stream chat handled via tool-calling pipeline")
                yield json.dumps({'event': 'token', 'data': tool_response.answer})
                final_data = {
                    "event": "complete",
                    "citations": [c.model_dump() for c in tool_response.citations],
                    "sources": tool_response.sources,
                }
                yield json.dumps(final_data)
                yield "[DONE]"
                return
        except Exception as e:
            logger.warning(f"Tool-calling route failed in stream, falling back to RAG: {e}")

        # 1. Validate
        cleaned_query = QueryValidator.validate(request.query)
        
        # 2. Retrieve
        retrieval_req = RetrievalRequest(
            query=cleaned_query,
            filters=request.filters,
            top_k=request.top_k,
            max_results=self.settings.max_context_documents,
            include_context=True,
            include_explanation=False
        )
        
        retrieval_resp = self.engine.query(retrieval_req)
        
        if not retrieval_resp.results:
            # Yield early if no results
            no_results = "No supporting evidence was found."
            yield json.dumps({'event': 'token', 'data': no_results})
            yield "[DONE]"
            return
            
        # 3. Build Prompt
        doc_ids = [d.document_id for d in retrieval_resp.results]
        sys_prompt, user_prompt = PromptBuilder.build(
            query=cleaned_query,
            context=retrieval_resp.context,
            document_ids=doc_ids
        )
        
        # 4. Stream LLM Response
        full_answer = []
        async for chunk in self.llm.stream(sys_prompt, user_prompt):
            full_answer.append(chunk)
            yield json.dumps({'event': 'token', 'data': chunk})
            
        # 5. Send Citations and Metadata as final event
        answer_str = "".join(full_answer)
        citations, sources = CitationBuilder.build(retrieval_resp.results, answer_str)
        
        final_data = {
            "event": "complete",
            "citations": [c.model_dump() for c in citations],
            "sources": sources
        }
        
        yield json.dumps(final_data)
        yield "[DONE]"
