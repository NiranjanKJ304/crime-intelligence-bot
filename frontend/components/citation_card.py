"""
Citation card rendering component.
"""

from __future__ import annotations

import streamlit as st

from api.client import Citation
from utils.helpers import fmt_score, truncate


def render_citation_cards(citations: list[Citation]) -> None:
    """Render a horizontal row of citation cards."""
    if not citations:
        return

    st.markdown(
        """
        <p style="font-weight:600; font-size:0.85rem; color:#1B3A5C;
                  margin:0.8rem 0 0.4rem; text-transform:uppercase;
                  letter-spacing:0.4px;">
            📎 &nbsp;Citations
        </p>
        """,
        unsafe_allow_html=True,
    )

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

    # Badge colour by document type
    badge_colours = {
        "case_summary": "#2A5F9E",
        "crime_pattern": "#6C3483",
        "suspect_profile": "#C0392B",
        "officer_record": "#27AE60",
        "court_record": "#D4AC0D",
        "station_report": "#2980B9",
    }
    badge_bg = badge_colours.get(cit.document_type, "#6C757D")

    st.markdown(
        f"""
        <div style="background:white; border:1px solid #E0E0E0; border-radius:10px;
                    padding:0.7rem 0.85rem; margin-bottom:0.5rem;
                    box-shadow:0 1px 4px rgba(0,0,0,0.05);
                    transition: transform 0.15s; cursor:default;"
             onmouseover="this.style.transform='translateY(-2px)'"
             onmouseout="this.style.transform='translateY(0)'">
            <div style="display:flex; justify-content:space-between; align-items:center;
                        margin-bottom:0.35rem;">
                <code style="font-size:0.73rem; color:#1B3A5C; font-weight:600;">
                    {cit.document_id}
                </code>
                <span style="background:{badge_bg}; color:white; font-size:0.65rem;
                             padding:2px 8px; border-radius:12px; font-weight:500;">
                    {cit.document_type}
                </span>
            </div>
            <p style="margin:0 0 0.3rem; font-size:0.78rem; color:#555; line-height:1.45;">
                {snippet}
            </p>
            <p style="margin:0; font-size:0.72rem; color:#2A5F9E; font-weight:600;">
                Similarity: {score_pct}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
