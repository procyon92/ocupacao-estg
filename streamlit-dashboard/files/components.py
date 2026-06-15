"""
components.py — Reusable Streamlit UI components.

All functions render into the active Streamlit container.
No SQL, no business logic, no state mutations.
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
from config import COLORS, DIMENSION_COVERAGE_COLS, Sentinel
from utils import pct


def render_kpi(label: str, value: str, icon: str = "") -> None:
    """Single KPI card."""
    st.markdown(f"""
    <div style="background:{COLORS['kpi_bg']};border-radius:14px;padding:1.3rem 1.5rem;
                height:110px;display:flex;flex-direction:column;justify-content:center;
                border:1px solid #E8EDF5;">
        <span style="color:{COLORS['kpi_label']};font-size:0.82rem;font-weight:500;
                    letter-spacing:0.02em;">{icon} {label}</span>
        <span style="color:{COLORS['kpi_value']};font-size:2rem;font-weight:700;
                     line-height:1.2;margin-top:0.3rem;">{value}</span>
    </div>
    """, unsafe_allow_html=True)


def render_rooms_kpi_row(kpi: dict, total_rooms: int) -> None:
    """
    Standard 3-column rooms KPI row (occupied / free / total).
    Shared by profiles A and E to eliminate duplication.
    """
    espacos_livres = max(total_rooms - kpi["espacos_ocupados"], 0)
    c1, c2, c3 = st.columns(3)
    with c1: render_kpi("Salas Ocupadas", f"{kpi['espacos_ocupados']:,}", "🏢")
    with c2: render_kpi("Salas Livres",   f"{espacos_livres:,}",          "🟢")
    with c3: render_kpi("Salas Totais",   f"{total_rooms:,}",             "📐")


def render_quality_card(label: str, value: int, color: str) -> None:
    st.markdown(f"""
    <div style="background:{color};border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.6rem;">
        <span style="color:#475569;font-size:0.78rem;font-weight:500;">{label}</span>
        <div style="font-size:1.6rem;font-weight:700;color:#1B2139;margin-top:2px;">{value:,}</div>
    </div>
    """, unsafe_allow_html=True)


def render_section_header(title: str) -> None:
    st.markdown(f"<h4 style='color:#1B2139;font-weight:700;'>{title}</h4>", unsafe_allow_html=True)


def render_spacer(rem: float = 1.0) -> None:
    st.markdown(f"<div style='height:{rem}rem'></div>", unsafe_allow_html=True)


def render_dimension_coverage(df: pd.DataFrame) -> None:
    """Dimension coverage table for the data quality profile."""
    coverage = []
    for label, col in DIMENSION_COVERAGE_COLS.items():
        if col not in df.columns:
            continue
        total  = len(df)
        filled = (df[col] != Sentinel.ND).sum()
        coverage.append({
            "Dimensão":    label,
            "Preenchidos": filled,
            "Total":       total,
            "Cobertura":   f"{pct(filled, total)}%",
        })
    if coverage:
        st.dataframe(pd.DataFrame(coverage), use_container_width=True, hide_index=True)
