"""
Sidebar component for the Streamlit application.
"""

from __future__ import annotations

import streamlit as st
from streamlit_option_menu import option_menu

from api.client import BackendClient
from utils.constants import APP_TITLE, APP_ICON, BACKEND_BASE_URL, DEFAULT_TOP_K
from utils.helpers import now_str


def render_sidebar() -> str:
    """Render the sidebar and return the selected page name."""

    with st.sidebar:
        # ── Logo / Brand ───────────────────────────────────────────
        st.markdown(
            f"""
            <div style="text-align:center; padding: 0.5rem 0 0.8rem;">
                <span style="font-size:2.8rem;">{APP_ICON}</span>
                <h2 class="ci-page-title" style="font-size:1.3rem;">{APP_TITLE}</h2>
                <p style="margin:0; font-size:0.78rem; color:#9FB0C3;
                          letter-spacing:0.3px;">
                    Karnataka Police &nbsp;•&nbsp; AI Investigation Unit
                </p>
            </div>
            <hr style="margin:0 0 0.6rem;">
            """,
            unsafe_allow_html=True,
        )

        # ── Navigation ────────────────────────────────────────────
        selected = option_menu(
            menu_title=None,
            options=["Chat", "Dashboard", "About"],
            icons=["chat-dots-fill", "bar-chart-line-fill", "info-circle-fill"],
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#7CB3F1", "font-size": "1rem"},
                "nav-link": {
                    "font-size": "0.9rem",
                    "text-align": "left",
                    "margin": "2px 0",
                    "padding": "0.55rem 0.8rem",
                    "border-radius": "8px",
                    "--hover-color": "#1C2430", "color": "#E6EDF3",
                },
                "nav-link-selected": {
                    "background-color": "#1B3A5C",
                    "color": "white",
                    "font-weight": "600",
                },
            },
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Backend Status ─────────────────────────────────────────
        client = BackendClient()
        health = client.health()

        if health.online:
            status_dot = "🟢"
            status_text = "Online"
        else:
            status_dot = "🔴"
            status_text = "Offline"

        st.markdown(
            f"""
            <div class="ci-panel">
                <p style="margin:0 0 0.3rem; font-weight:600; font-size:0.8rem;
                          color:#9FB0C3; text-transform:uppercase; letter-spacing:0.5px;">
                    System Status
                </p>
                <p style="margin:0; font-size:0.82rem;">
                    {status_dot} &nbsp;Backend: <strong>{status_text}</strong>
                </p>
                <p style="margin:0; font-size:0.75rem; color:#9FB0C3;">
                    {BACKEND_BASE_URL}
                </p>
                <p style="margin:0; font-size:0.75rem; color:#9FB0C3;">
                    Model: <code>{health.embedding_model or '—'}</code>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Settings ───────────────────────────────────────────────
        with st.expander("⚙️  Settings", expanded=False):
            st.session_state.setdefault("top_k", DEFAULT_TOP_K)
            st.session_state["top_k"] = st.slider(
                "Retrieved documents (top_k)",
                min_value=1, max_value=20,
                value=st.session_state["top_k"],
                help="Number of documents to retrieve from Qdrant.",
            )

            st.session_state.setdefault("streaming", True)
            st.session_state["streaming"] = st.toggle(
                "Streaming mode", value=st.session_state["streaming"],
                help="Stream response tokens in real time.",
            )

        # ── Actions ────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state["messages"] = []
                st.rerun()
        with col2:
            if st.button("➕ New Chat", use_container_width=True):
                st.session_state["messages"] = []
                st.session_state["chat_results"] = []
                st.rerun()

        # ── Footer ─────────────────────────────────────────────────
        st.markdown(
            f"""
            <hr style="margin:1rem 0 0.5rem;">
            <p style="text-align:center; font-size:0.7rem; color:#9FB0C3;">
                {now_str()}<br>
                Crime Intelligence Platform v1.0
            </p>
            """,
            unsafe_allow_html=True,
        )

    return selected
