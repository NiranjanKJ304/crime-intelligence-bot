"""
Chat message rendering components.
"""

from __future__ import annotations

import streamlit as st


def render_user_message(text: str) -> None:
    """Render a user message bubble."""
    st.markdown(
        f"""
        <div style="display:flex; justify-content:flex-end; margin-bottom:0.8rem;">
            <div style="background:linear-gradient(135deg,#1B3A5C,#2A5F9E);
                        color:white; padding:0.75rem 1rem; border-radius:16px 16px 4px 16px;
                        max-width:75%; font-size:0.92rem; line-height:1.55;
                        box-shadow:0 2px 8px rgba(27,58,92,0.15);">
                {text}
            </div>
            <div style="margin-left:0.5rem; font-size:1.5rem; line-height:1;">👤</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_assistant_message(text: str) -> None:
    """Render an assistant message bubble."""
    st.markdown(
        f"""
        <div style="display:flex; justify-content:flex-start; margin-bottom:0.8rem;">
            <div style="margin-right:0.5rem; font-size:1.5rem; line-height:1;">🔍</div>
            <div style="background:#F0F4F8; color:#1A1A1A;
                        padding:0.75rem 1rem; border-radius:16px 16px 16px 4px;
                        max-width:75%; font-size:0.92rem; line-height:1.55;
                        border:1px solid #E0E0E0;
                        box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_error_message(text: str) -> None:
    """Render an error banner."""
    st.error(f"⚠️  {text}", icon="🚨")
