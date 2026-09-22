"""
Karnataka Police Crime Intelligence Copilot — Streamlit Frontend

Entry point.  Run with:
    cd frontend
    streamlit run app.py
"""

from __future__ import annotations

import sys
import os

# Ensure the frontend root is on sys.path so relative imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from components.sidebar import render_sidebar
from pages import Chat, Dashboard, About

# ── Page Config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crime Intelligence Copilot",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ─────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Typography ─────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Remove Streamlit branding ──────────────────────────── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ── Sidebar ────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FAFBFC 0%, #F0F2F5 100%);
        border-right: 1px solid #E0E0E0;
    }

    /* ── Chat input ─────────────────────────────────────────── */
    [data-testid="stChatInput"] textarea {
        border-radius: 12px !important;
        border: 2px solid #D0D8E0 !important;
        padding: 0.8rem 1rem !important;
        font-size: 0.92rem !important;
        transition: border-color 0.2s;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #2A5F9E !important;
        box-shadow: 0 0 0 3px rgba(42,95,158,0.12) !important;
    }

    /* ── Buttons ────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.82rem;
        transition: all 0.15s ease;
        border: 1px solid #D0D8E0;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }

    /* ── Expander ───────────────────────────────────────────── */
    .streamlit-expanderHeader {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #1B3A5C !important;
    }

    /* ── Metric cards ──────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: #F8F9FA;
        border: 1px solid #E8ECF0;
        border-radius: 10px;
        padding: 0.6rem 0.8rem;
    }

    /* ── Smooth scrolling ──────────────────────────────────── */
    .main .block-container {
        max-width: 900px;
        padding-top: 1rem;
    }

    /* ── Dividers ──────────────────────────────────────────── */
    hr {
        border: none;
        border-top: 1px solid #E8ECF0;
    }

    /* ── Spinner ────────────────────────────────────────────── */
    .stSpinner > div {
        color: #2A5F9E !important;
    }

    /* ── Chat bubbles ───────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
        border: 1px solid #E4E9EF;
        background: #F7F9FB;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #1B3A5C, #2A5F9E);
        border-color: transparent;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {
        color: white;
    }
    [data-testid="stChatMessage"] p { line-height: 1.55; font-size: 0.93rem; }
    [data-testid="stChatMessage"] h3 { font-size: 1.05rem; margin: 0.2rem 0 0.5rem; color: #1B3A5C; }

    /* ── ResponseRenderer cards ─────────────────────────────── */
    .ci-card {
        background: white; border: 1px solid #E0E6EC; border-radius: 12px;
        padding: 0.9rem 1.05rem; margin: 0.35rem 0 0.7rem;
        box-shadow: 0 1px 4px rgba(27,58,92,0.06);
    }
    .ci-card-header { display: flex; align-items: center; gap: 0.65rem; margin-bottom: 0.7rem; }
    .ci-card-icon { font-size: 1.35rem; line-height: 1; }
    .ci-card-title { margin: 0; font-size: 1rem; font-weight: 700; color: #1B3A5C; }
    .ci-subtitle { margin: 0.1rem 0 0; font-size: 0.75rem; color: #6C757D; }
    .ci-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 0.5rem;
    }
    .ci-field {
        display: flex; flex-direction: column; gap: 0.12rem;
        background: #F8F9FA; border: 1px solid #ECF0F4; border-radius: 8px; padding: 0.5rem 0.65rem;
    }
    .ci-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.35px; color: #6C757D; }
    .ci-value { font-size: 0.95rem; font-weight: 600; color: #1B3A5C; word-break: break-word; }
    .ci-row { margin-bottom: 0.5rem; }
    .ci-note {
        background: #FFF8E6; border: 1px solid #F3DFA5; color: #7A5A00; border-radius: 8px;
        padding: 0.5rem 0.7rem; font-size: 0.8rem; margin-bottom: 0.6rem;
    }
    .ci-badge {
        display: inline-block; font-size: 0.7rem; font-weight: 600; padding: 2px 10px; border-radius: 12px;
    }
    .ci-badge-success { background: #E6F4EA; color: #1E7B3A; }
    .ci-badge-warning { background: #FFF3CD; color: #8A6D00; }
    .ci-badge-info    { background: #E8F0FE; color: #2A5F9E; }
    .ci-table-wrap { overflow-x: auto; border: 1px solid #E4E9EF; border-radius: 8px; }
    .ci-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
    .ci-table th {
        text-align: left; background: #F0F4F8; color: #1B3A5C; font-weight: 600;
        padding: 0.5rem 0.7rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.3px;
        white-space: nowrap;
    }
    .ci-table td { padding: 0.45rem 0.7rem; border-top: 1px solid #EEF2F6; color: #2B2B2B; white-space: nowrap; }
    .ci-table tbody tr:hover { background: #F8FAFC; }
    @media (max-width: 640px) {
        .ci-card { padding: 0.7rem 0.75rem; }
        .ci-grid { grid-template-columns: 1fr 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

from api.client import BackendClient

# ── Health Check ───────────────────────────────────────────────────
@st.cache_data(ttl=5)
def check_backend_health():
    return BackendClient().health()

health_status = check_backend_health()

if not health_status.online:
    st.error(
        f"🚨 **Backend Service Unavailable**\n\n"
        f"The backend services are currently unreachable. Please ensure the backend is running.\n\n"
        f"**Error Details:** {health_status.error}"
    )
    if st.button("Retry Connection", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# ── Routing ────────────────────────────────────────────────────────
selected_page = render_sidebar()

if selected_page == "Chat":
    Chat.render()
elif selected_page == "Dashboard":
    Dashboard.render()
elif selected_page == "About":
    About.render()
else:
    Chat.render()
