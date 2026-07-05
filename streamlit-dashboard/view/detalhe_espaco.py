from __future__ import annotations
import streamlit as st
from models import Filters
from view.base import BaseProfile
from queries import get_dados_detalhe_espaco, get_espacos
from transforms import normalizar_dataframe
from components import render_kpi, render_spacer, render_cabecalho_seccao
from utils import clamp, pct
from config import DAILY_CAPACITY_MINUTES, PLOTLY_CONFIG, Omisso, MESES_PT
from plots import chart_heatmap_espaco_unico, chart_calendario_mensal
from calendar_chart import render_calendario_horario
from view.tooltips import TAXA_UTILIZACAO, GHOST


class DetalheEspacoProfile(BaseProfile):
    def render(self, filters: Filters) -> None:
        self._h2("Detalhe de Espaço")
        self._subtitle("Selecione um espaço para ver a sua ocupação detalhada.")

        all_rooms = get_espacos(
            edificio=filters.get("edificio"),
            categoria=filters.get("categoria_espaco"),
            departamento=filters.get("departamento"),
        )
        room_opts     = [Omisso.NO_ROOM] + all_rooms
        global_espaco = filters.get("espaco")
        idx = room_opts.index(global_espaco) if global_espaco in room_opts else 0

        selected_room = st.selectbox("Espaço", room_opts, index=idx, key="profile_c_room")
        if selected_room == Omisso.NO_ROOM:
            return self._empty("Escolha um espaço para visualizar os detalhes.")

        df = normalizar_dataframe(
            get_dados_detalhe_espaco(
                space_name=selected_room,
                ano_escolar=filters.get("ano_letivo"),
                semestre=filters.get("semestre"),
                semana_escolar=filters.get("semana_escolar"),
            )
        )

        if df.empty:
            return self._empty("Nenhuma ocupação registada para este espaço com os filtros atuais.")

        total_hours    = int(df["Duracao_Minutos"].sum() / 60)
        avg_class_size = round(df["Numero_Presencas"].mean(), 1)
        ghost_count    = int((df["Numero_Presencas"] == 0).sum())
        unique_days    = df["DataCompleta"].nunique()
        util_rate      = clamp(pct(df["Duracao_Minutos"].sum(), unique_days * DAILY_CAPACITY_MINUTES))

        k1, k2, k3, k4 = st.columns(4)
        with k1: render_kpi("Horas Agendadas", f"{total_hours:,}h", "⏱️")
        with k2: render_kpi("Média Presenças", str(avg_class_size), "👥")
        with k3: render_kpi("Taxa Utilização", f"{util_rate}%", "📊", TAXA_UTILIZACAO)
        with k4: render_kpi("Sessões Vazias",  f"{ghost_count:,}", "👻", GHOST)

        render_spacer(1.2)
        render_cabecalho_seccao("Ocupação Semanal e Calendário Mensal")
        col_heatmap, col_calendar = st.columns(2)
        with col_heatmap:
            st.plotly_chart(chart_heatmap_espaco_unico(df),
                            use_container_width=True, key="chart_space_heat", config= PLOTLY_CONFIG)
        with col_calendar:
            c1, c2 = st.columns(2)
            with c1:
                available_years = sorted(df["DataCompleta"].dt.year.unique(), reverse=True)
                cal_year = st.selectbox("Ano", available_years, key="cal_year")
            with c2:
                cal_month = st.selectbox(
                    "Mês", range(1, 13),
                    format_func=lambda m: MESES_PT[m],
                    index=0, key="cal_month",
                )
            st.plotly_chart(chart_calendario_mensal(df, int(cal_year), int(cal_month)),
                            use_container_width=True, key="chart_month_cal", config= PLOTLY_CONFIG)

        render_spacer()
        render_cabecalho_seccao("Calendário de Horários")
        filtered_df = render_calendario_horario(df)

        render_spacer()
        render_cabecalho_seccao("Horário Analítico")
        # Usa o subset filtrado pelo calendário se existir, senão usa tudo
        timetable_df = filtered_df if (filtered_df is not None and not filtered_df.empty) else df
        timetable = timetable_df.sort_values(
            ["DataCompleta", "Hora_Inicio", "Minuto_Inicio"]
        ).copy()
        timetable["Data"]      = timetable["DataCompleta"].dt.strftime("%d/%m/%Y")
        timetable["Início"]    = timetable.apply(
            lambda r: f"{int(r['Hora_Inicio']):02d}:{int(r['Minuto_Inicio']):02d}", axis=1
        )
        timetable["Fim"]       = timetable.apply(
            lambda r: f"{int(r['Hora_Fim']):02d}:{int(r['Minuto_Fim']):02d}", axis=1
        )
        timetable["Duração"]   = timetable["Duracao_Minutos"].apply(lambda m: f"{m} min")
        timetable["Presenças"] = timetable["Numero_Presencas"].astype(int)

        display = timetable[[
            "Data", "DiaSemana", "Início", "Fim", "Duração",
            "Designacao_UC", "Nome_Curso", "Designacao_Atividade",
            "Docente_Responsavel", "Presenças", "Estado",
        ]].rename(columns={
            "DiaSemana": "Dia", "Designacao_UC": "UC", "Nome_Curso": "Curso",
            "Designacao_Atividade": "Atividade", "Docente_Responsavel": "Docente",
        })
        st.dataframe(display, use_container_width=True, hide_index=True,
            column_config={
                "Data":      st.column_config.TextColumn("Data",      width="small"),
                "Dia":       st.column_config.TextColumn("Dia",       width="small"),
                "Início":    st.column_config.TextColumn("Início",    width="small"),
                "Fim":       st.column_config.TextColumn("Fim",       width="small"),
                "Duração":   st.column_config.TextColumn("Duração",   width="small"),
                "UC":        st.column_config.TextColumn("UC",        width="medium"),
                "Curso":     st.column_config.TextColumn("Curso",     width="medium"),
                "Atividade": st.column_config.TextColumn("Atividade", width="small"),
                "Docente":   st.column_config.TextColumn("Docente",   width="medium"),
                "Presenças": st.column_config.NumberColumn("Presenças", width="small"),
                "Estado":    st.column_config.TextColumn("Estado", width="small"),
            },
        )