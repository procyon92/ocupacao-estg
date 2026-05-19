"""
pages.py — Módulo que define cada página/vista do Dashboard.
Cada função renderiza uma página completa no espaço principal.
"""
import streamlit as st
import pandas as pd
from data import (
    get_filtered_data,
    get_etl_quality_metrics,
    get_ocupacao_por_hora,
)
from plots import (
    chart_ocupacao_tempo,
    chart_ocupacao_edificio,
    chart_heatmap_ocupacao,
    chart_top_espacos,
    chart_tipo_atividade,
    chart_categoria_espaco,
)
from config import COLORS


# ═════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════
def _render_kpi(label: str, value: str, icon: str = ""):
    """Renderiza um card KPI com estilo premium."""
    st.markdown(f"""
    <div style="
        background: {COLORS['kpi_bg']};
        border-radius: 14px;
        padding: 1.3rem 1.5rem;
        height: 110px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        border: 1px solid #E8EDF5;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    ">
        <span style="
            color: {COLORS['kpi_label']};
            font-size: 0.82rem;
            font-weight: 500;
            letter-spacing: 0.02em;
        ">{icon} {label}</span>
        <span style="
            color: {COLORS['kpi_value']};
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.2;
            margin-top: 0.3rem;
        ">{value}</span>
    </div>
    """, unsafe_allow_html=True)


def _render_status_badge(status: str) -> str:
    """Retorna HTML de um badge de estado colorido."""
    color_map = {
        "Confirmada": (COLORS["badge_green"], COLORS["badge_green_text"]),
        "Pendente": (COLORS["badge_yellow"], COLORS["badge_yellow_text"]),
    }
    bg, text = color_map.get(status, (COLORS["badge_yellow"], COLORS["badge_yellow_text"]))
    return f'<span style="background:{bg};color:{text};padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:600;">{status}</span>'


def _render_quality_card(label: str, value: int, color: str):
    """Renderiza card de métrica de qualidade ETL."""
    st.markdown(f"""
    <div style="
        background: {color};
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
    ">
        <span style="color:#475569;font-size:0.78rem;font-weight:500;">{label}</span>
        <div style="font-size:1.6rem;font-weight:700;color:#1B2139;margin-top:2px;">
            {value:,}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════
# PÁGINA 1: DASHBOARD PRINCIPAL
# ═════════════════════════════════════════════════════════════════════
def page_dashboard(filters: dict):
    """Página principal — KPIs, linha temporal, donut, tabela, qualidade."""

    # ── Obter dados filtrados ────────────────────────────────────────
    df = get_filtered_data(**filters)

    # ── KPIs Row ─────────────────────────────────────────────────────
    total_ocupacoes = len(df)
    espacos_ativos = df["Nome_Espaco"].nunique() if not df.empty else 0

    # Taxa de ocupação: rácio real de alocação
    # (minutos usados) / (espaços x dias letivos x 480 min/dia)
    if not df.empty:
        total_min = df["Duracao_Minutos"].sum()
        espacos = df["Nome_Espaco"].nunique()
        dias = df["DataCompleta"].nunique()
        capacidade_disponivel = espacos * dias * 480
        taxa_ocupacao = min(round((total_min / max(capacidade_disponivel, 1)) * 100), 100) if capacidade_disponivel > 0 else 0
    else:
        taxa_ocupacao = 0

    # Tempo médio
    if not df.empty and "Duracao_Minutos" in df.columns:
        avg_min = df["Duracao_Minutos"].mean()
        horas = int(avg_min // 60)
        minutos = int(avg_min % 60)
        tempo_medio = f"{horas}h{minutos:02d}"
    else:
        tempo_medio = "—"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_kpi("Total de Ocupações", f"{total_ocupacoes:,}")
    with k2:
        _render_kpi("Espaços Ativos", str(espacos_ativos))
    with k3:
        _render_kpi("Taxa Ocupação", f"{taxa_ocupacao}%")
    with k4:
        _render_kpi("Tempo Médio", tempo_medio)

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # ── Charts Row 1: Line + Donut ───────────────────────────────────
    col_line, col_donut = st.columns([2, 1])

    with col_line:
        with st.container():
            # Granularity selector
            granularity = st.radio(
                "Granularidade",
                ["Diário", "Semanal", "Mensal"],
                horizontal=True,
                label_visibility="collapsed",
                key="gran_tempo",
            )
            fig_line = chart_ocupacao_tempo(df, granularity)
            st.plotly_chart(fig_line, use_container_width=True, key="chart_line")

    with col_donut:
        fig_donut = chart_ocupacao_edificio(df)
        st.plotly_chart(fig_donut, use_container_width=True, key="chart_donut")

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    # ── Row 2: Tabela Ocupações Recentes + ETL Quality ───────────────
    col_table, col_quality = st.columns([2, 1])

    with col_table:
        st.markdown(
            "<h4 style='color:#1B2139;font-weight:700;margin-bottom:0.8rem;'>Ocupações Recentes</h4>",
            unsafe_allow_html=True,
        )
        if not df.empty:
            recent = (
                df.sort_values("DataCompleta", ascending=False)
                .head(15)
                [["ID_Ocupacao", "Nome_Espaco", "Edificio", "Estado", "Designacao_Atividade", "DataCompleta"]]
                .copy()
            )
            recent["DataCompleta"] = recent["DataCompleta"].dt.strftime("%d/%m/%Y")
            recent.columns = ["ID", "Espaço", "Edifício", "Estado", "Tipo", "Data"]
            st.dataframe(
                recent,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config={
                    "ID": st.column_config.TextColumn("ID", width="small"),
                    "Espaço": st.column_config.TextColumn("Espaço", width="medium"),
                    "Edifício": st.column_config.TextColumn("Edifício", width="medium"),
                    "Estado": st.column_config.TextColumn("Estado", width="small"),
                    "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                    "Data": st.column_config.TextColumn("Data", width="small"),
                },
            )
        else:
            st.info("Sem dados para os filtros selecionados.")

    with col_quality:
        st.markdown(
            "<h4 style='color:#1B2139;font-weight:700;margin-bottom:0.8rem;'>ETL / Qualidade Dados</h4>",
            unsafe_allow_html=True,
        )
        metrics = get_etl_quality_metrics()
        _render_quality_card("Registos carregados", metrics["total"], COLORS["quality_green"])
        _render_quality_card("Registos válidos", metrics["valid"], COLORS["quality_yellow"])
        _render_quality_card("Erros", metrics["errors"], COLORS["quality_red"])


# ═════════════════════════════════════════════════════════════════════
# PÁGINA 2: OCUPAÇÃO (Heatmap + Top Espaços)
# ═════════════════════════════════════════════════════════════════════
def page_ocupacao(filters: dict):
    """Página de análise detalhada de ocupação."""
    st.markdown(
        "<h2 style='color:#1B2139;font-weight:700;'>Análise de Ocupação</h2>",
        unsafe_allow_html=True,
    )

    df = get_filtered_data(**filters)

    # KPIs contextuais
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_kpi("Total Ocupações", f"{len(df):,}", "📋")
    with k2:
        presencas = int(df["Numero_Presencas"].sum()) if not df.empty else 0
        _render_kpi("Total Presenças", f"{presencas:,}", "👥")
    with k3:
        dur_total = int(df["Duracao_Minutos"].sum()) if not df.empty else 0
        _render_kpi("Horas Totais", f"{dur_total // 60:,}h", "⏱️")
    with k4:
        online = int(df["is_online"].sum()) if not df.empty else 0
        _render_kpi("Sessões Online", f"{online:,}", "💻")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # Heatmap
    df_heatmap = get_ocupacao_por_hora(
        ano_letivo=filters.get("ano_letivo"),
        semestre=filters.get("semestre"),
        departamento=filters.get("departamento"),
    )
    fig_heat = chart_heatmap_ocupacao(df_heatmap)
    st.plotly_chart(fig_heat, use_container_width=True, key="chart_heatmap")

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    # Top espaços + Tipo atividade
    col1, col2 = st.columns(2)
    with col1:
        fig_top = chart_top_espacos(df)
        st.plotly_chart(fig_top, use_container_width=True, key="chart_top_espacos")
    with col2:
        fig_tipo = chart_tipo_atividade(df)
        st.plotly_chart(fig_tipo, use_container_width=True, key="chart_tipo_atividade")


# ═════════════════════════════════════════════════════════════════════
# PÁGINA 3: ESPAÇOS (Detalhe por Espaço/Edifício)
# ═════════════════════════════════════════════════════════════════════
def page_espacos(filters: dict):
    """Página de análise de espaços."""
    st.markdown(
        "<h2 style='color:#1B2139;font-weight:700;'>Análise de Espaços</h2>",
        unsafe_allow_html=True,
    )

    df = get_filtered_data(**filters)

    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    # KPIs
    k1, k2, k3 = st.columns(3)
    with k1:
        _render_kpi("Edifícios", str(df["Edificio"].nunique()), "🏢")
    with k2:
        _render_kpi("Espaços Únicos", str(df["Nome_Espaco"].nunique()), "🚪")
    with k3:
        _render_kpi("Categorias", str(df["Categoria_Espaco"].nunique()), "📐")

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    # Categoria pie + Building breakdown
    col1, col2 = st.columns(2)
    with col1:
        fig_cat = chart_categoria_espaco(df)
        st.plotly_chart(fig_cat, use_container_width=True, key="chart_cat_espaco")
    with col2:
        fig_edf = chart_ocupacao_edificio(df)
        st.plotly_chart(fig_edf, use_container_width=True, key="chart_edf_espaco")

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    # Tabela detalhada por espaço
    st.markdown(
        "<h4 style='color:#1B2139;font-weight:700;'>Resumo por Espaço</h4>",
        unsafe_allow_html=True,
    )
    summary = (
        df.groupby(["Edificio", "Nome_Espaco", "Categoria_Espaco"])
        .agg(
            Ocupacoes=("ID_Ocupacao", "count"),
            Duracao_Media=("Duracao_Minutos", "mean"),
            Presencas_Total=("Numero_Presencas", "sum"),
        )
        .reset_index()
        .sort_values("Ocupacoes", ascending=False)
        .head(30)
    )
    summary["Duracao_Media"] = summary["Duracao_Media"].round(0).astype(int).astype(str) + " min"
    summary.columns = ["Edifício", "Espaço", "Categoria", "Ocupações", "Duração Média", "Presenças"]
    st.dataframe(summary, use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════
# PÁGINA 4: RELATÓRIOS (Exportação)
# ═════════════════════════════════════════════════════════════════════
def page_relatorios(filters: dict):
    """Página de exportação de relatórios."""
    st.markdown(
        "<h2 style='color:#1B2139;font-weight:700;'>Relatórios</h2>",
        unsafe_allow_html=True,
    )

    df = get_filtered_data(**filters)

    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    st.markdown(
        "<p style='color:#64748B;margin-bottom:1.5rem;'>Exportação de dados filtrados em formato CSV.</p>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📄 Dados Completos")
        st.markdown(f"**{len(df):,}** registos com os filtros atuais.")
        csv_full = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Exportar CSV Completo",
            csv_full,
            file_name="ocupacao_dados_completos.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        st.markdown("#### 📊 Resumo por Edifício")
        summary_edf = (
            df.groupby("Edificio")
            .agg(
                Ocupacoes=("ID_Ocupacao", "count"),
                Duracao_Total=("Duracao_Minutos", "sum"),
                Presencas=("Numero_Presencas", "sum"),
                Espacos_Unicos=("Nome_Espaco", "nunique"),
            )
            .reset_index()
            .sort_values("Ocupacoes", ascending=False)
        )
        csv_summary = summary_edf.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Exportar Resumo CSV",
            csv_summary,
            file_name="ocupacao_resumo_edificio.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # Preview
    st.markdown("#### Pré-visualização")
    st.dataframe(
        df.head(50),
        use_container_width=True,
        hide_index=True,
    )


# ═════════════════════════════════════════════════════════════════════
# PÁGINA 5: ETL / LOGS
# ═════════════════════════════════════════════════════════════════════
def page_etl_logs(filters: dict):
    """Página de monitorização do ETL e qualidade dos dados."""
    st.markdown(
        "<h2 style='color:#1B2139;font-weight:700;'>ETL / Logs</h2>",
        unsafe_allow_html=True,
    )

    metrics = get_etl_quality_metrics()

    # KPIs de qualidade
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_kpi("Total Carregados", f"{metrics['total']:,}", "📦")
    with k2:
        _render_kpi("Válidos", f"{metrics['valid']:,}", "✅")
    with k3:
        _render_kpi("Com Erros", f"{metrics['errors']:,}", "⚠️")
    with k4:
        pct = round(metrics["valid"] / max(metrics["total"], 1) * 100, 1)
        _render_kpi("Taxa Qualidade", f"{pct}%", "🎯")

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # Distribuição de SKs
    df = get_filtered_data(**filters)
    if not df.empty:
        st.markdown("#### Cobertura de Chaves Dimensionais")

        sk_cols = {
            "Edifício": "Edificio",
            "UC": "Designacao_UC",
            "Responsável": "Docente_Responsavel",
            "Estado": "Estado",
            "Turno": "Designacao_Turno",
        }
        coverage_data = []
        for label, col in sk_cols.items():
            if col in df.columns:
                total = len(df)
                filled = (df[col] != "N/D").sum()
                pct = round(filled / total * 100, 1)
                coverage_data.append({"Dimensão": label, "Preenchidos": filled, "Total": total, "Cobertura": f"{pct}%"})

        if coverage_data:
            st.dataframe(pd.DataFrame(coverage_data), use_container_width=True, hide_index=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;font-size:0.85rem;'>Dados atualizados em tempo real a partir do Data Warehouse MySQL.</p>",
        unsafe_allow_html=True,
    )
