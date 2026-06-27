from __future__ import annotations
import streamlit as st
from models import Filters
from view.base import BaseProfile
from view._helpers import load_and_prepare
from queries import get_filtered_rooms_count
from transforms import compute_general_kpis, build_heatmap_data
from components import render_kpi, render_spacer, render_section_header
from utils import fmt_duration
from plots import (
    chart_ocupacao_tempo, chart_ocupacao_edificio, chart_heatmap_ocupacao,
    chart_top_espacos, chart_bottom_espacos, chart_tipo_atividade,
    chart_categoria_espaco, chart_period_of_day,
)
from config import PLOTLY_CONFIG
from view.tooltips import TAXA_UTILIZACAO, TEMPO_MEDIO, GHOST

class GeralProfile(BaseProfile):
    def render(self, filters: Filters) -> None:
        self._h2("Visão Geral")

        df = load_and_prepare(filters)
        if df.empty:
            return self._empty()

        kpi = compute_general_kpis(df)
        total_rooms = get_filtered_rooms_count(
            escola=filters.get("escola"),
            edificio=filters.get("edificio"),
            categoria_espaco=filters.get("categoria_espaco"),
        )

        # KPIs
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        with k1: render_kpi("Salas Ocupadas",   f"{kpi['espacos_ocupados']:,}", "🏢")
        with k2: render_kpi("Salas Livres",     f"{max(total_rooms - kpi['espacos_ocupados'], 0):,}", "🟢")
        with k3: render_kpi("Salas Totais",     f"{total_rooms:,}", "📐")
        with k4: render_kpi("Taxa Utilização",  f"{kpi['taxa_ocup']}%", "📊", TAXA_UTILIZACAO)
        with k5: render_kpi("Tempo Médio",      fmt_duration(kpi["avg_min"]), "⏱️", TEMPO_MEDIO)
        with k6: render_kpi("Sessões Vazias %", f"{kpi['ghost_pct']}%", "👻", GHOST)

        render_spacer(1.2)

        # Distribuição por edifício e categoria
        render_section_header("Distribuição por Edifício e Categoria")
        col_donut1, col_donut2 = st.columns(2)
        with col_donut1:
            st.plotly_chart(chart_ocupacao_edificio(df), use_container_width=True, key="chart_donut_v2", config= PLOTLY_CONFIG)
        with col_donut2:
            st.plotly_chart(chart_categoria_espaco(df), use_container_width=True, key="chart_cat_v2", config= PLOTLY_CONFIG)

        render_spacer()

        # Análise por período do dia e tipo de atividade
        render_section_header("Análise por Período e Tipo de Atividade")
        col_period, col_atv = st.columns(2)
        with col_period:
            st.plotly_chart(chart_period_of_day(df), use_container_width=True, key="chart_period", config= PLOTLY_CONFIG)
        with col_atv:
            st.plotly_chart(chart_tipo_atividade(df), use_container_width=True, key="chart_atv_v2", config= PLOTLY_CONFIG)

        render_spacer()

        # Espaços com mais e menos ocupações
        render_section_header("Espaços com Mais e Menos Ocupações")
        slider_col, _ = st.columns([1, 3])
        with slider_col:
            top_n = st.slider("Número de espaços", 5, 30, 10, key="top_n")

        col_top, col_bottom = st.columns(2)
        with col_top:
            st.plotly_chart(chart_top_espacos(df, top_n), use_container_width=True, key="chart_top", config= PLOTLY_CONFIG)
        with col_bottom:
            st.plotly_chart(chart_bottom_espacos(df, top_n), use_container_width=True, key="chart_bottom", config= PLOTLY_CONFIG)

        render_spacer()

        # Ocupação ao longo do tempo
        render_section_header("Ocupação ao Longo do Tempo")
        gran = st.radio(
            "Granularidade",
            ["Diário", "Semanal", "Mensal"],
            horizontal=True,
            label_visibility="collapsed",
            key="gran_tempo",
        )
        st.plotly_chart(chart_ocupacao_tempo(df, gran), use_container_width=True, key="chart_trend", config= PLOTLY_CONFIG)

        render_spacer()

        # Mapa de calor de ocupação
        render_section_header("Mapa de Calor de Ocupação")
        st.plotly_chart(
            chart_heatmap_ocupacao(build_heatmap_data(df)),
            use_container_width=True,
            key="chart_heat_v2",
            config= PLOTLY_CONFIG
        )