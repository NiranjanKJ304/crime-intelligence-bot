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
    </style>
    """,
    unsafe_allow_html=True,
)

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
