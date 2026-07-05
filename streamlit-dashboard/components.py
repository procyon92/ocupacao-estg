from __future__ import annotations
import streamlit as st
import pandas as pd
from config import COLORS, DIMENSION_COVERAGE_COLS, Omisso
from utils import pct


def render_kpi(label: str, value: str, icon: str = "", tooltip: str = "") -> None:
    # Cartão KPI com tooltip opcional — o tooltip aparece ao passar o rato por cima
    title_attr = ""
    if tooltip:
        safe = tooltip.replace('"', "&quot;").replace("'", "&#39;")
        title_attr = f'title="{safe}"'

    cursor = "cursor:help;" if tooltip else ""

    st.markdown(f"""
    <div {title_attr} style="background:{COLORS['kpi_bg']};border-radius:14px;
                padding:1.3rem 1.5rem;height:110px;display:flex;flex-direction:column;
                justify-content:center;border:2px solid #A8B8E8;
                box-shadow:0 2px 8px rgba(59,99,251,0.10);{cursor}">
        <span style="color:{COLORS['kpi_label']};font-size:0.82rem;font-weight:500;
                    letter-spacing:0.02em;">{icon} {label}</span>
        <span style="color:{COLORS['kpi_value']};font-size:2rem;font-weight:700;
                     line-height:1.2;margin-top:0.3rem;">{value}</span>
    </div>
    """, unsafe_allow_html=True)


def render_linha_kpi_salas(kpi: dict, total_rooms: int) -> None:
    # Linha de KPIs de salas (ocupadas / livres / total) — partilhada entre várias views
    espacos_livres = max(total_rooms - kpi["espacos_ocupados"], 0)
    c1, c2, c3 = st.columns(3)
    with c1: render_kpi("Salas Ocupadas", f"{kpi['espacos_ocupados']:,}", "🏢")
    with c2: render_kpi("Salas Livres",   f"{espacos_livres:,}",          "🟢")
    with c3: render_kpi("Salas Totais",   f"{total_rooms:,}",             "📐")


def render_cartao_qualidade(label: str, value: int, color: str) -> None:
    st.markdown(f"""
    <div style="background:{color};border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.6rem;">
        <span style="color:#475569;font-size:0.78rem;font-weight:500;">{label}</span>
        <div style="font-size:1.6rem;font-weight:700;color:#1B2139;margin-top:2px;">{value:,}</div>
    </div>
    """, unsafe_allow_html=True)


def render_cabecalho_seccao(title: str) -> None:
    st.markdown(f"<h4 style='color:#1B2139;font-weight:700;'>{title}</h4>", unsafe_allow_html=True)


def render_spacer(rem: float = 1.0) -> None:
    st.markdown(f"<div style='height:{rem}rem'></div>", unsafe_allow_html=True)


def render_cobertura_dimensao(df: pd.DataFrame) -> None:
    # Para cada dimensão, calcula quantos registos têm valor preenchido (diferente de N/D)
    coverage = []
    for label, col in DIMENSION_COVERAGE_COLS.items():
        if col not in df.columns:
            continue
        total  = len(df)
        filled = (df[col] != Omisso.ND).sum()
        coverage.append({
            "Dimensão":    label,
            "Preenchidos": filled,
            "Total":       total,
            "Cobertura":   f"{pct(filled, total)}%",
        })
    if coverage:
        st.dataframe(pd.DataFrame(coverage), use_container_width=True, hide_index=True)