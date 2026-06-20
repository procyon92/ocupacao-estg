"""profiles/labs.py — Profile B: Laboratórios."""
from __future__ import annotations
import streamlit as st
import pandas as pd
from models import Filters
from profiles.base import BaseProfile
from profiles._helpers import load_and_prepare
from queries import get_filtered_rooms_count, get_departamentos
from transforms import build_heatmap_data
from components import render_kpi, render_spacer, render_section_header
from utils import fmt_duration_long
from config import LAB_CATEGORY, Sentinel
from plots import (
    chart_heatmap_ocupacao, chart_period_of_day,
    chart_tipo_atividade, chart_top_espacos, chart_bottom_espacos,
)

_TOOLTIPS = {
    "ghost":    "Percentagem de sessões com 0 presenças registadas.",
}

class LabsProfile(BaseProfile):
    def render(self, filters: Filters) -> None:
        self._h2("Laboratórios")
        self._subtitle(
            "Filtro automático: Categoria = Laboratório. "
            "Os restantes filtros podem ser ajustados livremente."
        )

        dept_map       = get_departamentos()
        dept_labels    = list(dept_map.keys())
        DEFAULT_LABEL  = "Engenharia Informática"
        label_opts     = [Sentinel.ALL_DEPTS] + dept_labels
        default_idx    = label_opts.index(DEFAULT_LABEL) if DEFAULT_LABEL in label_opts else 0

        selected_label = st.selectbox(
            "Departamento", options=label_opts, index=default_idx, key="v2_lab_dept_select"
        )

        # Build a labs-specific filters copy: force LAB_CATEGORY and optionally dept
        lab_filters: Filters = dict(filters)   # type: ignore[assignment]
        lab_filters["only_labs"]        = True
        lab_filters["categoria_espaco"] = LAB_CATEGORY
        if selected_label != Sentinel.ALL_DEPTS:
            lab_filters["departamento"] = dept_map[selected_label]
        else:
            lab_filters.pop("departamento", None)

        df = load_and_prepare(lab_filters)
        if df.empty:
            return self._empty("Sem dados de laboratório para os filtros selecionados.")

        total_ocup  = len(df)
        labs_unicos = df["Nome_Espaco"].nunique()
        total_pres  = int(df["Numero_Presencas"].sum())
        avg_pres    = round(total_pres / max(total_ocup, 1), 1)
        ghost_count = int((df["Numero_Presencas"] == 0).sum())

        total_labs  = get_filtered_rooms_count(
            escola=lab_filters.get("escola"),
            edificio=lab_filters.get("edificio"),
            categoria_espaco=LAB_CATEGORY,
            departamento=lab_filters.get("departamento"),
        )
        labs_livres = max(total_labs - labs_unicos, 0)

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1: render_kpi("Sessões",             f"{total_ocup:,}", "🔬")
        with k2: render_kpi("Laboratórios Livres", str(labs_livres),  "🟢")
        with k3: render_kpi("Laboratórios Totais", str(total_labs),   "🖥️")
        with k4: render_kpi("Média Presenças",     str(avg_pres),     "👥")
        with k5: render_kpi("Sessões Vazias",      f"{ghost_count:,}", "👻", _TOOLTIPS["ghost"])

        render_spacer(1.2)
        col_heat, col_period = st.columns([2, 1])
        with col_heat:
            st.plotly_chart(chart_heatmap_ocupacao(build_heatmap_data(df)),
                            use_container_width=True, key="lab_chart_heat")
        with col_period:
            st.plotly_chart(chart_period_of_day(df), use_container_width=True, key="lab_chart_period")

        render_spacer()
        top_n = st.slider("Top / Bottom N Laboratórios", 5, 30, 10, key="v2_lab_top_n")
        col_tipo, col_top, col_bottom = st.columns(3)
        with col_tipo:
            st.plotly_chart(chart_tipo_atividade(df), use_container_width=True, key="lab_chart_tipo")
        with col_top:
            st.plotly_chart(chart_top_espacos(df, top_n), use_container_width=True, key="lab_chart_top")
        with col_bottom:
            st.plotly_chart(chart_bottom_espacos(df, top_n), use_container_width=True, key="lab_chart_bottom")

        render_spacer()
        render_section_header("Gestão de Capacidade — Laboratórios")
        summary = (
            df.groupby(["Edificio", "Nome_Espaco"])
            .agg(
                Sessoes=("ID_Ocupacao",      "count"),
                Horas_Total=("Duracao_Minutos", "sum"),
                Media_Presencas=("Numero_Presencas", "mean"),
                Media_Horas=("Duracao_Minutos",  "mean"),
            )
            .reset_index()
            .sort_values("Sessoes", ascending=False)
        )
        q75 = summary["Sessoes"].quantile(0.75)
        q50 = summary["Sessoes"].quantile(0.50)
        summary["Horas_Total"]     = (summary["Horas_Total"] / 60).round(0).astype(int)
        summary["Media_Presencas"] = summary["Media_Presencas"].round(1)
        summary["Media_Horas"] = summary["Media_Horas"].apply(fmt_duration_long)
        summary["Carga"] = summary["Sessoes"].apply(
            lambda x: "🔴 Alta" if x > q75 else "🟡 Média" if x > q50 else "🟢 Baixa"
        )
        summary.columns = [
            "Edifício", "Laboratório", "Sessões",
            "Horas Totais", "Média Presenças", "Duração Média por Sessão", "Carga",
        ]
        st.dataframe(summary, use_container_width=True, hide_index=True)
