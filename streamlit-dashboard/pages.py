"""
pages.py — V2 profile renderers for the ESTG Dashboard.
Profile A: General ESTG Overview.  Profile B: Computer Labs.
"""
import streamlit as st
import pandas as pd
from data import get_filtered_data, get_space_detail_data, get_espacos, get_etl_quality_metrics, get_ghost_sessions_trend, get_unmapped_records_count, get_raw_anomalies
from plots import (
    chart_ocupacao_tempo, chart_ocupacao_edificio, chart_heatmap_ocupacao,
    chart_top_espacos, chart_bottom_espacos, chart_tipo_atividade,
    chart_categoria_espaco, chart_period_of_day, chart_single_space_heatmap,
    chart_anomalies_trend, chart_monthly_calendar,
)
from config import COLORS


def _render_kpi(label: str, value: str, icon: str = ""):
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


def _render_quality_card(label: str, value: int, color: str):
    st.markdown(f"""
    <div style="background:{color};border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.6rem;">
        <span style="color:#475569;font-size:0.78rem;font-weight:500;">{label}</span>
        <div style="font-size:1.6rem;font-weight:700;color:#1B2139;margin-top:2px;">{value:,}</div>
    </div>
    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════
# PROFILE A — General ESTG Overview
# ═════════════════════════════════════════════════════════════════════
def render_profile_a_general(filters: dict):
    st.markdown("<h2 style='color:#1B2139;font-weight:700;'>Visão Geral — ESTG</h2>", unsafe_allow_html=True)

    df = get_filtered_data(**filters)

    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    # ── 6 KPIs ───────────────────────────────────────────────────────
    total_ocup = len(df)
    espacos_ativos = df["Nome_Espaco"].nunique()
    total_min = df["Duracao_Minutos"].sum()
    espacos = df["Nome_Espaco"].nunique()
    dias = df["DataCompleta"].nunique()
    cap_disponivel = espacos * dias * 480
    taxa_ocup = min(round((total_min / max(cap_disponivel, 1)) * 100), 100) if cap_disponivel > 0 else 0
    avg_min = df["Duracao_Minutos"].mean()
    tempo_medio = f"{int(avg_min//60)}h{int(avg_min%60):02d}" if not df.empty else "—"
    total_pres = int(df["Numero_Presencas"].sum()) if not df.empty else 0
    ghost_pct = round((df["Numero_Presencas"] == 0).sum() / len(df) * 100, 1) if not df.empty else 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: _render_kpi("Ocupações", f"{total_ocup:,}", "📋")
    with k2: _render_kpi("Espaços Ativos", str(espacos_ativos), "🏢")
    with k3: _render_kpi("Taxa Ocupação", f"{taxa_ocup}%", "📊")
    with k4: _render_kpi("Tempo Médio", tempo_medio, "⏱️")
    with k5: _render_kpi("Presenças", f"{total_pres:,}", "👥")
    with k6: _render_kpi("Ghost %", f"{ghost_pct}%", "👻")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # ── Top / Bottom N with slider ───────────────────────────────────
    st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Top / Bottom Espaços</h4>", unsafe_allow_html=True)
    top_n = st.slider("Número de espaços", min_value=5, max_value=30, value=10, key="v2_top_n")
    col_top, col_bottom = st.columns(2)
    with col_top:
        fig_top = chart_top_espacos(df, top_n)
        st.plotly_chart(fig_top, use_container_width=True, key="chart_top")
    with col_bottom:
        fig_bot = chart_bottom_espacos(df, top_n)
        st.plotly_chart(fig_bot, use_container_width=True, key="chart_bottom")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Time Analysis: Trend + Period of Day ────────────────────────
    st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Análise Temporal</h4>", unsafe_allow_html=True)
    col_trend, col_period = st.columns([2, 1])
    with col_trend:
        granularity = st.radio("Granularidade", ["Diário", "Semanal", "Mensal"], horizontal=True,
                               label_visibility="collapsed", key="v2_gran_tempo")
        fig_line = chart_ocupacao_tempo(df, granularity)
        st.plotly_chart(fig_line, use_container_width=True, key="chart_trend")
    with col_period:
        fig_period = chart_period_of_day(df)
        st.plotly_chart(fig_period, use_container_width=True, key="chart_period")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Weekday × Hour Heatmap + Building Donut ──────────────────────
    col_heat, col_donut = st.columns([2, 1])
    with col_heat:
        df_heat = df.groupby(["DiaSemana", "Hora_Inicio"]).size().reset_index(name="Total_Ocupacoes")
        fig_heat = chart_heatmap_ocupacao(df_heat)
        st.plotly_chart(fig_heat, use_container_width=True, key="chart_heat_v2")
    with col_donut:
        fig_donut = chart_ocupacao_edificio(df)
        st.plotly_chart(fig_donut, use_container_width=True, key="chart_donut_v2")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Category + Activity Type ─────────────────────────────────────
    col_cat, col_atv = st.columns(2)
    with col_cat:
        fig_cat = chart_categoria_espaco(df)
        st.plotly_chart(fig_cat, use_container_width=True, key="chart_cat_v2")
    with col_atv:
        fig_atv = chart_tipo_atividade(df)
        st.plotly_chart(fig_atv, use_container_width=True, key="chart_atv_v2")


# ═════════════════════════════════════════════════════════════════════
# PROFILE B — Computer Labs Dashboard
# ═════════════════════════════════════════════════════════════════════
def render_profile_b_labs(filters: dict):
    st.markdown("<h2 style='color:#1B2139;font-weight:700;'>Laboratórios de Informática</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748B;font-size:0.85rem;'>Filtro automático: Categoria = Laboratório. "
                "Os restantes filtros podem ser ajustados livremente.</p>", unsafe_allow_html=True)

    # Force categoria_espaco = "Laboratório"
    filters["only_labs"] = True
    df = get_filtered_data(**filters)

    if df.empty:
        st.info("Sem dados de laboratório para os filtros selecionados.")
        return

    # ── Lab KPIs ─────────────────────────────────────────────────────
    total_ocup = len(df)
    labs_unicos = df["Nome_Espaco"].nunique() if not df.empty else 0
    total_min = int(df["Duracao_Minutos"].sum()) if not df.empty else 0
    total_pres = int(df["Numero_Presencas"].sum()) if not df.empty else 0
    avg_pres = round(total_pres / max(total_ocup, 1), 1)
    ghost_count = int((df["Numero_Presencas"] == 0).sum()) if not df.empty else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: _render_kpi("Sessões", f"{total_ocup:,}", "🔬")
    with k2: _render_kpi("Laboratórios", str(labs_unicos), "🖥️")
    with k3: _render_kpi("Horas Totais", f"{total_min//60:,}h", "⏱️")
    with k4: _render_kpi("Média Presenças", str(avg_pres), "👥")
    with k5: _render_kpi("Sessões Vazias", f"{ghost_count:,}", "👻")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # ── Occupancy by Weekday × Hour ──────────────────────────────────
    col_heat, col_period = st.columns([2, 1])
    with col_heat:
        df_heat = df.groupby(["DiaSemana", "Hora_Inicio"]).size().reset_index(name="Total_Ocupacoes")
        fig_heat = chart_heatmap_ocupacao(df_heat)
        st.plotly_chart(fig_heat, use_container_width=True, key="lab_chart_heat")
    with col_period:
        fig_period = chart_period_of_day(df)
        st.plotly_chart(fig_period, use_container_width=True, key="lab_chart_period")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Usage Type Breakdown + Top / Bottom Labs ──────────────────────
    top_labs = st.slider("Top / Bottom N Laboratórios", 5, 30, 10, key="v2_lab_top_n")
    col_tipo, col_top, col_bottom = st.columns([1, 1, 1])
    with col_tipo:
        fig_tipo = chart_tipo_atividade(df)
        st.plotly_chart(fig_tipo, use_container_width=True, key="lab_chart_tipo")
    with col_top:
        fig_top = chart_top_espacos(df, top_labs)
        st.plotly_chart(fig_top, use_container_width=True, key="lab_chart_top")
    with col_bottom:
        fig_bottom = chart_bottom_espacos(df, top_labs)
        st.plotly_chart(fig_bottom, use_container_width=True, key="lab_chart_bottom")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Lab Capacity Management Table ────────────────────────────────
    st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Gestão de Capacidade — Laboratórios</h4>", unsafe_allow_html=True)
    summary = (
        df.groupby(["Edificio", "Nome_Espaco"])
        .agg(
            Sessoes=("ID_Ocupacao", "count"),
            Horas_Total=("Duracao_Minutos", "sum"),
            Media_Presencas=("Numero_Presencas", "mean"),
            Presencas_Total=("Numero_Presencas", "sum"),
        )
        .reset_index()
        .sort_values("Sessoes", ascending=False)
    )
    summary["Horas_Total"] = (summary["Horas_Total"] / 60).round(0).astype(int)
    summary["Media_Presencas"] = summary["Media_Presencas"].round(1)
    summary["Carga"] = summary["Sessoes"].apply(
        lambda x: "🔴 Alta" if x > summary["Sessoes"].quantile(0.75)
        else "🟡 Média" if x > summary["Sessoes"].quantile(0.5)
        else "🟢 Baixa"
    )
    summary.columns = ["Edifício", "Laboratório", "Sessões", "Horas Totais", "Média Presenças", "Presenças Total", "Carga"]
    st.dataframe(summary, use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════
# PROFILE C — Space Detail (placeholder for Phase 2)
# ═════════════════════════════════════════════════════════════════════
def render_profile_c_spaces(filters: dict):
    st.markdown("<h2 style='color:#1B2139;font-weight:700;'>Detalhe de Espaço</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748B;font-size:0.85rem;'>Selecione um espaço para ver a sua ocupação detalhada.</p>",
                unsafe_allow_html=True)

    # ── Room selector — pre-fill from global cascading filters ──────
    global_espaco = filters.get("espaco")
    all_rooms = get_espacos(
        edificio=filters.get("edificio"),
        categoria=filters.get("categoria_espaco"),
    )
    room_opts = ["— Selecione um espaço —"] + all_rooms
    idx = 0
    if global_espaco and global_espaco in all_rooms:
        idx = room_opts.index(global_espaco)
    selected_room = st.selectbox(
        "Espaço",
        room_opts,
        index=idx,
        key="v2_profile_c_room",
    )

    if selected_room == "— Selecione um espaço —":
        st.info("Escolha um espaço para visualizar os detalhes.")
        return

    # ── Fetch detail data for this single space ─────────────────────
    df = get_space_detail_data(
        space_name=selected_room,
        ano_escolar=filters.get("ano_letivo"),
        semestre=filters.get("semestre"),
    )

    if df.empty:
        st.warning("Nenhuma ocupação registada para este espaço com os filtros atuais.")
        return

    # ── Row 1: 4 KPIs ───────────────────────────────────────────────
    total_hours = int(df["Duracao_Minutos"].sum() / 60)
    avg_class_size = round(df["Numero_Presencas"].mean(), 1) if not df.empty else 0
    ghost_count = int((df["Numero_Presencas"] == 0).sum()) if not df.empty else 0

    # Utilization rate: unique days the room is used × 8h (480 min) per day
    unique_days = df["DataCompleta"].nunique()
    total_available_min = unique_days * 480
    used_min = df["Duracao_Minutos"].sum()
    util_rate = min(round(used_min / max(total_available_min, 1) * 100, 1), 100)

    k1, k2, k3, k4 = st.columns(4)
    with k1: _render_kpi("Horas Agendadas", f"{total_hours:,}h", "⏱️")
    with k2: _render_kpi("Média Presenças", str(avg_class_size), "👥")
    with k3: _render_kpi("Taxa Utilização", f"{util_rate}%", "📊")
    with k4: _render_kpi("Sessões Vazias", f"{ghost_count:,}", "👻")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # ── Row 2: Weekly heatmap + Monthly Calendar (side by side) ─────
    st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Ocupação Semanal e Calendário Mensal</h4>", unsafe_allow_html=True)
    col_heatmap, col_calendar = st.columns([1, 1])
    with col_heatmap:
        fig_heat = chart_single_space_heatmap(df)
        st.plotly_chart(fig_heat, use_container_width=True, key="chart_space_heat")
    with col_calendar:
        cal_col1, cal_col2 = st.columns(2)
        with cal_col1:
            available_years = sorted(df["DataCompleta"].dt.year.unique(), reverse=True)
            cal_year = st.selectbox("Ano", available_years, key="v2_cal_year")
        with cal_col2:
            cal_month = st.selectbox("Mês", range(1, 13),
                                     format_func=lambda m: ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                                                            "Jul", "Ago", "Set", "Out", "Nov", "Dez"][m-1],
                                     index=0, key="v2_cal_month")
        fig_cal = chart_monthly_calendar(df, int(cal_year), int(cal_month))
        st.plotly_chart(fig_cal, use_container_width=True, key="chart_month_cal")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Row 3: Operational timetable ────────────────────────────────
    st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Horário Analítico</h4>", unsafe_allow_html=True)

    timetable = df.sort_values(["DataCompleta", "Hora_Inicio", "Minuto_Inicio"]).copy()
    timetable["Data"] = timetable["DataCompleta"].dt.strftime("%d/%m/%Y")
    timetable["Início"] = timetable.apply(lambda r: f"{int(r['Hora_Inicio']):02d}:{int(r['Minuto_Inicio']):02d}", axis=1)
    timetable["Fim"] = timetable.apply(lambda r: f"{int(r['Hora_Fim']):02d}:{int(r['Minuto_Fim']):02d}", axis=1)
    timetable["Duração"] = timetable["Duracao_Minutos"].apply(lambda m: f"{m} min")
    timetable["Presenças"] = timetable["Numero_Presencas"].astype(int)

    display = timetable[[
        "Data", "DiaSemana", "Início", "Fim", "Duração",
        "Designacao_UC", "Nome_Curso", "Designacao_Atividade",
        "Docente_Responsavel", "Presenças", "Estado",
    ]].rename(columns={
        "DiaSemana": "Dia",
        "Designacao_UC": "UC",
        "Nome_Curso": "Curso",
        "Designacao_Atividade": "Atividade",
        "Docente_Responsavel": "Docente",
    })

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.TextColumn("Data", width="small"),
            "Dia": st.column_config.TextColumn("Dia", width="small"),
            "Início": st.column_config.TextColumn("Início", width="small"),
            "Fim": st.column_config.TextColumn("Fim", width="small"),
            "Duração": st.column_config.TextColumn("Duração", width="small"),
            "UC": st.column_config.TextColumn("UC", width="medium"),
            "Curso": st.column_config.TextColumn("Curso", width="medium"),
            "Atividade": st.column_config.TextColumn("Atividade", width="small"),
            "Docente": st.column_config.TextColumn("Docente", width="medium"),
            "Presenças": st.column_config.NumberColumn("Presenças", width="small"),
            "Estado": st.column_config.TextColumn("Estado", width="small"),
        },
    )


# ═════════════════════════════════════════════════════════════════════
# PROFILE D — Data Quality Audit
# ═════════════════════════════════════════════════════════════════════
def render_profile_d_quality(filters: dict):
    st.markdown("<h2 style='color:#1B2139;font-weight:700;'>Qualidade dos Dados / ETL</h2>", unsafe_allow_html=True)

    metrics = get_etl_quality_metrics()
    ghost_trend = get_ghost_sessions_trend(
        ano_escolar=filters.get("ano_letivo"),
        semestre=filters.get("semestre"),
    )
    unmapped = get_unmapped_records_count()
    total_ghost = unmapped.get("Ghost Sessions (0 Presenças)", 0)
    total_unmapped_uc = unmapped.get("UC Sem Mapeamento", 0)
    total_unmapped_curso = unmapped.get("Curso Sem Mapeamento", 0)

    # ── Row 1: KPIs ────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: _render_kpi("Total Carregados", f"{metrics['total']:,}", "📦")
    with k2: _render_kpi("Válidos", f"{metrics['valid']:,}", "✅")
    with k3: _render_kpi("Com Erros", f"{metrics['errors']:,}", "⚠️")
    with k4:
        pct = round(metrics["valid"] / max(metrics["total"], 1) * 100, 1)
        _render_kpi("Qualidade", f"{pct}%", "🎯")
    with k5: _render_kpi("Ghost Sessions", f"{total_ghost:,}", "👻")
    with k6: _render_kpi("UC/Curso N/D", f"{total_unmapped_uc + total_unmapped_curso:,}", "🚫")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # ── Row 2: Anomalies Trend Chart ────────────────────────────────
    st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Evolução de Anomalias</h4>", unsafe_allow_html=True)
    fig_trend = chart_anomalies_trend(ghost_trend)
    st.plotly_chart(fig_trend, use_container_width=True, key="chart_ghost_trend")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Row 3: Coverage table ──────────────────────────────────────
    df = get_filtered_data(**filters)
    if not df.empty:
        st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Cobertura de Chaves Dimensionais</h4>", unsafe_allow_html=True)
        sk_cols = {
            "Edifício": "Edificio", "Espaço": "Nome_Espaco", "Categoria": "Categoria_Espaco",
            "UC": "Designacao_UC", "Ciclo Estudo": "Ciclo_Estudo", "Curso": "Nome_Curso",
            "Tipo Atividade": "Designacao_Atividade", "Responsável": "Docente_Responsavel",
            "Estado": "Estado", "Turno": "Designacao_Turno",
        }
        coverage = []
        for label, col in sk_cols.items():
            if col in df.columns:
                total = len(df)
                filled = (df[col] != "N/D").sum()
                pct_cov = round(filled / total * 100, 1)
                coverage.append({"Dimensão": label, "Preenchidos": filled, "Total": total, "Cobertura": f"{pct_cov}%"})
        if coverage:
            st.dataframe(pd.DataFrame(coverage), use_container_width=True, hide_index=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Row 4: Raw Anomalies Audit Log ─────────────────────────────
    st.markdown("<h4 style='color:#1B2139;font-weight:700;'>Registo de Anomalias (Auditoria)</h4>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748B;font-size:0.85rem;'>Últimos registos com problemas de qualidade — ghost sessions, UC sem mapeamento, curso N/D ou responsável indefinido.</p>",
                unsafe_allow_html=True)

    anomalies_df = get_raw_anomalies(limit=100)
    if not anomalies_df.empty:
        display = anomalies_df.copy()
        if "DataCompleta" in display.columns:
            display["Data"] = display["DataCompleta"].dt.strftime("%d/%m/%Y")
        display["Início"] = display.apply(lambda r: f"{int(r['Hora_Inicio']):02d}h", axis=1)
        display["Fim"] = display.apply(lambda r: f"{int(r['Hora_Fim']):02d}h", axis=1)

        # Build a combined anomaly flag column
        def _combine_flags(row):
            flags = []
            if row.get("Ghost_Flag"): flags.append("👻 Ghost")
            if row.get("UC_Flag"): flags.append("📚 UC N/D")
            if row.get("Curso_Flag"): flags.append("🎓 Curso N/D")
            if row.get("Resp_Flag"): flags.append("👤 Resp. N/D")
            return " | ".join(flags) if flags else "—"

        display["Anomalias"] = display.apply(_combine_flags, axis=1)

        audit_cols = ["Data", "DiaSemana", "Início", "Fim", "Edificio", "Nome_Espaco",
                      "Designacao_UC", "Nome_Curso", "Docente_Responsavel",
                      "Duracao_Minutos", "Numero_Presencas", "Anomalias"]
        audit_cols = [c for c in audit_cols if c in display.columns]

        st.dataframe(
            display[audit_cols].rename(columns={
                "DiaSemana": "Dia",
                "Nome_Espaco": "Espaço",
                "Designacao_UC": "UC",
                "Nome_Curso": "Curso",
                "Docente_Responsavel": "Docente",
                "Duracao_Minutos": "Dur. (min)",
                "Numero_Presencas": "Presenças",
            }),
            use_container_width=True,
            hide_index=True,
            height=400,
        )
    else:
        st.success("Nenhuma anomalia encontrada nos registos atuais.")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8;font-size:0.85rem;'>Dados do Data Warehouse MySQL. Anomalias atualizadas a cada 5 minutos.</p>", unsafe_allow_html=True)