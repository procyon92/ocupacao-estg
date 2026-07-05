from __future__ import annotations
import streamlit as st
import pandas as pd
from models import Filters
from view.base import BaseProfile
from queries import get_dados_detalhe_espaco, get_espacos
from transforms import normalizar_dataframe, apply_filtros_post
from components import render_spacer, render_cabecalho_seccao
from utils import clamp, pct
from config import DAILY_CAPACITY_MINUTES, PLOTLY_CONFIG
from plots import chart_top_espacos, chart_tendencia_comparacao


class ComparacaoProfile(BaseProfile):
    def render(self, filters: Filters) -> None:
        self._h2("Comparação de Ocupação entre Salas")
        self._subtitle("Selecione várias salas para comparar as suas métricas de ocupação.")

        all_rooms = get_espacos(
            edificio=filters.get("edificio"),
            categoria=filters.get("categoria_espaco"),
            departamento=filters.get("departamento"),
        )
        selected_rooms = st.multiselect(
            "Salas para comparar", options=all_rooms, default=[],
            key="compare_rooms", max_selections=10,
        )

        if not selected_rooms:
            return self._empty("Selecione pelo menos uma sala para começar a comparação.")

        # Carrega os dados de cada sala selecionada
        rooms_data: dict[str, pd.DataFrame] = {}
        with st.spinner("A carregar dados das salas..."):
            for room in selected_rooms:
                rd = apply_filtros_post(
                    normalizar_dataframe(
                        get_dados_detalhe_espaco(
                            space_name=room,
                            ano_escolar=filters.get("ano_letivo"),
                            semestre=filters.get("semestre"),
                            semana_escolar=filters.get("semana"),
                        )
                    ),
                    hide_online=filters.get("hide_online", False),
                    hide_concurrent=filters.get("hide_concurrent", False),
                    hide_ghost=filters.get("hide_ghost", False),
                )
                if not rd.empty:
                    rooms_data[room] = rd

        if not rooms_data:
            st.warning("Nenhum dado encontrado para as salas selecionadas.")
            return

        render_cabecalho_seccao("Tabela Comparativa")
        rows = [
            {
                "Sala":            name,
                "Sessões":         len(rd),
                "Horas":           int(rd["Duracao_Minutos"].sum() / 60),
                "Média Presenças": round(rd["Numero_Presencas"].mean(), 1),
                "Ghost %":         round(pct((rd["Numero_Presencas"] == 0).sum(), len(rd)), 1),
                "Tx. Utilização":  clamp(pct(rd["Duracao_Minutos"].sum(),
                                             rd["DataCompleta"].nunique() * DAILY_CAPACITY_MINUTES)),
            }
            for name, rd in rooms_data.items()
        ]
        comp_df = pd.DataFrame(rows).sort_values("Sessões", ascending=False)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        render_spacer()
        render_cabecalho_seccao("Sessões por Sala")
        # Junta todos os DataFrames numa coluna Nome_Espaco para o gráfico de barras
        combined = pd.concat(
            [rd.assign(Nome_Espaco=name) for name, rd in rooms_data.items()],
            ignore_index=True,
        )
        st.plotly_chart(
            chart_top_espacos(combined, top_n=len(rooms_data)),
            use_container_width=True, key="chart_compare_bar", config= PLOTLY_CONFIG
        )

        render_spacer()
        render_cabecalho_seccao("Tendência Diária Comparativa")
        st.plotly_chart(
            chart_tendencia_comparacao(rooms_data),
            use_container_width=True, key="chart_compare_trend", config= PLOTLY_CONFIG
        )