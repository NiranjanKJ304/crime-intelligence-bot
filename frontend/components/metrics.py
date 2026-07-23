"""
Metrics panel component — shows RAG pipeline performance stats.
"""

from __future__ import annotations

import streamlit as st

from api.client import RetrievalMetrics
from utils.helpers import fmt_ms, fmt_score, fmt_tokens


def render_metrics_panel(metrics: RetrievalMetrics, confidence: float) -> None:
    """Render the performance metrics panel below the AI response."""

    st.markdown(
        """
        <p style="font-weight:600; font-size:0.85rem; color:#1B3A5C;
                  margin:0.8rem 0 0.4rem; text-transform:uppercase;
                  letter-spacing:0.4px;">
            📊 &nbsp;Pipeline Metrics
        </p>
        """,
        unsafe_allow_html=True,
    )

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

    # Model badge
    st.markdown(
        f"""
        <p style="font-size:0.75rem; color:#6C757D; margin-top:0.3rem;">
            Model: <code>{metrics.model}</code>
        </p>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(label: str, value: str, icon: str = "") -> None:
    st.markdown(
        f"""
        <div style="background:#F8F9FA; border:1px solid #E8ECF0; border-radius:8px;
                    padding:0.5rem 0.6rem; text-align:center;">
            <p style="margin:0; font-size:0.7rem; color:#6C757D; text-transform:uppercase;
                      letter-spacing:0.3px;">
                {icon} {label}
            </p>
            <p style="margin:0; font-size:1.05rem; font-weight:700; color:#1B3A5C;">
                {value}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
