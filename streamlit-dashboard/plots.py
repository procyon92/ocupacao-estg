import plotly.graph_objects as go
import pandas as pd
import calendar
from config import COLORS, WEEKDAY_ORDER_FULL, WEEKDAY_PT, WEEKDAY_SHORT, WEEKDAY_SHORT_FULL


def _base_layout(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    # Layout padrão aplicado a todos os gráficos — fundo transparente, fonte Inter
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=16, color="#1B2139", family="Inter, sans-serif"),
            x=0.02, y=0.96,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#64748B", size=12),
        height=height,
        margin=dict(l=50, r=30, t=60, b=50),
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.25,
            xanchor="center", x=0.5, font=dict(size=11),
        ),
    )
    fig.update_xaxes(showgrid=True, gridcolor=COLORS["chart_grid"], gridwidth=0.5, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["chart_grid"], gridwidth=0.5, zeroline=False)
    return fig


def _build_heatmap_pivot(df: pd.DataFrame, value_col: str) -> tuple:
    # Constrói o pivot (DiaSemana × Hora) usado pelos mapas de calor
    day_order = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"]
    df = df[df["DiaSemana"].isin(day_order)].copy()
    pivot = df.pivot_table(index="DiaSemana", columns="Hora_Inicio", values=value_col, fill_value=0)
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    # Só mostra horas com pelo menos uma ocupação
    active_hours = sorted([h for h in pivot.columns if pivot[h].sum() > 0])
    if active_hours:
        pivot = pivot[active_hours]
    y_labels = [WEEKDAY_PT.get(d, d) for d in pivot.index]
    return pivot, y_labels, day_order


def chart_ocupacao_tempo(df: pd.DataFrame, granularity: str = "Mensal") -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação ao longo do tempo")

    df = df.copy()
    # Agrupa por diário, semanal ou mensal conforme o que o user escolheu
    if granularity == "Diário":
        grouped = df.groupby("DataCompleta").size().reset_index(name="Total").sort_values("DataCompleta")
        x_col = "DataCompleta"
    elif granularity == "Semanal":
        df["Semana"] = df["DataCompleta"].dt.to_period("W").apply(lambda r: r.start_time)
        grouped = df.groupby("Semana").size().reset_index(name="Total").sort_values("Semana")
        x_col = "Semana"
    else:
        df["Mes_Periodo"] = df["DataCompleta"].dt.to_period("M").apply(lambda r: r.start_time)
        grouped = df.groupby("Mes_Periodo").size().reset_index(name="Total").sort_values("Mes_Periodo")
        x_col = "Mes_Periodo"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=grouped[x_col], y=grouped["Total"],
        fill="tozeroy", fillcolor="rgba(59, 99, 251, 0.08)",
        line=dict(color=COLORS["primary"], width=2.5, shape="spline"),
        mode="lines", name="Ocupações",
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Total: %{y:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, "Ocupação ao longo do tempo", height=380)
    fig.update_xaxes(title_text="", tickfont=dict(color="#334155"))
    fig.update_yaxes(title_text="Nº Ocupações", tickfont=dict(color="#334155"))
    return fig


def chart_ocupacao_edificio(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação por Edifício")

    top = df[df["Edificio"] != "N/D"].groupby("Edificio").size().reset_index(name="Total").sort_values("Total", ascending=False)
    # Trunca nomes longos para não desformatar o gráfico
    top["Label"] = top["Edificio"].apply(lambda x: x[:25] + "…" if len(x) > 25 else x)
    # Agrupa tudo a partir do 8º edifício em "Outros"
    if len(top) > 8:
        main = top.head(7)
        others = pd.DataFrame({"Edificio": ["Outros"], "Total": [top.iloc[7:]["Total"].sum()], "Label": ["Outros"]})
        top = pd.concat([main, others], ignore_index=True)

    fig = go.Figure(data=[go.Pie(
        labels=top["Label"], values=top["Total"], hole=0.55,
        marker=dict(colors=COLORS["donut_palette"][:len(top)]),
        textinfo="percent", textposition="outside", textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>Total: %{value:,.0f}<br>%{percent}<extra></extra>",
        pull=[0.03 if i == 0 else 0 for i in range(len(top))],
    )])
    fig = _base_layout(fig, "Ocupação por Edifício", height=380)
    fig.update_layout(showlegend=True, margin=dict(r=140),
        legend=dict(orientation="v", yanchor="top", y=0.88, xanchor="left", x=1.02, font=dict(size=10)))
    return fig


def chart_heatmap_ocupacao(df_heatmap: pd.DataFrame) -> go.Figure:
    if df_heatmap.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Mapa de Calor — Ocupação por Hora")

    pivot, y_labels, _ = _build_heatmap_pivot(df_heatmap, "Total_Ocupacoes")

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=[f"{h}h" for h in pivot.columns], y=y_labels,
        colorscale=[[0.0, "#EFF6FF"], [0.25, "#BFDBFE"], [0.5, "#60A5FA"], [0.75, "#3B63FB"], [1.0, "#1E3A8A"]],
        hovertemplate="<b>%{y}</b> às <b>%{x}</b><br>Ocupações: %{z:,.0f}<extra></extra>",
        showscale=True, colorbar=dict(title=dict(text="Ocupações", font=dict(size=11)), tickfont=dict(size=10), thickness=12, len=0.8),
    ))
    fig = _base_layout(fig, "Mapa de Calor — Ocupação por Hora", height=350)
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(color="#334155"))
    fig.update_xaxes(showgrid=False, side="top", tickfont=dict(color="#334155"))
    return fig


def chart_top_espacos(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, f"Espaços com maior ocupação")

    top = (df[df["Nome_Espaco"] != "N/D"].groupby("Nome_Espaco").size().reset_index(name="Total").sort_values("Total", ascending=True).tail(top_n))
    fig = go.Figure(go.Bar(
        x=top["Total"], y=top["Nome_Espaco"], orientation="h",
        marker=dict(color=top["Total"], colorscale=[[0, "#93C5FD"], [1, "#3B63FB"]], cornerradius=4),
        text=top["Total"].apply(lambda v: f"{v:,.0f}"), textposition="outside",
        textfont=dict(size=11, color="#1B2139"),
        hovertemplate="<b>%{y}</b><br>Total: %{x:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, f"Espaços com maior ocupação", height=400)
    fig.update_xaxes(title_text="Nº Ocupações", tickfont=dict(color="#334155"))
    fig.update_yaxes(title_text="", showgrid=False, tickfont=dict(color="#334155"))
    return fig


def chart_bottom_espacos(df: pd.DataFrame, bottom_n: int = 10) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, f"Espaços com menor ocupação")

    bottom = (df[df["Nome_Espaco"] != "N/D"].groupby("Nome_Espaco").size().reset_index(name="Total").sort_values("Total", ascending=True).head(bottom_n))
    fig = go.Figure(go.Bar(
        x=bottom["Total"], y=bottom["Nome_Espaco"], orientation="h",
        marker=dict(color=bottom["Total"], colorscale=[[0, "#FCA5A5"], [1, "#EF4444"]], cornerradius=4),
        text=bottom["Total"].apply(lambda v: f"{v:,.0f}"), textposition="outside",
        textfont=dict(size=11, color="#1B2139"),
        hovertemplate="<b>%{y}</b><br>Total: %{x:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, f"Espaços com menor ocupação", height=400)
    fig.update_xaxes(title_text="Nº Ocupações", tickfont=dict(color="#334155"))
    fig.update_yaxes(title_text="", showgrid=False, tickfont=dict(color="#334155"), autorange="reversed")
    return fig


def chart_tipo_atividade(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Distribuição por Tipo de Atividade")

    grouped = (df[df["Designacao_Atividade"] != "N/D"].groupby("Designacao_Atividade").size().reset_index(name="Total").sort_values("Total", ascending=False))
    fig = go.Figure(go.Bar(
        x=grouped["Designacao_Atividade"], y=grouped["Total"],
        marker=dict(color=COLORS["donut_palette"][:len(grouped)], cornerradius=6),
        text=grouped["Total"].apply(lambda v: f"{v:,.0f}"), textposition="outside", textfont=dict(size=11),
        hovertemplate="<b>%{x}</b><br>Total: %{y:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, "Distribuição por Tipo de Atividade", height=370)
    fig.update_xaxes(title_text="", tickangle=-30, tickfont=dict(color="#334155"))
    fig.update_yaxes(title_text="Nº Ocupações", tickfont=dict(color="#334155"))
    return fig


def chart_categoria_espaco(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação por Categoria de Espaço")

    grouped = (df[df["Categoria_Espaco"] != "N/D"].groupby("Categoria_Espaco").size().reset_index(name="Total").sort_values("Total", ascending=False))
    fig = go.Figure(data=[go.Pie(
        labels=grouped["Categoria_Espaco"], values=grouped["Total"], hole=0.5,
        marker=dict(colors=COLORS["donut_palette"][:len(grouped)]),
        textinfo="label+percent", textposition="outside", textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>Total: %{value:,.0f}<br>%{percent}<extra></extra>",
    )])
    fig = _base_layout(fig, "Ocupação por Categoria de Espaço", height=370)
    return fig


def chart_period_of_day(df: pd.DataFrame) -> go.Figure:
    if df.empty or "Periodo_Dia" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação por Período do Dia")

    period_order = ["Manhã", "Tarde", "Noite"]
    counts = df["Periodo_Dia"].value_counts().reindex(period_order, fill_value=0).reset_index()
    counts.columns = ["Periodo", "Total"]
    colors_map = {"Manhã": "#3B63FB", "Tarde": "#F59E0B", "Noite": "#8B5CF6"}

    fig = go.Figure(data=[go.Pie(
        labels=counts["Periodo"], values=counts["Total"], hole=0.4,
        marker=dict(colors=[colors_map.get(p, "#94A3B8") for p in counts["Periodo"]]),
        textinfo="label+percent", textposition="outside", textfont=dict(size=12),
        hovertemplate="<b>%{label}</b><br>Total: %{value:,.0f}<br>%{percent}<extra></extra>",
    )])
    fig = _base_layout(fig, "Ocupação por Período do Dia", height=370)
    return fig


def chart_single_space_heatmap(df: pd.DataFrame) -> go.Figure:
    # Mapa de calor semanal para uma sala específica — células vazias ficam a verde claro
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação Semanal — Sala")

    day_order = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"]
    df = df[df["DiaSemana"].isin(day_order)].copy()
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação Semanal — Sala")

    # Conta sessões por (dia, hora)
    grid = df.groupby(["DiaSemana", "Hora_Inicio"]).size().reset_index(name="count")
    pivot = grid.pivot_table(index="DiaSemana", columns="Hora_Inicio", values="count", fill_value=0)
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    all_hours = sorted([h for h in pivot.columns])
    if all_hours:
        pivot = pivot[all_hours]

    y_labels = [WEEKDAY_PT.get(d, d) for d in pivot.index]

    # Verde claro para 0 sessões; azul crescente para mais sessões
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f"{h}h" for h in pivot.columns],
        y=y_labels,
        colorscale=[
            [0.0, "#F0FDF4"],
            [0.01, "#EFF6FF"],
            [0.25, "#BFDBFE"],
            [0.5,  "#60A5FA"],
            [0.75, "#3B63FB"],
            [1.0,  "#1E3A8A"],
        ],
        hovertemplate="<b>%{y}</b> às <b>%{x}</b><br>Sessões: %{z}<extra></extra>",
        showscale=True,
        colorbar=dict(title=dict(text="Sessões", font=dict(size=11)), tickfont=dict(size=10), thickness=12, len=0.8),
    ))
    fig = _base_layout(fig, "Ocupação Semanal — Sala", height=350)
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(color="#334155"))
    fig.update_xaxes(showgrid=False, side="top", dtick=1, tickfont=dict(color="#334155"))
    return fig


def chart_anomalies_trend(df: pd.DataFrame) -> go.Figure:
    # Evolução temporal das ghost sessions (aulas com 0 presenças)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados de anomalias", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Evolução de Anomalias")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Periodo"],
        y=df["Ghost_Count"],
        mode="lines+markers",
        line=dict(color="#EF4444", width=2.5),
        marker=dict(size=8, color="#EF4444", line=dict(color="#991B1B", width=1)),
        fill="tozeroy",
        fillcolor="rgba(239, 68, 68, 0.08)",
        name="Ghost Sessions",
        hovertemplate="<b>%{x}</b><br>Ghost: %{y}<extra></extra>",
    ))
    fig = _base_layout(fig, "Evolução de Sessões Fantasma (Ghost)", height=350)
    fig.update_xaxes(title_text="", tickangle=-45, tickfont=dict(color="#334155"))
    fig.update_yaxes(title_text="Nº Ghost Sessions", tickfont=dict(color="#334155"))
    return fig


def chart_monthly_calendar(df: pd.DataFrame, year: int, month: int) -> go.Figure:
    # Calendário onde cada célula representa um dia do mês, cor indica nº de sessões
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, f"Calendário {calendar.month_name[month]} {year}")

    df = df.copy()
    df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])
    # Conta sessões por dia
    daily = df.groupby(df["DataCompleta"].dt.date).size().reset_index(name="count")
    daily.columns = ["date", "count"]

    cal = calendar.monthcalendar(year, month)
    day_names = WEEKDAY_SHORT  # Seg a Sáb — sem domingo

    z = []
    hover_texts = []
    for week_idx, week in enumerate(cal):
        row = []
        hrow = []
        for day_idx, day_num in enumerate(week):
            if day_idx >= 6:  # ignora domingo
                continue
            if day_num == 0:
                # Dia fora do mês — célula vazia
                row.append(None)
                hrow.append("")
            else:
                d = pd.Timestamp(year=year, month=month, day=day_num)
                match = daily[daily["date"] == d.date()]
                val = int(match["count"].sum()) if not match.empty else 0
                row.append(val)
                hrow.append(
                    f"{d.strftime('%d/%m/%Y')} ({day_names[day_idx]})<br>"
                    f"Sessões: {val}"
                )
        z.append(row)
        hover_texts.append(hrow)

    week_labels = [f"S {i+1}" for i in range(len(cal))]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=day_names,
        y=week_labels,
        text=hover_texts,
        hoverinfo="text",
        colorscale=[
            [0.0,    "#F0FDF4"],   # 0 sessões — verde claro
            [0.001,  "#EFF6FF"],   # 1 sessão  — azul muito claro
            [0.15,   "#BFDBFE"],
            [0.35,   "#60A5FA"],
            [0.55,   "#3B63FB"],
            [0.75,   "#1D4ED8"],
            [1.0,    "#1E3A8A"],
        ],
        showscale=True,
        colorbar=dict(
            title=dict(text="Sessões", font=dict(size=11)),
            tickfont=dict(size=10),
            thickness=12, len=0.7,
        ),
        xgap=4, ygap=4,
    ))

    fig.update_layout(
        title=dict(
            text=f"Calendário de Ocupação — {calendar.month_name[month]} {year}",
            font=dict(size=16, color="#1B2139", family="Inter, sans-serif"),
            x=0.02, y=0.96,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#64748B", size=12),
        height=300,
        margin=dict(l=40, r=30, t=60, b=30),
    )
    fig.update_xaxes(showgrid=False, side="top", tickfont=dict(size=11))
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(size=11))
    return fig


def chart_critical_heatmap(
    df: pd.DataFrame,
    total_rooms: int,
    low_threshold: float = 30.0,
    high_threshold: float = 70.0,
) -> go.Figure:
    # Mapa de calor com 3 níveis: verde (baixo), amarelo (médio), vermelho (alto)
    if df.empty or total_rooms == 0:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados", showarrow=False, font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Ocupação Crítica por Horário")

    df = df.copy()
    # Percentagem de salas ocupadas em cada slot
    df["ratio"] = df["Salas_Ocupadas"] / total_rooms * 100
    pivot, y_labels, _ = _build_heatmap_pivot(df, "ratio")

    l = low_threshold / 100.0
    h = high_threshold / 100.0

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f"{h}h" for h in pivot.columns],
        y=y_labels,
        colorscale=[
            [0.0,         "#22C55E"],
            [l,           "#22C55E"],
            [l + 0.001,   "#EAB308"],
            [h,           "#EAB308"],
            [h + 0.001,   "#EF4444"],
            [1.0,         "#EF4444"],
        ],
        zmin=0,
        zmax=100,
        hovertemplate="<b>%{y}</b> às <b>%{x}</b><br>Ocupação: %{z:.1f}%<extra></extra>",
        showscale=True,
        colorbar=dict(
            title=dict(text="Ocupação %", font=dict(size=11)),
            tickfont=dict(size=10),
            thickness=12, len=0.8,
            tickvals=[0, low_threshold, high_threshold, 100],
            ticktext=[f"0%", f"{low_threshold:.0f}%", f"{high_threshold:.0f}%", "100%"],
        ),
    ))

    fig = _base_layout(fig, "Ocupação Crítica por Horário", height=350)
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(color="#334155"))
    fig.update_xaxes(showgrid=False, side="top", tickfont=dict(color="#334155"))
    return fig


def chart_comparison_trend(rooms_dict: dict) -> go.Figure:
    # Sobreposição de tendências diárias para várias salas — uma linha por sala
    if not rooms_dict:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados para comparação", showarrow=False,
                           font=dict(size=16, color="#94A3B8"))
        return _base_layout(fig, "Comparação de Ocupação")

    palette = COLORS["donut_palette"]
    fig = go.Figure()

    for i, (room_name, room_df) in enumerate(rooms_dict.items()):
        if room_df.empty:
            continue
        daily = room_df.copy()
        daily["Data"] = pd.to_datetime(daily["DataCompleta"]).dt.date
        counts = daily.groupby("Data").size().reset_index(name="count")
        counts = counts.sort_values("Data")
        fig.add_trace(go.Scatter(
            x=counts["Data"].astype(str),
            y=counts["count"],
            mode="lines+markers",
            name=room_name,
            line=dict(color=palette[i % len(palette)], width=2),
            marker=dict(size=6),
            hovertemplate=f"<b>{room_name}</b><br>%{{x}}<br>Sessões: %{{y}}<extra></extra>",
        ))

    fig = _base_layout(fig, "Comparação de Ocupação — Tendência Diária", height=400)
    fig.update_xaxes(title_text="", tickangle=-45, tickfont=dict(color="#334155"))
    fig.update_yaxes(title_text="Nº Sessões", tickfont=dict(color="#334155"))
    return fig


def _get_color_map(df: pd.DataFrame) -> dict:
    # Atribui uma cor estável a cada UC — ordem alfabética para ser consistente entre vistas
    keys = sorted(df["Designacao_UC"].dropna().unique().tolist())
    return {k: COLORS["turno_palette"][i % len(COLORS["turno_palette"])] for i, k in enumerate(keys)}


def _time_to_hour(hora: int, minuto: int) -> float:
    # Converte hora + minuto para decimal (ex: 9h30 → 9.5)
    return hora + minuto / 60.0


def _fmt_time(hora: int, minuto: int) -> str:
    return f"{int(hora):02d}:{int(minuto):02d}"


def _wrap_text(text: str, max_chars: int = 18) -> str:
    # Trunca texto longo em várias linhas para caber nas células do calendário
    if len(text) <= max_chars:
        return text
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "<br>".join(lines)


def _base_calendar_layout(fig: go.Figure, title: str, height: int) -> go.Figure:
    # Layout base para as vistas de calendário (dia, semana, mês)
    # Margem do topo aumentada para o título não tapar o cabeçalho dos dias
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#1B2139", family="Inter, sans-serif"), x=0.01, y=0.97),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FAFBFF",
        height=height,
        margin=dict(l=60, r=20, t=70, b=30),
        showlegend=False,
        font=dict(family="Inter, sans-serif", size=11, color="#334155"),
    )
    return fig


def chart_calendar_day(df: pd.DataFrame, date: pd.Timestamp) -> go.Figure:
    # Vista diária — uma coluna com os blocos de aulas ordenados por hora
    day_df = df[df["DataCompleta"].dt.date == date.date()].copy()
    fig = go.Figure()

    y_min, y_max = 8, 24
    color_map = _get_color_map(df)

    # Linhas de grelha hora a hora
    for h in range(y_min, y_max + 1):
        fig.add_shape(type="line", x0=0, x1=1, y0=h, y1=h,
                      line=dict(color="#94A3B8", width=1))
        fig.add_annotation(x=-0.02, y=h, text=f"{h}h", showarrow=False,
                           font=dict(size=10, color="#94A3B8"), xref="paper", yref="y", xanchor="right")

    if day_df.empty:
        fig.add_annotation(text="Sem aulas neste dia", x=0.5, y=(y_min + y_max) / 2,
                           showarrow=False, font=dict(size=14, color="#94A3B8"), xref="paper", yref="y")
    else:
        for _, row in day_df.iterrows():
            t_start = _time_to_hour(row["Hora_Inicio"], row["Minuto_Inicio"])
            t_end   = _time_to_hour(row["Hora_Fim"],   row["Minuto_Fim"])

            # Se o fim for antes ou igual ao início, assume meia-noite
            if t_end <= t_start:
                t_end = 24.0

            color = color_map.get(row.get("Designacao_UC", ""), "#3B63FB")
            label = f"{_wrap_text(str(row.get('Designacao_UC', '')), 40)}<br>" \
                    f"<span style='font-size:10px'>{row.get('Designacao_Turno', '')} · " \
                    f"{_fmt_time(row['Hora_Inicio'], row['Minuto_Inicio'])}–{_fmt_time(row['Hora_Fim'], row['Minuto_Fim'])}</span>"
            hover = (f"<b>{row.get('Designacao_UC', '')}</b><br>"
                     f"Turno: {row.get('Designacao_Turno', 'N/D')}<br>"
                     f"Hora: {_fmt_time(row['Hora_Inicio'], row['Minuto_Inicio'])} – {_fmt_time(row['Hora_Fim'], row['Minuto_Fim'])}<br>"
                     f"Docente: {row.get('Docente_Responsavel', 'N/D')}<br>"
                     f"Sala: {row.get('Nome_Espaco', 'N/D')}")
            fig.add_shape(type="rect", x0=0.05, x1=0.95, y0=t_start, y1=t_end,
                          fillcolor=color, opacity=0.85, line=dict(color="white", width=1.5),
                          layer="above")
            fig.add_annotation(
                x=0.5, y=(t_start + t_end) / 2,
                text=label,
                showarrow=False,
                font=dict(size=11, color="white"),
                xref="paper", yref="y",
                align="center",
                xanchor="center", yanchor="middle",
                bgcolor="rgba(0,0,0,0)",
                borderpad=3,
            )

    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(range=[y_max, y_min], showgrid=False, showticklabels=False, zeroline=False)
    fig = _base_calendar_layout(fig, f"📅 {date.strftime('%A, %d de %B de %Y')}", height=700)
    return fig


def chart_calendar_week(df: pd.DataFrame, week_dates: list[pd.Timestamp], title: str = "") -> go.Figure:
    # Vista semanal — uma coluna por dia, blocos de aulas sobrepostos na grelha horária
    fig = go.Figure()
    color_map = _get_color_map(df)

    y_min, y_max = 8, 24
    n_days = len(week_dates)

    # Cabeçalho com o nome curto do dia e o número — ponto azul se tiver aulas
    for col_i, day_ts in enumerate(week_dates):
        x_center = col_i + 0.5
        day_df = df[df["DataCompleta"].dt.date == day_ts.date()]
        dot = " 🔵" if not day_df.empty else ""
        fig.add_annotation(
            x=x_center, y=y_max + 0.5,
            # WEEKDAY_SHORT_FULL para suportar domingo sem IndexError
            text=f"<b>{WEEKDAY_SHORT_FULL[day_ts.weekday()]}</b><br><span style='font-size:12px'>{day_ts.day}</span>{dot}",
            showarrow=False, font=dict(size=12, color="#1B2139"), yref="y", xref="x",
            align="center",
        )

    # Grelha de horas
    for h in range(y_min, y_max + 1):
        fig.add_shape(type="line", x0=0, x1=n_days, y0=h, y1=h,
                      line=dict(color="#94A3B8", width=0.8))
        fig.add_annotation(x=-0.15, y=h, text=f"{h}h", showarrow=False,
                           font=dict(size=9, color="#94A3B8"), xref="x", yref="y", xanchor="right")

    # Separadores verticais entre dias
    for col_i in range(n_days + 1):
        fig.add_shape(type="line", x0=col_i, x1=col_i, y0=y_min, y1=y_max,
                      line=dict(color="#94A3B8", width=1))

    # Blocos de eventos
    for col_i, day_ts in enumerate(week_dates):
        day_df = df[df["DataCompleta"].dt.date == day_ts.date()].copy()
        if day_df.empty:
            continue
        for _, row in day_df.iterrows():
            t_start = _time_to_hour(row["Hora_Inicio"], row["Minuto_Inicio"])
            t_end   = _time_to_hour(row["Hora_Fim"],   row["Minuto_Fim"])

            # Se o fim for antes ou igual ao início, assume meia-noite
            if t_end <= t_start:
                t_end = 24.0

            color    = color_map.get(row.get("Designacao_UC", ""), "#3B63FB")
            uc_short = str(row.get("Designacao_UC", ""))[:40]
            turno    = str(row.get("Designacao_Turno", ""))
            hora     = f"{_fmt_time(row['Hora_Inicio'], row['Minuto_Inicio'])}–{_fmt_time(row['Hora_Fim'], row['Minuto_Fim'])}"
            label    = f"{uc_short}<br>{turno} - {hora}"
            hover    = (f"<b>{row.get('Designacao_UC', '')}</b><br>"
                        f"Turno: {turno}<br>"
                        f"{_fmt_time(row['Hora_Inicio'], row['Minuto_Inicio'])} – {_fmt_time(row['Hora_Fim'], row['Minuto_Fim'])}<br>"
                        f"Docente: {row.get('Docente_Responsavel', 'N/D')}<br>"
                        f"Sala: {row.get('Nome_Espaco', 'N/D')}")

            x0 = col_i + 0.05
            x1 = col_i + 0.95
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=t_start, y1=t_end,
                          fillcolor=color, opacity=0.88,
                          line=dict(color="white", width=1.2), layer="above")
            fig.add_annotation(
                x=(x0 + x1) / 2,
                y=(t_start + t_end) / 2,
                text=label,
                showarrow=False,
                font=dict(size=16, color="white"),
                xref="x", yref="y",
                align="center",
                xanchor="center", yanchor="middle",
                bgcolor="rgba(0,0,0,0)",
                borderpad=2,
            )

    fig.update_xaxes(range=[-0.3, n_days], showgrid=False, showticklabels=False, zeroline=False)
    fig.update_yaxes(range=[y_max + 1, y_min - 0.5], showgrid=False, showticklabels=False, zeroline=False)
    fig = _base_calendar_layout(fig, title or "📅 Vista Semanal", height=750)
    return fig


def chart_calendar_month(df: pd.DataFrame, year: int, month: int) -> go.Figure:
    import calendar as cal_lib
    color_map = _get_color_map(df)

    fig = go.Figure()
    cal_matrix = cal_lib.monthcalendar(year, month)
    month_name = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][month - 1]

    n_weeks = len(cal_matrix)

    # Pré-agrupa sessões por data — evita filtrar o DataFrame inteiro para cada dia
    daily_groups = df.groupby(df["DataCompleta"].dt.date)
    daily_counts = daily_groups.size().to_dict()

    # Altura dinâmica baseada no dia com mais eventos de todo o mês
    max_events_in_day = max(daily_counts.values(), default=1)

    cell_height_px = 40 + max_events_in_day * 40
    total_height   = 80 + n_weeks * cell_height_px
    cell_h         = 1.0 / n_weeks
    day_names      = WEEKDAY_SHORT  # Seg a Sáb — sem domingo

    # Cabeçalho com os nomes dos dias
    for col_i, dname in enumerate(day_names):
        fig.add_annotation(x=col_i + 0.5, y=1.04, text=f"<b>{dname}</b>",
                           showarrow=False, font=dict(size=16, color="#475569"),
                           xref="x", yref="paper", xanchor="center")

    for row_i, week in enumerate(cal_matrix):
        y_top    = 1.0 - row_i * cell_h
        y_bottom = y_top - cell_h

        for col_i, day_num in enumerate(week):
            if col_i >= 6:  # ignora domingo
                continue

            x0, x1 = col_i, col_i + 1
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y_bottom, y1=y_top,
                          fillcolor="white", line=dict(color="#94A3B8", width=1), layer="below")

            if day_num == 0:
                # Dia fora do mês — fundo cinzento
                fig.add_shape(type="rect", x0=x0, x1=x1, y0=y_bottom, y1=y_top,
                              fillcolor="#F8FAFC", line=dict(color="#94A3B8", width=1), layer="below")
                continue

            # Número do dia no canto superior esquerdo da célula
            fig.add_annotation(x=x0 + 0.08, y=y_top - 0.008,
                               text=f"<b>{day_num}</b>",
                               showarrow=False, font=dict(size=11, color="#334155"),
                               xref="x", yref="paper", xanchor="left", yanchor="top")

            day_ts   = pd.Timestamp(year=year, month=month, day=day_num).date()
            day_df   = daily_groups.get_group(day_ts).sort_values("Hora_Inicio") if day_ts in daily_groups.groups else pd.DataFrame()
            n_events = len(day_df)

            if n_events == 0:
                continue

            header_frac = 0.08
            padding     = 0.01
            available   = cell_h - header_frac * cell_h - padding
            # ev_h consistente com max_events_in_day — garante que nenhum bloco transborda
            ev_h = available / max(max_events_in_day, 1)

            for ev_i, (_, row) in enumerate(day_df.iterrows()):
                color       = color_map.get(row.get("Designacao_UC", ""), "#3B63FB")
                ev_y_top    = y_top - header_frac * cell_h - padding - ev_i * (ev_h + 0.000)
                ev_y_bot    = ev_y_top - ev_h
                hora        = f"{_fmt_time(row['Hora_Inicio'], row['Minuto_Inicio'])}–{_fmt_time(row['Hora_Fim'], row['Minuto_Fim'])}"
                uc_short    = str(row.get("Designacao_UC", ""))[:14]
                turno_short = str(row.get("Designacao_Turno", ""))[:8]
                label       = f"{hora} {uc_short} {turno_short}"

                fig.add_shape(type="rect",
                              x0=x0 + 0.04, x1=x1 - 0.04,
                              y0=ev_y_bot, y1=ev_y_top,
                              fillcolor=color, opacity=0.85,
                              line=dict(color="white", width=0.5), layer="above")
                fig.add_annotation(
                    x=(x0 + x1) / 2, y=(ev_y_top + ev_y_bot) / 2,
                    text=label,
                    showarrow=False,
                    font=dict(size=10, color="white"),
                    xref="x", yref="paper",
                    align="center",
                    xanchor="center", yanchor="middle",
                    bgcolor="rgba(0,0,0,0)",
                    borderpad=1,
                )

    fig.update_xaxes(range=[0, 6], showgrid=False, showticklabels=False, zeroline=False)
    fig.update_yaxes(range=[0, 1], showgrid=False, showticklabels=False, zeroline=False)
    fig = _base_calendar_layout(fig, f"📅 {month_name} {year}", height=total_height)
    fig.update_layout(margin=dict(l=10, r=10, t=70, b=10))
    return fig