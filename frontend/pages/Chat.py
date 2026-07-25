"""
Chat page — the primary interface for the Crime Intelligence Copilot.
"""

from __future__ import annotations

import streamlit as st

from api.client import BackendClient, ChatResult, Citation
from components.chat_message import render_user_message, render_assistant_message, render_error_message
from components.citation_card import render_citation_cards
from components.metrics import render_metrics_panel
from utils.constants import APP_TITLE, APP_SUBTITLE, APP_ICON


def render() -> None:
    """Render the Chat page."""

    # ── Initialise session state ───────────────────────────────────
    st.session_state.setdefault("messages", [])        # list[dict]
    st.session_state.setdefault("chat_results", [])    # parallel list[ChatResult | None]
    st.session_state.setdefault("top_k", 5)
    st.session_state.setdefault("streaming", True)

    client = BackendClient()

    # ── Header ─────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="text-align:center; padding:1.2rem 0 0.6rem;">
            <h1 style="margin:0; font-size:2rem; font-weight:800; color:#1B3A5C;
                       letter-spacing:-0.5px;">
                {APP_ICON}  {APP_TITLE}
            </h1>
            <p style="margin:0.2rem 0 0; font-size:0.95rem; color:#6C757D;">
                {APP_SUBTITLE}
            </p>
        </div>
        <hr style="margin:0 0 1rem; border-color:#E8ECF0;">
        """,
        unsafe_allow_html=True,
    )

    # ── Chat history ───────────────────────────────────────────────
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state["messages"]):
            if msg["role"] == "user":
                render_user_message(msg["content"])
            else:
                render_assistant_message(msg["content"])

                # Show citations + metrics if available
                if i < len(st.session_state["chat_results"]):
                    result = st.session_state["chat_results"][i]
                    if result and not result.error:
                        with st.expander("📎 Citations & Metrics", expanded=False):
                            render_citation_cards(result.citations)
                            if result.retrieval:
                                render_metrics_panel(result.retrieval, result.confidence)

    # ── Input ──────────────────────────────────────────────────────
    query = st.chat_input(
        placeholder="Ask about crime patterns, cases, suspects, or statistics…",
    )

    if query:
        # Append user message
        st.session_state["messages"].append({"role": "user", "content": query})
        st.session_state["chat_results"].append(None)  # placeholder

        # Build conversation history for the backend (exclude the current query)
        history = _get_history()

        # Decide sync vs streaming
        if st.session_state.get("streaming", True):
            _handle_streaming(client, query, history)
        else:
            _handle_sync(client, query, history)


def _get_history() -> list[dict[str, str]]:
    """Extract conversation history from session state for the backend."""
    history = []
    for msg in st.session_state["messages"][:-1]:  # Exclude the just-appended user message
        if msg["role"] in ("user", "assistant") and msg.get("content"):
            history.append({"role": msg["role"], "content": msg["content"]})
    return history[-6:]  # Last 3 turns


def _handle_sync(client: BackendClient, query: str, history: list[dict] | None = None) -> None:
    """Send a synchronous chat request and display the full response."""
    with st.spinner("🔍  Searching crime intelligence…"):
        result = client.chat(query, top_k=st.session_state["top_k"], history=history)

    if result.error:
        st.error(f"🚨 **Backend Error:** {result.error}")
        st.session_state["messages"].append({"role": "assistant", "content": f"Error: {result.error}"})
        st.session_state["chat_results"].append(result)
    else:
        st.session_state["messages"].append({"role": "assistant", "content": result.answer})
        st.session_state["chat_results"].append(result)

    st.rerun()


def _handle_streaming(client: BackendClient, query: str, history: list[dict] | None = None) -> None:
    """Stream tokens from the backend and display them incrementally."""

    # Placeholder for the streaming response
    with st.spinner("🔍  Searching crime intelligence…"):
        tokens: list[str] = []
        citations: list[Citation] = []
        sources: list[str] = []
        error: str | None = None

        response_placeholder = st.empty()

        for event in client.chat_stream(query, top_k=st.session_state["top_k"], history=history):
            evt_type = event.get("event", "")

            if evt_type == "token":
                tokens.append(event.get("data", ""))
                # Update the placeholder with accumulated text
                response_placeholder.markdown("".join(tokens))

            elif evt_type == "complete":
                for c in event.get("citations", []):
                    citations.append(
                        Citation(
                            document_id=c.get("document_id", ""),
                            document_type=c.get("document_type", ""),
                            score=c.get("score", 0.0),
                            text_snippet=c.get("text_snippet"),
                        )
                    )
                sources = event.get("sources", [])

            elif evt_type == "error":
                error = event.get("data", "Unknown error")
                st.error(f"🚨 **Streaming Error:** {error}")

            elif evt_type == "done":
                break
                
        if error and not tokens:
            response_placeholder.error(f"🚨 **Connection Error:** {error}")

    answer = "".join(tokens) if tokens else (error or "No response received.")

    # Build a lightweight ChatResult for history
    result = ChatResult(
        query=query,
        answer=answer,
        citations=citations,
        sources=sources,
        error=error,
    )

    st.session_state["messages"].append({"role": "assistant", "content": answer})
    st.session_state["chat_results"].append(result)
    st.rerun()
