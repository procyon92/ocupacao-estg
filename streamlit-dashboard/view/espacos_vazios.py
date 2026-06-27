from __future__ import annotations
from datetime import datetime
import streamlit as st
from models import Filters
from view.base import BaseProfile
from queries import get_free_rooms_by_interval, get_filtered_rooms_count
from components import render_kpi, render_spacer
from utils import pct


class EspacosVaziosProfile(BaseProfile):
    def render(self, filters: Filters) -> None:
        self._h2("Consulta de Salas Livres por Intervalo")
        self._subtitle(
            "Selecione o dia e o intervalo horário pretendido. A plataforma irá listar "
            "apenas as salas que se encontram disponíveis durante todo o bloco selecionado."
        )

        col_date, col_h_ini, col_h_fim = st.columns([2, 1, 1])
        with col_date:
            search_date = st.date_input(
                "Data de Pesquisa", value=datetime.now().date(),
                format="DD/MM/YYYY", key="free_search_date",
            )
        with col_h_ini:
            search_hour_ini = st.selectbox(
                "Hora de Início", options=range(8, 23),
                format_func=lambda h: f"{h:02d}:00 h", index=1, key="free_search_hour_ini",
            )
        with col_h_fim:
            search_hour_fim = st.selectbox(
                "Hora de Fim", options=range(search_hour_ini + 1, 24),
                format_func=lambda h: f"{h:02d}:00 h", index=1, key="free_search_hour_fim",
            )

        esc = filters.get("escola")
        dep = filters.get("departamento")
        edi = filters.get("edificio")
        cat = filters.get("categoria_espaco")

        df_free = get_free_rooms_by_interval(
            data_pesquisa=str(search_date),
            hora_inicio=search_hour_ini,
            hora_fim=search_hour_fim,
            escola=esc, departamento=dep, edificio=edi, categoria_espaco=cat,
        )
        total_rooms = get_filtered_rooms_count(
            escola=esc, edificio=edi, categoria_espaco=cat, departamento=dep
        )

        vazias_count       = len(df_free)
        ocupadas_count     = max(total_rooms - vazias_count, 0)
        tx_disponibilidade = round(pct(vazias_count, total_rooms), 1)

        k1, k2, k3, k4 = st.columns(4)
        with k1: render_kpi("Salas Vazias",     f"{vazias_count:,}", "🟢")
        with k2: render_kpi("Salas Ocupadas",   f"{ocupadas_count:,}", "🏢")
        with k3: render_kpi("Total de Espaços", f"{total_rooms:,}", "📐")
        with k4: render_kpi("Disponibilidade",  f"{tx_disponibilidade}%", "📊")

        render_spacer(1.5)
        data_pt = search_date.strftime("%d/%m/%Y")
        st.markdown(
            f"<h4 style='color:#1B2139;font-weight:700;'>"
            f"Salas livres para {data_pt} entre as {search_hour_ini:02d}:00 e as {search_hour_fim:02d}:00"
            f"</h4>",
            unsafe_allow_html=True,
        )

        if not df_free.empty:
            st.dataframe(
                df_free, use_container_width=True, hide_index=True,
                column_config={
                    "Edificio":  st.column_config.TextColumn("Edifício",      width="medium"),
                    "Sala":      st.column_config.TextColumn("Sala / Espaço", width="medium"),
                    "Categoria": st.column_config.TextColumn("Tipologia",     width="medium"),
                    "Escola":    st.column_config.TextColumn("Escola",        width="medium"),
                },
            )
            st.caption(
                f"💡 Foram encontradas {vazias_count} salas disponíveis "
                f"de um universo de {total_rooms} espaços visíveis."
            )
        else:
            st.warning(
                "⚠️ Não existem salas livres que cubram todo este intervalo "
                "de tempo com os filtros atuais."
            )