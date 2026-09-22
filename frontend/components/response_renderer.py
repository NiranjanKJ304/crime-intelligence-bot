"""
ResponseRenderer — turns a backend ChatResult into structured UI.

Dispatches on `response_type` (see api/schemas.py) and renders cards /
tables for database results. Anything unknown, or a response without
structured data, falls back to rendering the Markdown `answer`.
Never shows raw JSON or Markdown syntax to the user.
"""

from __future__ import annotations

import html
from typing import Any, Callable

import streamlit as st

from api.client import ChatResult
from api.schemas import (
    CaseDetailsData,
    OfficerDetailsData,
    PersonDetailsData,
    SearchResultsData,
    StatisticsData,
)

# ── Field labels (logical key -> human label) ──────────────────────────
CASE_FIELDS: list[tuple[str, str]] = [
    ("case_number", "Case Number (CaseNo)"),
    ("crime_number", "Crime Number (FIR)"),
    ("status", "Case Status ID"),
    ("police_person_id", "Investigating Officer ID"),
    ("station_id", "Police Station ID"),
    ("case_id", "CaseMasterID"),
]
OFFICER_FIELDS: list[tuple[str, str]] = [
    ("first_name", "Name"),
    ("kgid", "KGID"),
    ("designation", "Designation ID"),
    ("rank", "Rank ID"),
    ("employee_id", "Employee ID"),
]
PERSON_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "victim": [("victim_id", "VictimMasterID"), ("name", "Name"), ("age", "Age"), ("gender", "Gender ID"), ("case_id", "CaseMasterID")],
    "accused": [("accused_id", "AccusedMasterID"), ("name", "Name"), ("age", "Age"), ("gender", "Gender ID"), ("person_id", "PersonID"), ("case_id", "CaseMasterID")],
}


# ── Low-level HTML helpers (styled by .ci-* classes in app.py) ─────────

def _fmt(value: Any, default: str = "—") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return html.escape(str(value))


def _card(title: str, body_html: str, icon: str = "", subtitle: str | None = None) -> None:
    sub = f'<p class="ci-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="ci-card">
            <div class="ci-card-header">
                <span class="ci-card-icon">{icon}</span>
                <div><h4 class="ci-card-title">{html.escape(title)}</h4>{sub}</div>
            </div>
            {body_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _field_grid(record: dict[str, Any], fields: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<div class="ci-field"><span class="ci-label">{html.escape(label)}</span>'
        f'<span class="ci-value">{_fmt(record.get(key))}</span></div>'
        for key, label in fields
        if key in record
    )
    return f'<div class="ci-grid">{cells}</div>'


def _table(columns: list[tuple[str, str]], rows: list[dict[str, Any]]) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_fmt(row.get(key))}</td>" for key, _ in columns) + "</tr>"
        for row in rows
    )
    return f'<div class="ci-table-wrap"><table class="ci-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _badge(text: str, tone: str = "info") -> str:
    return f'<span class="ci-badge ci-badge-{tone}">{html.escape(text)}</span>'


def _case_label(case: dict[str, Any] | None) -> str | None:
    if not case:
        return None
    return f"CaseNo {case.get('case_number', '—')} · CaseMasterID {case.get('case_id', '—')}"


# ── Renderers ─────────────────────────────────────────────────────────

def render_answer(answer: str) -> None:
    """Plain / LLM answer — Markdown rendered by Streamlit, never shown raw."""
    st.markdown(answer or "_No response._")


def render_case_details(data: CaseDetailsData, answer: str) -> None:
    case = data.get("case")
    if not case:
        return render_answer(answer)

    _card(
        f"Case {case.get('case_number', '')}",
        _field_grid(case, CASE_FIELDS),
        icon="📁",
        subtitle="PostgreSQL · CaseMaster",
    )

    chargesheet = data.get("chargesheet")
    if chargesheet is not None:
        filed = bool(chargesheet.get("filed"))
        status = _badge("Filed", "success") if filed else _badge("Not filed", "warning")
        body = f'<div class="ci-row">{status}</div>'
        if filed:
            body += _field_grid(
                {"date": chargesheet.get("date"), "court_name": chargesheet.get("court_name")},
                [("date", "Filed on"), ("court_name", "Court")],
            )
        _card("Chargesheet", body, icon="📄")


def render_officer_details(data: OfficerDetailsData, answer: str) -> None:
    officer = data.get("officer")
    if not officer:
        return render_answer(answer)

    case = data.get("case")
    subtitle = f"Investigating officer for {_case_label(case)}" if case else "PostgreSQL · Employee"
    _card(
        officer.get("first_name") or "Officer",
        _field_grid(officer, OFFICER_FIELDS),
        icon="👮",
        subtitle=subtitle,
    )


def render_person_details(data: PersonDetailsData, answer: str) -> None:
    role = data.get("role", "accused")
    persons = data.get("persons") or []
    case = data.get("case")
    if not persons:
        return render_answer(answer)

    columns = PERSON_COLUMNS.get(role, PERSON_COLUMNS["accused"])
    noun = "victim" if role == "victim" else "accused"
    title = f"{len(persons)} {noun}{'s' if len(persons) != 1 and role == 'victim' else ''}"
    subtitle = f"Recorded on {_case_label(case)}" if case else None
    _card(title, _table(columns, persons), icon="🧾" if role == "victim" else "🕵️", subtitle=subtitle)


def render_search_results(data: SearchResultsData, answer: str) -> None:
    results = data.get("results") or []
    if not results:
        return render_answer(answer)

    entity = data.get("entity", "record")
    query = data.get("query", "")
    total = data.get("total", len(results))
    columns = PERSON_COLUMNS.get(entity) or [(k, k) for k in results[0].keys()]

    body = ""
    if data.get("note"):
        body += f'<div class="ci-note">{html.escape(data["note"])}</div>'
    body += _table(columns, results)
    _card(
        f"{total} {entity} record{'s' if total != 1 else ''} for “{query}”",
        body,
        icon="🔎",
        subtitle="PostgreSQL · exact name match",
    )


def render_statistics(data: StatisticsData, answer: str) -> None:
    metrics = data.get("metrics") or {}
    if not metrics:
        return render_answer(answer)

    st.markdown(f"**{html.escape(data.get('title', 'Statistics'))}**")
    items = list(metrics.items())
    for start in range(0, len(items), 4):
        cols = st.columns(min(4, len(items) - start))
        for col, (label, value) in zip(cols, items[start:start + 4]):
            with col:
                st.metric(label, value if value is not None else "—")


_RENDERERS: dict[str, Callable[[dict[str, Any], str], None]] = {
    "case_details": render_case_details,
    "officer_details": render_officer_details,
    "person_details": render_person_details,
    "search_results": render_search_results,
    "statistics": render_statistics,
}


def render_response(result: ChatResult) -> None:
    """Entry point: pick a structured renderer, fall back to the Markdown answer."""
    if result.error:
        st.error(f"🚨 **Backend Error:** {result.error}")
        return

    renderer = _RENDERERS.get(result.response_type)
    if renderer and isinstance(result.data, dict):
        try:
            renderer(result.data, result.answer)
            return
        except Exception:  # never let a rendering bug hide the answer
            pass
    render_answer(result.answer)
