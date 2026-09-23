"""
Chat message containers.

Uses Streamlit's native chat containers so Markdown is rendered (not shown
raw) and structured components can be placed inside a message bubble.
Styling lives in the .ci-* / stChatMessage rules in app.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st

USER_AVATAR = "👤"
ASSISTANT_AVATAR = "🔍"


def render_user_message(text: str) -> None:
    with st.chat_message("user", avatar=USER_AVATAR):
        # Custom avatars all get the same test id, so a hidden marker lets the
        # CSS style user bubbles differently from assistant bubbles.
        st.markdown('<span class="ci-user-marker"></span>', unsafe_allow_html=True)
        st.markdown(text)


@contextmanager
def assistant_message() -> Iterator[None]:
    """Container for an assistant turn; render structured content inside it."""
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        yield


def render_assistant_message(text: str) -> None:
    with assistant_message():
        st.markdown(text)


def render_error_message(text: str) -> None:
    """Render an error banner."""
    st.error(f"⚠️  {text}", icon="🚨")
