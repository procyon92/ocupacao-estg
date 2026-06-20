import streamlit as st
import pandas as pd
from plots import chart_calendar_day, chart_calendar_week, chart_calendar_month


def render_timetable_calendar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Render do calendário de horários. Devolve o subset do df
    correspondente à vista/período actualmente seleccionado.
    """
    if df.empty:
        st.info("Sem dados para o calendário.")
        return df

    df = df.copy()
    df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])

    col_vista, col_nav1, col_nav2 = st.columns([2, 1, 1])
    with col_vista:
        vista = st.radio("Vista", ["Dia", "Semana", "Mês"],
                         horizontal=True, key="cal_vista")

    min_date = df["DataCompleta"].min().date()
    max_date = df["DataCompleta"].max().date()

    if vista == "Dia":
        with col_nav1:
            selected_date = st.date_input("Data", value=min_date,
                                          min_value=min_date, max_value=max_date,
                                          key="cal_day_date")
        fig = chart_calendar_day(df, pd.Timestamp(selected_date))
        st.plotly_chart(fig, use_container_width=True, key="chart_cal_day")
        return df[df["DataCompleta"].dt.date == selected_date].copy()

    elif vista == "Semana":
        df["week_start"] = df["DataCompleta"].dt.to_period("W").apply(lambda p: p.start_time)
        # Mapeia cada week_start para a semana letiva (Numero_Semana_Escolar) correspondente
        week_sl_map = (
            df.groupby(df["week_start"].dt.date)["Numero_Semana_Escolar"]
            .min()
            .to_dict()
        )
        week_starts = sorted(week_sl_map.keys())
        with col_nav1:
            sel_week = st.selectbox(
                "Semana de",
                options=week_starts,
                format_func=lambda d: f"Semana {week_sl_map.get(d, '?')} — {pd.Timestamp(d).strftime('%d/%m/%Y')}",
                key="cal_week_sel"
            )
        week_ts  = pd.Timestamp(sel_week)
        week_end = week_ts + pd.Timedelta(days=6)
        week_dates = [week_ts + pd.Timedelta(days=i) for i in range(7)
                      if (week_ts + pd.Timedelta(days=i)).date() <= max_date]
        sl_num = week_sl_map.get(sel_week, "?")
        title  = f"📅 Semana Letiva {sl_num} — {week_ts.strftime('%d/%m')} a {(week_ts + pd.Timedelta(days=6)).strftime('%d/%m/%Y')}"
        fig = chart_calendar_week(df, week_dates, title=title)
        st.plotly_chart(fig, use_container_width=True, key="chart_cal_week")
        return df[(df["DataCompleta"].dt.date >= sel_week) &
                  (df["DataCompleta"].dt.date <= week_end.date())].copy()

    elif vista == "Mês":
        available_months = sorted(df["DataCompleta"].dt.to_period("M").unique())
        with col_nav1:
            sel_month = st.selectbox(
                "Mês",
                options=available_months,
                format_func=lambda p: p.strftime("%B %Y"),
                key="cal_month_sel"
            )
        fig = chart_calendar_month(df, sel_month.year, sel_month.month)
        st.plotly_chart(fig, use_container_width=True, key="chart_cal_month")
        return df[(df["DataCompleta"].dt.year == sel_month.year) &
                  (df["DataCompleta"].dt.month == sel_month.month)].copy()

    return df