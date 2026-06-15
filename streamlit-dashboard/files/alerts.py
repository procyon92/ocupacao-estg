"""profiles/alerts.py — Profile E: Painel de Alertas (Critical Hours)."""
from __future__ import annotations
import streamlit as st
from models import Filters
from profiles.base import BaseProfile
from profiles._helpers import load_and_prepare
from queries import get_filtered_rooms_count, get_occupancy_by_slot
from transforms import compute_general_kpis
from components import render_kpi, render_spacer, render_section_header
from plots import chart_critical_heatmap


class AlertsProfile(BaseProfile):
    def render(self, filters: Filters) -> None:
        self._h2("Painel de Alertas — Horários Críticos")
        self._subtitle(
            "Defina os limites de ocupação para identificar horários críticos. "
            "Os thresholds aplicam-se à percentagem de salas ocupadas por slot (Dia da Semana × Hora)."
        )

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            low_threshold  = st.slider("Limite Baixo-Médio (%)", 10, 50, 30, key="v4_alert_low")
        with col_s2:
            high_threshold = st.slider("Limite Médio-Alto (%)",  51, 95, 70, key="v4_alert_high")

        if low_threshold >= high_threshold:
            st.error("O limite baixo-médio deve ser inferior ao limite médio-alto.")
            return

        df = load_and_prepare(filters)
        if df.empty:
            return self._empty()

        total_rooms = get_filtered_rooms_count(
            escola=filters.get("escola"),
            edificio=filters.get("edificio"),
            categoria_espaco=filters.get("categoria_espaco"),
        )
        kpi            = compute_general_kpis(df)
        espacos_livres = max(total_rooms - kpi["espacos_ocupados"], 0)

        df_slots = get_occupancy_by_slot(
            ano_letivo=filters.get("ano_letivo"),
            semestre=filters.get("semestre"),
            escola=filters.get("escola"),
            edificio=filters.get("edificio"),
            categoria_espaco=filters.get("categoria_espaco"),
        )

        if not df_slots.empty:
            df_slots       = df_slots.copy()
            df_slots["ratio"] = df_slots["Salas_Ocupadas"] / max(total_rooms, 1) * 100
            critical_count = (df_slots["ratio"] > high_threshold).sum()
            tx_critica     = round(critical_count / max(len(df_slots), 1) * 100, 1)
        else:
            tx_critica = 0

        k1, k2, k3, k4 = st.columns(4)
        with k1: render_kpi("Salas Ocupadas", f"{kpi['espacos_ocupados']:,}", "🏢")
        with k2: render_kpi("Salas Livres",   f"{espacos_livres:,}", "🟢")
        with k3: render_kpi("Total Salas",    f"{total_rooms:,}", "📐")
        with k4: render_kpi("Tx. Crítica",    f"{tx_critica}%", "🔴")

        render_spacer(1.2)
        render_section_header("Mapa de Ocupação Crítica")
        st.plotly_chart(
            chart_critical_heatmap(df_slots, total_rooms, low_threshold, high_threshold),
            use_container_width=True, key="chart_critical_heat",
        )

        render_spacer()
        render_section_header("Slots Críticos")
        if not df_slots.empty:
            df_slots["Nível"] = df_slots["ratio"].apply(
                lambda r: "🔴 Alta" if r > high_threshold
                else "🟡 Média" if r >= low_threshold
                else "🟢 Baixa"
            )
            df_slots["% Ocupação"] = df_slots["ratio"].round(1).astype(str) + "%"
            display = (
                df_slots.sort_values("ratio", ascending=False)
                [["DiaSemana", "Hora_Inicio", "Salas_Ocupadas", "% Ocupação", "Nível"]]
                .rename(columns={
                    "DiaSemana": "Dia", "Hora_Inicio": "Hora", "Salas_Ocupadas": "Salas Ocupadas"
                })
            )
            display["Hora"] = display["Hora"].astype(int).astype(str) + "h"
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)
        else:
            self._empty("Sem dados de ocupação por slot.")
