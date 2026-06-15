"""profiles/quality.py — Profile D: Qualidade dos Dados / ETL."""
from __future__ import annotations
import streamlit as st
import pandas as pd
from models import Filters
from profiles.base import BaseProfile
from queries import (
    get_filtered_data, get_etl_quality_metrics,
    get_ghost_sessions_trend, get_unmapped_records_count, get_raw_anomalies,
)
from transforms import normalize_dataframe, combine_anomaly_flags
from components import render_kpi, render_spacer, render_section_header, render_dimension_coverage
from plots import chart_anomalies_trend


class QualityProfile(BaseProfile):
    def render(self, filters: Filters) -> None:
        self._h2("Qualidade dos Dados / ETL")

        metrics     = get_etl_quality_metrics()
        ghost_trend = get_ghost_sessions_trend(
            ano_escolar=filters.get("ano_letivo"),
            semestre=filters.get("semestre"),
        )
        unmapped       = get_unmapped_records_count()
        total_ghost    = unmapped.get("Ghost Sessions (0 Presenças)", 0)
        total_uc       = unmapped.get("UC Sem Mapeamento", 0)
        total_curso    = unmapped.get("Curso Sem Mapeamento", 0)
        pct_quality    = round(metrics["valid"] / max(metrics["total"], 1) * 100, 1)

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        with k1: render_kpi("Total Carregados", f"{metrics['total']:,}", "📦")
        with k2: render_kpi("Válidos",           f"{metrics['valid']:,}", "✅")
        with k3: render_kpi("Com Erros",         f"{metrics['errors']:,}", "⚠️")
        with k4: render_kpi("Qualidade",         f"{pct_quality}%", "🎯")
        with k5: render_kpi("Ghost Sessions",    f"{total_ghost:,}", "👻")
        with k6: render_kpi("UC/Curso N/D",      f"{total_uc + total_curso:,}", "🚫")

        render_spacer(1.2)
        render_section_header("Evolução de Anomalias")
        st.plotly_chart(chart_anomalies_trend(ghost_trend),
                        use_container_width=True, key="chart_ghost_trend")

        render_spacer()
        df = normalize_dataframe(get_filtered_data(
            ano_letivo=filters.get("ano_letivo"),
            semestre=filters.get("semestre"),
        ))
        if not df.empty:
            render_section_header("Cobertura de Chaves Dimensionais")
            render_dimension_coverage(df)

        render_spacer()
        render_section_header("Registo de Anomalias (Auditoria)")
        self._subtitle(
            "Últimos registos com problemas de qualidade — ghost sessions, "
            "UC sem mapeamento, curso N/D ou responsável indefinido."
        )

        anomalies_df = normalize_dataframe(get_raw_anomalies(limit=100))
        if anomalies_df.empty:
            st.success("Nenhuma anomalia encontrada nos registos atuais.")
            return

        display = anomalies_df.copy()
        if "DataCompleta" in display.columns:
            display["Data"] = display["DataCompleta"].dt.strftime("%d/%m/%Y")
        display["Início"]    = display.apply(lambda r: f"{int(r['Hora_Inicio']):02d}h", axis=1)
        display["Fim"]       = display.apply(lambda r: f"{int(r['Hora_Fim']):02d}h", axis=1)
        display["Anomalias"] = display.apply(combine_anomaly_flags, axis=1)

        audit_cols = [c for c in [
            "Data", "DiaSemana", "Início", "Fim", "Edificio", "Nome_Espaco",
            "Designacao_UC", "Nome_Curso", "Docente_Responsavel",
            "Duracao_Minutos", "Numero_Presencas", "Anomalias",
        ] if c in display.columns]

        st.dataframe(
            display[audit_cols].rename(columns={
                "DiaSemana": "Dia", "Nome_Espaco": "Espaço", "Designacao_UC": "UC",
                "Nome_Curso": "Curso", "Docente_Responsavel": "Docente",
                "Duracao_Minutos": "Dur. (min)", "Numero_Presencas": "Presenças",
            }),
            use_container_width=True, hide_index=True, height=400,
        )

        render_spacer()
        st.markdown(
            "<p style='color:#94A3B8;font-size:0.85rem;'>"
            "Dados do Data Warehouse MySQL. Anomalias atualizadas a cada 5 minutos.</p>",
            unsafe_allow_html=True,
        )
