"""
Chat page — the primary interface for the Crime Intelligence Copilot.
"""

from __future__ import annotations

import streamlit as st

from api.client import BackendClient, ChatResult, parse_citations, parse_metrics
from components.chat_message import assistant_message, render_user_message
from components.citation_card import render_citation_cards
from components.metrics import render_metrics_panel
from components.response_renderer import render_response
from utils.constants import APP_ICON, APP_SUBTITLE, APP_TITLE


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
            <h1 class="ci-page-title" style="font-size:2rem; font-weight:800;">
                {APP_ICON}  {APP_TITLE}
            </h1>
            <p class="ci-page-subtitle" style="font-size:0.95rem;">
                {APP_SUBTITLE}
            </p>
        </div>
        <hr style="margin:0 0 1rem;">
        """,
        unsafe_allow_html=True,
    )

    # ── Chat history ───────────────────────────────────────────────
    for i, msg in enumerate(st.session_state["messages"]):
        if msg["role"] == "user":
            render_user_message(msg["content"])
            continue

        result = st.session_state["chat_results"][i] if i < len(st.session_state["chat_results"]) else None
        with assistant_message():
            render_response(result or ChatResult(answer=msg["content"]))
            if result and not result.error and (result.citations or result.retrieval):
                with st.expander("📎 Citations & Metrics", expanded=False):
                    render_citation_cards(result.citations)
                    if result.retrieval:
                        render_metrics_panel(result.retrieval, result.confidence)

    # ── Input ──────────────────────────────────────────────────────
    query = st.chat_input(placeholder="Ask about crime patterns, cases, suspects, or statistics…")

    if query:
        st.session_state["messages"].append({"role": "user", "content": query})
        st.session_state["chat_results"].append(None)  # placeholder
        render_user_message(query)

        history = _get_history()
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


def _store(result: ChatResult) -> None:
    content = f"Error: {result.error}" if result.error else result.answer
    st.session_state["messages"].append({"role": "assistant", "content": content})
    st.session_state["chat_results"].append(result)
    st.rerun()


def _handle_sync(client: BackendClient, query: str, history: list[dict] | None = None) -> None:
    """Send a synchronous chat request and display the full response."""
    with assistant_message():
        with st.spinner("Searching crime intelligence…"):
            result = client.chat(query, top_k=st.session_state["top_k"], history=history)
    _store(result)


def _handle_streaming(client: BackendClient, query: str, history: list[dict] | None = None) -> None:
    """Stream tokens from the backend, then swap in the structured rendering."""
    result = ChatResult(query=query)
    tokens: list[str] = []

    with assistant_message():
        placeholder = st.empty()
        placeholder.markdown("_Searching crime intelligence…_")

        for event in client.chat_stream(query, top_k=st.session_state["top_k"], history=history):
            evt_type = event.get("event", "")

            if evt_type == "token":
                tokens.append(event.get("data", ""))
                placeholder.markdown("".join(tokens))

            elif evt_type == "complete":
                result.response_type = event.get("response_type", "answer")
                result.data = event.get("data")
                result.citations = parse_citations(event.get("citations"))
                result.sources = event.get("sources", [])
                result.confidence = event.get("confidence", 0.0)
                result.retrieval = parse_metrics(event.get("retrieval"))

            elif evt_type == "error":
                result.error = event.get("data", "Unknown error")
                placeholder.error(f"🚨 **Backend Error:** {result.error}")

            elif evt_type == "done":
                break

    result.answer = "".join(tokens) if tokens else (result.error or "No response received.")
    _store(result)
