"""
plots.py — Módulo de visualizações Plotly para o Dashboard.
Cada função retorna um objeto go.Figure pronto a renderizar.
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from config import COLORS


def _base_layout(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    """Aplica estilo base consistente a todos os gráficos."""
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=16, color="#1B2139", family="Inter, sans-serif"),
            x=0.02,
            y=0.96,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#64748B", size=12),
        height=height,
        margin=dict(l=50, r=30, t=60, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=COLORS["chart_grid"],
        gridwidth=0.5,
        zeroline=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=COLORS["chart_grid"],
        gridwidth=0.5,
        zeroline=False,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────
# GRÁFICO 1: Ocupação ao Longo do Tempo (Line Chart)
# ─────────────────────────────────────────────────────────────────────
def chart_ocupacao_tempo(df: pd.DataFrame, granularity: str = "Diário") -> go.Figure:
    """
    Line chart com total de ocupações ao longo do tempo.
    Suporta granularidade Diário / Semanal / Mensal.
    """
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados disponíveis", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação ao longo do tempo")

    df = df.copy()

    if granularity == "Diário":
        grouped = df.groupby("DataCompleta").size().reset_index(name="Total")
        grouped = grouped.sort_values("DataCompleta")
        x_col = "DataCompleta"
    elif granularity == "Semanal":
        df["Semana"] = df["DataCompleta"].dt.to_period("W").apply(lambda r: r.start_time)
        grouped = df.groupby("Semana").size().reset_index(name="Total")
        grouped = grouped.sort_values("Semana")
        x_col = "Semana"
    else:  # Mensal
        df["Mes_Periodo"] = df["DataCompleta"].dt.to_period("M").apply(lambda r: r.start_time)
        grouped = df.groupby("Mes_Periodo").size().reset_index(name="Total")
        grouped = grouped.sort_values("Mes_Periodo")
        x_col = "Mes_Periodo"

    fig = go.Figure()

    # Area fill
    fig.add_trace(go.Scatter(
        x=grouped[x_col],
        y=grouped["Total"],
        fill="tozeroy",
        fillcolor="rgba(59, 99, 251, 0.08)",
        line=dict(color=COLORS["primary"], width=2.5, shape="spline"),
        mode="lines",
        name="Ocupações",
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Total: %{y:,.0f}<extra></extra>",
    ))

    fig = _base_layout(fig, "Ocupação ao longo do tempo", height=380)
    fig.update_xaxes(title_text="")
    fig.update_yaxes(title_text="Nº Ocupações")
    return fig


# ─────────────────────────────────────────────────────────────────────
# GRÁFICO 2: Ocupação por Edifício (Donut Chart)
# ─────────────────────────────────────────────────────────────────────
def chart_ocupacao_edificio(df: pd.DataFrame) -> go.Figure:
    """Donut chart com distribuição de ocupações por edifício."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação por Edifício")

    top = df[df["Edificio"] != "N/D"].groupby("Edificio").size().reset_index(name="Total")
    top = top.sort_values("Total", ascending=False)

    # Truncate labels for long building names
    top["Label"] = top["Edificio"].apply(
        lambda x: x[:25] + "…" if len(x) > 25 else x
    )

    # Agrupar edifícios com poucos registos como "Outros"
    if len(top) > 8:
        main = top.head(7)
        others = pd.DataFrame({
            "Edificio": ["Outros"],
            "Total": [top.iloc[7:]["Total"].sum()],
            "Label": ["Outros"],
        })
        top = pd.concat([main, others], ignore_index=True)

    fig = go.Figure(data=[go.Pie(
        labels=top["Label"],
        values=top["Total"],
        hole=0.55,
        marker=dict(colors=COLORS["donut_palette"][:len(top)]),
        textinfo="percent",
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>Total: %{value:,.0f}<br>%{percent}<extra></extra>",
        pull=[0.03 if i == 0 else 0 for i in range(len(top))],
    )])

    fig = _base_layout(fig, "Ocupação por Edifício", height=380)
    fig.update_layout(showlegend=True)
    fig.update_layout(
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=-0.1,
            font=dict(size=10),
        )
    )
    return fig


# ─────────────────────────────────────────────────────────────────────
# GRÁFICO 3: Heatmap Ocupação por Hora e Dia da Semana
# ─────────────────────────────────────────────────────────────────────
def chart_heatmap_ocupacao(df_heatmap: pd.DataFrame) -> go.Figure:
    """Heatmap de intensidade de ocupação: eixo X = Hora, eixo Y = Dia da Semana."""
    if df_heatmap.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Mapa de Calor — Ocupação por Hora")

    day_order = [
        "Segunda-feira", "Terça-feira", "Quarta-feira",
        "Quinta-feira", "Sexta-feira", "Sábado",
    ]
    df_heatmap = df_heatmap[df_heatmap["DiaSemana"].isin(day_order)]

    pivot = df_heatmap.pivot_table(
        index="DiaSemana", columns="Hora", values="Total_Ocupacoes", fill_value=0
    )
    # Reindex to desired order
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    # Filter hours with activity (typically 8-22)
    active_hours = sorted([h for h in pivot.columns if pivot[h].sum() > 0])
    if active_hours:
        pivot = pivot[active_hours]

    # Short day labels
    short_days = {
        "Segunda-feira": "Seg", "Terça-feira": "Ter",
        "Quarta-feira": "Qua", "Quinta-feira": "Qui",
        "Sexta-feira": "Sex", "Sábado": "Sáb",
    }
    y_labels = [short_days.get(d, d) for d in pivot.index]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f"{h}h" for h in pivot.columns],
        y=y_labels,
        colorscale=[
            [0.0, "#EFF6FF"],
            [0.25, "#BFDBFE"],
            [0.5, "#60A5FA"],
            [0.75, "#3B63FB"],
            [1.0, "#1E3A8A"],
        ],
        hovertemplate="<b>%{y}</b> às <b>%{x}</b><br>Ocupações: %{z:,.0f}<extra></extra>",
        showscale=True,
        colorbar=dict(
            title=dict(text="Ocupações", font=dict(size=11)),
            tickfont=dict(size=10),
            thickness=12,
            len=0.8,
        ),
    ))

    fig = _base_layout(fig, "Mapa de Calor — Ocupação por Hora", height=350)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    fig.update_xaxes(showgrid=False, side="top")
    return fig


# ─────────────────────────────────────────────────────────────────────
# GRÁFICO 4: Top 10 Espaços Mais Utilizados (Horizontal Bar)
# ─────────────────────────────────────────────────────────────────────
def chart_top_espacos(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Bar chart horizontal com os espaços mais utilizados."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, f"Top {top_n} Espaços Mais Utilizados")

    top = (
        df[df["Nome_Espaco"] != "N/D"]
        .groupby("Nome_Espaco")
        .size()
        .reset_index(name="Total")
        .sort_values("Total", ascending=True)
        .tail(top_n)
    )

    fig = go.Figure(go.Bar(
        x=top["Total"],
        y=top["Nome_Espaco"],
        orientation="h",
        marker=dict(
            color=top["Total"],
            colorscale=[[0, "#93C5FD"], [1, "#3B63FB"]],
            cornerradius=4,
        ),
        text=top["Total"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
        textfont=dict(size=11, color="#1B2139"),
        hovertemplate="<b>%{y}</b><br>Total: %{x:,.0f}<extra></extra>",
    ))

    fig = _base_layout(fig, f"Top {top_n} Espaços Mais Utilizados", height=400)
    fig.update_xaxes(title_text="Nº Ocupações", showgrid=True)
    fig.update_yaxes(title_text="", showgrid=False)
    return fig


# ─────────────────────────────────────────────────────────────────────
# GRÁFICO 5: Distribuição por Tipo de Atividade (Bar Vertical)
# ─────────────────────────────────────────────────────────────────────
def chart_tipo_atividade(df: pd.DataFrame) -> go.Figure:
    """Vertical bar chart com distribuição por tipo de atividade."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Distribuição por Tipo de Atividade")

    grouped = (
        df[df["Designacao_Atividade"] != "N/D"]
        .groupby("Designacao_Atividade")
        .size()
        .reset_index(name="Total")
        .sort_values("Total", ascending=False)
    )

    fig = go.Figure(go.Bar(
        x=grouped["Designacao_Atividade"],
        y=grouped["Total"],
        marker=dict(
            color=COLORS["donut_palette"][:len(grouped)],
            cornerradius=6,
        ),
        text=grouped["Total"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="<b>%{x}</b><br>Total: %{y:,.0f}<extra></extra>",
    ))

    fig = _base_layout(fig, "Distribuição por Tipo de Atividade", height=370)
    fig.update_xaxes(title_text="", tickangle=-30)
    fig.update_yaxes(title_text="Nº Ocupações")
    return fig


# ─────────────────────────────────────────────────────────────────────
# GRÁFICO 6: Ocupação por Categoria de Espaço (Donut)
# ─────────────────────────────────────────────────────────────────────
def chart_categoria_espaco(df: pd.DataFrame) -> go.Figure:
    """Donut chart com distribuição por categoria de espaço."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação por Categoria de Espaço")

    grouped = (
        df[df["Categoria_Espaco"] != "N/D"]
        .groupby("Categoria_Espaco")
        .size()
        .reset_index(name="Total")
        .sort_values("Total", ascending=False)
    )

    fig = go.Figure(data=[go.Pie(
        labels=grouped["Categoria_Espaco"],
        values=grouped["Total"],
        hole=0.5,
        marker=dict(colors=COLORS["donut_palette"][:len(grouped)]),
        textinfo="label+percent",
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>Total: %{value:,.0f}<br>%{percent}<extra></extra>",
    )])

    fig = _base_layout(fig, "Ocupação por Categoria de Espaço", height=370)
    return fig
