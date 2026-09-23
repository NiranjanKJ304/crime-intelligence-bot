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
    /* ══════════════════════════════════════════════════════════════
       Dark theme (pinned in .streamlit/config.toml). Every rule below
       sets BOTH background and text colour so nothing depends on the
       theme default. Palette: utils/constants.py
       page #0E1117 · surface #161B22 · surface-alt #1C2430 · border #2A3441
       text #E6EDF3 · muted #9FB0C3 · accent #4A90D9 / #7CB3F1 · navy #1B3A5C
       ══════════════════════════════════════════════════════════════ */

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
        background: linear-gradient(180deg, #11161D 0%, #0E1117 100%);
        border-right: 1px solid #2A3441;
    }

    /* ── Chat input ─────────────────────────────────────────── */
    [data-testid="stChatInput"] textarea {
        border-radius: 12px !important;
        border: 2px solid #2A3441 !important;
        padding: 0.8rem 1rem !important;
        font-size: 0.92rem !important;
        color: #E6EDF3 !important;
        transition: border-color 0.2s;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #4A90D9 !important;
        box-shadow: 0 0 0 3px rgba(74,144,217,0.2) !important;
    }

    /* ── Buttons ────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.82rem;
        transition: all 0.15s ease;
        border: 1px solid #2A3441;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.35);
        border-color: #4A90D9;
    }

    /* ── Expander (Citations & Metrics) ─────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid #2A3441 !important;
        border-radius: 10px !important;
        background: #11161D;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    .streamlit-expanderHeader {
        color: #E6EDF3 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] summary:hover { color: #7CB3F1 !important; }
    [data-testid="stExpander"] svg { fill: #E6EDF3; color: #E6EDF3; }

    /* ── Metric cards ──────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: #161B22;
        border: 1px solid #2A3441;
        border-radius: 10px;
        padding: 0.6rem 0.8rem;
    }
    [data-testid="stMetric"] label, [data-testid="stMetricLabel"] { color: #9FB0C3 !important; }
    [data-testid="stMetricValue"] { color: #E6EDF3 !important; }

    /* ── Layout ────────────────────────────────────────────── */
    .main .block-container {
        max-width: 900px;
        padding-top: 1rem;
    }
    hr { border: none; border-top: 1px solid #2A3441; }
    .stSpinner > div { color: #7CB3F1 !important; }

    /* ── Chat bubbles ───────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
        border: 1px solid #2A3441;
        background: #161B22;
        color: #E6EDF3;
    }
    /* Everything rendered inside a bubble inherits the bubble's text colour
       unless a component sets its own (cards below do). */
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] span,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] strong,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] em,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] td,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] th,
    [data-testid="stChatMessage"] .stMarkdown p,
    [data-testid="stChatMessage"] .stMarkdown li {
        color: #E6EDF3;
    }
    [data-testid="stChatMessage"] p { line-height: 1.55; font-size: 0.93rem; }
    [data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2,
    [data-testid="stChatMessage"] h3, [data-testid="stChatMessage"] h4 {
        color: #F3F6FA; margin: 0.2rem 0 0.5rem;
    }
    [data-testid="stChatMessage"] h3 { font-size: 1.05rem; }
    [data-testid="stChatMessage"] a { color: #7CB3F1; text-decoration: underline; }
    [data-testid="stChatMessage"] code {
        background: #0E1117; color: #E6EDF3; border: 1px solid #2A3441;
        border-radius: 4px; padding: 0.1rem 0.35rem; font-size: 0.85em;
    }
    [data-testid="stChatMessage"] pre {
        background: #0E1117; border: 1px solid #2A3441; border-radius: 8px;
        padding: 0.75rem 0.9rem; overflow-x: auto;
    }
    [data-testid="stChatMessage"] pre code { background: transparent; border: none; padding: 0; }
    [data-testid="stChatMessage"] blockquote { border-left: 3px solid #4A90D9; color: #CBD5E1; }
    /* Markdown tables rendered inside a bubble */
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] table {
        border-collapse: collapse; width: 100%; display: block; overflow-x: auto;
    }
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] th {
        background: #1B3A5C; color: #E6EDF3; padding: 0.45rem 0.7rem; border: 1px solid #2A3441;
    }
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] td {
        padding: 0.4rem 0.7rem; border: 1px solid #2A3441; color: #DCE4EE;
    }
    /* Native dataframes inside a bubble */
    [data-testid="stChatMessage"] [data-testid="stDataFrame"] { border: 1px solid #2A3441; border-radius: 8px; }

    /* User bubble: navy gradient, white text (marker span emitted by chat_message.py) */
    [data-testid="stChatMessage"]:has(.ci-user-marker) {
        background: linear-gradient(135deg, #1B3A5C, #2A5F9E);
        border-color: transparent;
    }
    [data-testid="stChatMessage"]:has(.ci-user-marker) [data-testid="stMarkdownContainer"] p,
    [data-testid="stChatMessage"]:has(.ci-user-marker) [data-testid="stMarkdownContainer"] li,
    [data-testid="stChatMessage"]:has(.ci-user-marker) [data-testid="stMarkdownContainer"] span,
    [data-testid="stChatMessage"]:has(.ci-user-marker) [data-testid="stMarkdownContainer"] strong {
        color: #FFFFFF;
    }
    .ci-user-marker { display: none; }

    /* ── ResponseRenderer cards (dark surface, light text) ─── */
    .ci-card {
        background: #1C2430; color: #E6EDF3; border: 1px solid #2A3441; border-radius: 12px;
        padding: 0.9rem 1.05rem; margin: 0.35rem 0 0.7rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.35);
    }
    .ci-card-header { display: flex; align-items: center; gap: 0.65rem; margin-bottom: 0.7rem; }
    .ci-card-icon { font-size: 1.35rem; line-height: 1; }
    .ci-card-title { margin: 0; font-size: 1rem; font-weight: 700; color: #F3F6FA; }
    .ci-subtitle { margin: 0.1rem 0 0; font-size: 0.75rem; color: #9FB0C3; }
    .ci-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 0.5rem;
    }
    .ci-field {
        display: flex; flex-direction: column; gap: 0.12rem;
        background: #161B22; border: 1px solid #2A3441; border-radius: 8px; padding: 0.5rem 0.65rem;
    }
    .ci-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.35px; color: #9FB0C3; }
    .ci-value { font-size: 0.95rem; font-weight: 600; color: #E6EDF3; word-break: break-word; }
    .ci-row { margin-bottom: 0.5rem; }
    .ci-note {
        background: #2B2410; border: 1px solid #6B5A1E; color: #F5D76E; border-radius: 8px;
        padding: 0.5rem 0.7rem; font-size: 0.8rem; margin-bottom: 0.6rem;
    }
    .ci-badge {
        display: inline-block; font-size: 0.7rem; font-weight: 600; padding: 2px 10px; border-radius: 12px;
    }
    .ci-badge-success { background: #123B22; color: #6EE7A0; }
    .ci-badge-warning { background: #3A2C0A; color: #F5D76E; }
    .ci-badge-info    { background: #1B3A5C; color: #BFDBFE; }
    .ci-table-wrap { overflow-x: auto; border: 1px solid #2A3441; border-radius: 8px; }
    .ci-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
    .ci-table th {
        text-align: left; background: #1B3A5C; color: #E6EDF3; font-weight: 600;
        padding: 0.5rem 0.7rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.3px;
        white-space: nowrap;
    }
    .ci-table td { padding: 0.45rem 0.7rem; border-top: 1px solid #2A3441; color: #DCE4EE; white-space: nowrap; background: #161B22; }
    .ci-table tbody tr:hover td { background: #1F2937; }

    /* ── Citation / metric cards (components/) ─────────────── */
    .ci-section-title {
        font-weight: 600; font-size: 0.85rem; color: #E6EDF3; margin: 0.8rem 0 0.4rem;
        text-transform: uppercase; letter-spacing: 0.4px;
    }
    .ci-cite {
        background: #1C2430; color: #E6EDF3; border: 1px solid #2A3441; border-radius: 10px;
        padding: 0.7rem 0.85rem; margin-bottom: 0.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    }
    .ci-cite-head { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; }
    .ci-cite-id { font-size: 0.73rem; color: #7CB3F1; font-weight: 600; word-break: break-all; }
    .ci-cite-badge { color: #FFFFFF; font-size: 0.65rem; padding: 2px 8px; border-radius: 12px; font-weight: 500; white-space: nowrap; }
    .ci-cite-snippet { margin: 0 0 0.3rem; font-size: 0.78rem; color: #CBD5E1; line-height: 1.45; }
    .ci-cite-score { margin: 0; font-size: 0.72rem; color: #7CB3F1; font-weight: 600; }
    .ci-metric {
        background: #1C2430; border: 1px solid #2A3441; border-radius: 8px;
        padding: 0.5rem 0.6rem; text-align: center;
    }
    .ci-metric-label { margin: 0; font-size: 0.7rem; color: #9FB0C3; text-transform: uppercase; letter-spacing: 0.3px; }
    .ci-metric-value { margin: 0; font-size: 1.05rem; font-weight: 700; color: #E6EDF3; }
    .ci-muted { font-size: 0.75rem; color: #9FB0C3; margin-top: 0.3rem; }
    .ci-muted code { background: #0E1117; color: #7CB3F1; border: 1px solid #2A3441; border-radius: 4px; padding: 0.05rem 0.3rem; }

    /* ── Page headers / status cards (pages/, sidebar) ─────── */
    .ci-page-title { margin: 0; font-weight: 700; color: #F3F6FA; letter-spacing: -0.5px; }
    .ci-page-subtitle { margin: 0.2rem 0 0; color: #9FB0C3; }
    .ci-status-card {
        background: #161B22; color: #E6EDF3; border: 1px solid #2A3441; border-radius: 10px;
        padding: 0.65rem 0.8rem; text-align: center;
    }
    .ci-status-card .ci-label, .ci-status-card .ci-value { display: block; }
    .ci-panel {
        background: #161B22; color: #E6EDF3; border: 1px solid #2A3441; border-radius: 10px;
        padding: 0.7rem 0.85rem; margin-bottom: 0.8rem;
    }
    .ci-panel p { margin: 0; }

    @media (max-width: 640px) {
        .ci-card { padding: 0.7rem 0.75rem; }
        .ci-grid { grid-template-columns: 1fr 1fr; }
        [data-testid="stChatMessage"] { padding: 0.7rem 0.75rem; }
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
