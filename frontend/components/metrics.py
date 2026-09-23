"""
Metrics panel component — shows RAG pipeline performance stats.

Styled by the .ci-metric* classes in app.py (dark surface, light text).
"""

from __future__ import annotations

import html

import streamlit as st

from api.client import RetrievalMetrics
from utils.helpers import fmt_ms, fmt_score, fmt_tokens


def render_metrics_panel(metrics: RetrievalMetrics, confidence: float) -> None:
    """Render the performance metrics panel below the AI response."""

    st.markdown('<p class="ci-section-title">📊 &nbsp;Pipeline Metrics</p>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _metric_card("Confidence", fmt_score(confidence), icon="🎯")
    with col2:
        _metric_card("Retrieval", fmt_ms(metrics.retrieval_time_ms), icon="⚡")
    with col3:
        _metric_card("LLM", fmt_ms(metrics.llm_time_ms), icon="🧠")
    with col4:
        _metric_card("Documents", str(metrics.documents_used), icon="📄")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        _metric_card("Prompt Build", fmt_ms(metrics.prompt_build_time_ms), icon="🛠️")
    with col6:
        _metric_card("Prompt Tokens", fmt_tokens(metrics.prompt_tokens), icon="📝")
    with col7:
        _metric_card("Completion Tokens", fmt_tokens(metrics.completion_tokens), icon="✍️")
    with col8:
        _metric_card("Total Tokens", fmt_tokens(metrics.total_tokens), icon="🔢")

    st.markdown(
        f'<p class="ci-muted">Model: <code>{html.escape(metrics.model or "—")}</code></p>',
        unsafe_allow_html=True,
    )


def _metric_card(label: str, value: str, icon: str = "") -> None:
    st.markdown(
        f"""
        <div class="ci-metric">
            <p class="ci-metric-label">{icon} {html.escape(label)}</p>
            <p class="ci-metric-value">{html.escape(value)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
