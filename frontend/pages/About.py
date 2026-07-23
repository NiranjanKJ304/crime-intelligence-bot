"""
About page — project architecture and system overview.
"""

from __future__ import annotations

import streamlit as st

from utils.constants import (
    APP_TITLE, APP_ICON, EMBEDDING_MODEL, VECTOR_DB,
    LLM_PROVIDER, LLM_MODEL, BACKEND_BASE_URL,
)


def render() -> None:
    """Render the About page."""

    st.markdown(
        f"""
        <div style="padding:0.8rem 0 0.4rem;">
            <h1 style="margin:0; font-size:1.6rem; font-weight:700; color:#1B3A5C;">
                {APP_ICON}  About
            </h1>
            <p style="margin:0.2rem 0 0; font-size:0.88rem; color:#6C757D;">
                Architecture, components, and technology stack
            </p>
        </div>
        <hr style="margin:0 0 1rem; border-color:#E8ECF0;">
        """,
        unsafe_allow_html=True,
    )

    # ── Project Overview ───────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#1B3A5C,#2A5F9E);
                    color:white; border-radius:14px; padding:1.5rem 1.8rem;
                    margin-bottom:1.2rem; box-shadow:0 4px 15px rgba(27,58,92,0.2);">
            <h2 style="margin:0 0 0.3rem; font-size:1.3rem; font-weight:700;">
                {APP_TITLE}
            </h2>
            <p style="margin:0; font-size:0.9rem; opacity:0.9; line-height:1.6;">
                A Semantic RAG‑powered investigation assistant built for the
                <strong>Karnataka State Police</strong>. The system ingests structured
                crime data, generates AI documents, embeds them into a vector database,
                and retrieves contextually relevant evidence in response to natural
                language queries from investigators.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Architecture ───────────────────────────────────────────────
    st.markdown("### 🏗️  System Architecture")

    st.markdown(
        """
        ```
        ┌───────────────────────────────────────────────────────┐
        │                   Streamlit Frontend                  │
        │            (Chat · Dashboard · About)                 │
        └────────────────────────┬──────────────────────────────┘
                                 │  REST API (HTTP)
                                 ▼
        ┌───────────────────────────────────────────────────────┐
        │                 FastAPI Backend                       │
        │  ┌─────────┐  ┌──────────┐  ┌──────────────────┐     │
        │  │  Chat    │  │ Retrieval│  │  RAG Orchestrator │     │
        │  │  Routes  │→ │  Engine  │→ │  Prompt → LLM    │     │
        │  └─────────┘  └────┬─────┘  └──────────────────┘     │
        │                    │                                  │
        │        ┌───────────┼───────────┐                     │
        │        ▼           ▼           ▼                     │
        │   ┌────────┐  ┌────────┐  ┌────────┐                │
        │   │ Qdrant │  │ Ranking│  │ Context│                │
        │   │ Search │  │ Engine │  │ Builder│                │
        │   └────────┘  └────────┘  └────────┘                │
        └───────────────────────────────────────────────────────┘
        ```
        """,
    )

    # ── Technology Stack ───────────────────────────────────────────
    st.markdown("### 🔧  Technology Stack")

    col1, col2 = st.columns(2)

    with col1:
        _info_card("Embedding Model", EMBEDDING_MODEL, "🧬",
                   "Sentence‑level embeddings for semantic similarity search.")
        _info_card("Vector Database", VECTOR_DB, "🗄️",
                   "High‑performance vector search engine with HNSW indexing.")
        _info_card("LLM Provider", LLM_PROVIDER, "☁️",
                   "Ultra‑fast inference for large language models via cloud API.")

    with col2:
        _info_card("LLM Model", LLM_MODEL, "🧠",
                   "70B‑parameter instruction‑tuned model for precise, grounded answers.")
        _info_card("Backend", f"FastAPI — {BACKEND_BASE_URL}", "⚡",
                   "Async Python web framework with automatic OpenAPI documentation.")
        _info_card("Frontend", "Streamlit", "🖥️",
                   "Rapid‑prototyping Python UI framework with reactive state management.")

    st.markdown("---")

    # ── Pipeline Phases ────────────────────────────────────────────
    st.markdown("### 📋  Completed Pipeline Phases")

    phases = [
        ("Phase 1", "Data Engineering", "ETL pipeline, data cleaning, PostgreSQL analytics tables.", "✅"),
        ("Phase 2", "Knowledge Layer", "AI document generation, Neo4j knowledge graph, embedding generation, Qdrant vector database.", "✅"),
        ("Phase 3", "Retrieval Engine", "Query processing, semantic search, ranking, explainability, context builder, APIs.", "✅"),
        ("Phase 4", "GraphRAG + LLM", "RAG orchestrator, prompt builder, Groq integration, citation builder, chat & streaming APIs.", "✅"),
        ("Phase 5", "Frontend", "Streamlit UI, chat interface, dashboard, API client.", "✅"),
    ]

    for phase, title, desc, status in phases:
        st.markdown(
            f"""
            <div style="background:#F8F9FA; border:1px solid #E8ECF0; border-radius:10px;
                        padding:0.6rem 1rem; margin-bottom:0.5rem; display:flex;
                        align-items:center; gap:0.8rem;">
                <span style="font-size:1.2rem;">{status}</span>
                <div>
                    <p style="margin:0; font-weight:700; font-size:0.88rem; color:#1B3A5C;">
                        {phase}: {title}
                    </p>
                    <p style="margin:0; font-size:0.78rem; color:#6C757D;">{desc}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Footer ─────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center; padding:1rem 0; color:#9E9E9E; font-size:0.75rem;">
            Built for Karnataka State Police &nbsp;•&nbsp; Crime Intelligence Division<br>
            Powered by Semantic RAG &nbsp;|&nbsp; Qdrant &nbsp;|&nbsp; Groq &nbsp;|&nbsp; Llama 3.3
        </div>
        """,
        unsafe_allow_html=True,
    )


def _info_card(label: str, value: str, icon: str, description: str) -> None:
    st.markdown(
        f"""
        <div style="background:white; border:1px solid #E0E0E0; border-radius:10px;
                    padding:0.75rem 0.9rem; margin-bottom:0.6rem;
                    box-shadow:0 1px 4px rgba(0,0,0,0.04);">
            <p style="margin:0; font-size:0.72rem; color:#6C757D; text-transform:uppercase;
                      letter-spacing:0.3px;">
                {icon} &nbsp;{label}
            </p>
            <p style="margin:0.15rem 0 0.15rem; font-size:0.95rem; font-weight:700;
                      color:#1B3A5C;">{value}</p>
            <p style="margin:0; font-size:0.75rem; color:#888; line-height:1.4;">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
