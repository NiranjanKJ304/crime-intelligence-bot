"""
Citation card rendering component.

Styled by the .ci-cite* classes in app.py (dark surface, light text).
"""

from __future__ import annotations

import html

import streamlit as st

from api.client import Citation
from utils.helpers import fmt_score, truncate

# Badge backgrounds are all dark enough for white badge text.
BADGE_COLOURS = {
    "postgresql": "#1B3A5C",
    "backend_tool": "#6C3483",
    "case_summary": "#2A5F9E",
    "accused_profile": "#C0392B",
    "victim_profile": "#D35400",
    "officer_profile": "#1E8449",
    "court_summary": "#9A7D0A",
    "district_summary": "#2471A3",
}


def render_citation_cards(citations: list[Citation]) -> None:
    """Render a horizontal row of citation cards."""
    if not citations:
        return

    st.markdown('<p class="ci-section-title">📎 &nbsp;Citations</p>', unsafe_allow_html=True)

    # Up to 3 columns per row
    cols_per_row = min(len(citations), 3)
    for row_start in range(0, len(citations), cols_per_row):
        row_citations = citations[row_start : row_start + cols_per_row]
        cols = st.columns(len(row_citations))
        for col, cit in zip(cols, row_citations):
            with col:
                _render_single_card(cit)


def _render_single_card(cit: Citation) -> None:
    """Render one citation card."""
    snippet = truncate(cit.text_snippet, 160) if cit.text_snippet else "—"
    score_pct = fmt_score(cit.score)
    badge_bg = BADGE_COLOURS.get(cit.document_type, "#4B5563")
    score_label = "Match" if cit.document_type in ("postgresql", "backend_tool") else "Similarity"

    st.markdown(
        f"""
        <div class="ci-cite">
            <div class="ci-cite-head">
                <code class="ci-cite-id">{html.escape(cit.document_id)}</code>
                <span class="ci-cite-badge" style="background:{badge_bg};">{html.escape(cit.document_type)}</span>
            </div>
            <p class="ci-cite-snippet">{html.escape(snippet)}</p>
            <p class="ci-cite-score">{score_label}: {score_pct}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
