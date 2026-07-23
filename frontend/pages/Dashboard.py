"""
Dashboard page — backend health, model info, and usage analytics.
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

from api.client import BackendClient
from utils.constants import APP_ICON
from utils.helpers import fmt_ms


def render() -> None:
    """Render the Dashboard page."""

    st.markdown(
        f"""
        <div style="padding:0.8rem 0 0.4rem;">
            <h1 style="margin:0; font-size:1.6rem; font-weight:700; color:#1B3A5C;">
                {APP_ICON}  System Dashboard
            </h1>
            <p style="margin:0.2rem 0 0; font-size:0.88rem; color:#6C757D;">
                Real-time backend health, model status, and retrieval analytics
            </p>
        </div>
        <hr style="margin:0 0 1rem; border-color:#E8ECF0;">
        """,
        unsafe_allow_html=True,
    )

    client = BackendClient()

    # ── Health ─────────────────────────────────────────────────────
    health = client.health()

    st.markdown("### 🩺 Backend Health")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        _status_card(
            "Backend",
            "Online" if health.online else "Offline",
            "🟢" if health.online else "🔴",
        )
    with c2:
        _status_card("Qdrant", health.qdrant.capitalize(), "🟢" if health.qdrant == "healthy" else "🟡")
    with c3:
        _status_card("Neo4j", health.neo4j.capitalize(), "🟢" if health.neo4j == "healthy" else "🟡")
    with c4:
        _status_card("Version", health.version or "—", "📦")

    if health.error:
        st.warning(f"⚠️  {health.error}")

    st.markdown("---")

    # ── Configuration ──────────────────────────────────────────────
    st.markdown("### ⚙️ Retrieval Configuration")
    config = client.config()
    if config:
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            st.metric("Top K", config.get("top_k", "—"))
        with cc2:
            st.metric("Score Threshold", config.get("default_score_threshold", "—"))
        with cc3:
            st.metric("Max Context Tokens", config.get("max_context_tokens", "—"))

        st.markdown(
            f"""
            <p style="font-size:0.8rem; color:#6C757D; margin-top:0.3rem;">
                Embedding Model: <code>{config.get('embedding_model', '—')}</code>
            </p>
            """,
            unsafe_allow_html=True,
        )

        # Ranking weights
        weights = config.get("ranking_weights", {})
        if weights:
            with st.expander("Ranking Weights", expanded=False):
                for k, v in weights.items():
                    st.markdown(f"- **{k}**: `{v}`")
    else:
        st.info("Backend offline — configuration unavailable.")

    st.markdown("---")

    # ── Analytics ──────────────────────────────────────────────────
    st.markdown("### 📈 Retrieval Analytics")
    stats = client.statistics()

    if stats:
        perf = stats.get("performance", {})
        cache = stats.get("cache_stats", {})
        types = stats.get("document_type_distribution", {})

        p1, p2, p3, p4 = st.columns(4)
        with p1:
            st.metric("Total Queries", stats.get("total_queries", 0))
        with p2:
            st.metric("Avg Response", fmt_ms(perf.get("avg_search_time_ms")))
        with p3:
            st.metric("Cache Hits", cache.get("hits", 0))
        with p4:
            st.metric("Cache Misses", cache.get("misses", 0))

        # Document type distribution chart
        if types:
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=list(types.keys()),
                        y=list(types.values()),
                        marker_color="#2A5F9E",
                        marker_line_width=0,
                    )
                ]
            )
            fig.update_layout(
                title=dict(text="Document Type Distribution", font=dict(size=14, color="#1B3A5C")),
                xaxis_title="Type",
                yaxis_title="Count",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(l=40, r=20, t=50, b=40),
                font=dict(size=11),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Similarity histogram
        sim = perf.get("similarity_histogram")
        if sim and isinstance(sim, dict):
            fig2 = go.Figure(
                data=[
                    go.Bar(
                        x=list(sim.keys()),
                        y=list(sim.values()),
                        marker_color="#27AE60",
                    )
                ]
            )
            fig2.update_layout(
                title=dict(text="Top Similarity Score Distribution", font=dict(size=14, color="#1B3A5C")),
                xaxis_title="Score Bucket",
                yaxis_title="Queries",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=280,
                margin=dict(l=40, r=20, t=50, b=40),
                font=dict(size=11),
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No analytics data available yet. Send some queries first!")


def _status_card(label: str, value: str, icon: str) -> None:
    st.markdown(
        f"""
        <div style="background:#F8F9FA; border:1px solid #E8ECF0; border-radius:10px;
                    padding:0.65rem 0.8rem; text-align:center;">
            <p style="margin:0; font-size:1.3rem;">{icon}</p>
            <p style="margin:0; font-size:0.72rem; color:#6C757D; text-transform:uppercase;
                      letter-spacing:0.3px;">{label}</p>
            <p style="margin:0; font-size:0.95rem; font-weight:700; color:#1B3A5C;">{value}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
