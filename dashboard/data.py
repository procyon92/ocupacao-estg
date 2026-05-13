"""
data.py — Camada de acesso a dados do Dashboard.
Responsável por queries ao Data Warehouse MySQL e caching via st.cache_data.
"""
import streamlit as st
import pandas as pd
import pymysql
from config import DB_CONFIG


def _get_connection():
    """Cria conexão PyMySQL."""
    return pymysql.connect(**DB_CONFIG)


@st.cache_data(ttl=300)
def get_anos_letivos() -> list:
    """Retorna lista de anos letivos com dados na Facto."""
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT d.Ano_Letivo
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            WHERE d.Ano_Letivo != 'N/D'
            ORDER BY d.Ano_Letivo DESC
        """
        df = pd.read_sql(query, conn)
        return df["Ano_Letivo"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_semestres() -> list:
    """Retorna lista de semestres disponíveis (1, 2)."""
    return [1, 2]


@st.cache_data(ttl=300)
def get_edificios() -> list:
    """Retorna lista de edifícios distintos com dados."""
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT e.Edificio
            FROM Facto_Ocupacao f
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            WHERE e.Edificio != 'N/D'
            ORDER BY e.Edificio
        """
        df = pd.read_sql(query, conn)
        return df["Edificio"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_espacos(edificio: str = None) -> list:
    """Retorna lista de espaços, opcionalmente filtrados por edifício."""
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT e.Nome_Espaco
            FROM Facto_Ocupacao f
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            WHERE e.Nome_Espaco != 'N/D'
        """
        params = []
        if edificio:
            query += " AND e.Edificio = %s"
            params.append(edificio)
        query += " ORDER BY e.Nome_Espaco"
        df = pd.read_sql(query, conn, params=params)
        return df["Nome_Espaco"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_departamentos() -> list:
    """Retorna lista de departamentos/unidades responsáveis."""
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT e.Unidade_Responsavel
            FROM Dim_Espaco e
            WHERE e.Unidade_Responsavel NOT IN ('N/D', 'Indefinido/N.D.')
            ORDER BY e.Unidade_Responsavel
        """
        df = pd.read_sql(query, conn)
        return df["Unidade_Responsavel"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=120)
def get_filtered_data(
    ano_letivo: str = None,
    semestre: int = None,
    edificio: str = None,
    espaco: str = None,
    departamento: str = None,
    data_inicio: str = None,
    data_fim: str = None,
) -> pd.DataFrame:
    """
    Query principal: retorna dados da Facto cruzados com todas as dimensões,
    aplicando os filtros do dashboard.
    """
    conn = _get_connection()
    try:
        query = """
            SELECT
                f.ID_Ocupacao,
                f.Duracao_Minutos,
                f.Numero_Presencas,
                f.Flag_Evento_Agregado,
                d.DataCompleta,
                d.Ano,
                d.Ano_Letivo,
                d.Mes,
                d.Dia,
                d.DiaSemana,
                d.Semestre,
                d.Numero_Semana,
                d.Epoca_Exame,
                d.Tipo_Dia,
                h1.Hora AS Hora_Inicio,
                h1.Minuto AS Minuto_Inicio,
                h2.Hora AS Hora_Fim,
                h2.Minuto AS Minuto_Fim,
                e.Edificio,
                e.Nome_Espaco,
                e.Categoria_Espaco,
                e.Unidade_Responsavel,
                e.is_online,
                uc.Codigo_UC,
                uc.Designacao_UC,
                uc.Ciclo_Estudo,
                r.Nome_Responsavel,
                ta.Designacao_Atividade,
                ea.Estado,
                t.Designacao_Turno
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            JOIN Dim_Hora h1 ON f.SK_Hora_Inicio = h1.SK_Hora
            JOIN Dim_Hora h2 ON f.SK_Hora_Fim = h2.SK_Hora
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            JOIN Dim_Responsavel r ON f.SK_Responsavel = r.SK_Responsavel
            JOIN Dim_Tipo_Atividade ta ON f.SK_Tipo_Atividade = ta.SK_Tipo_Atividade
            JOIN Dim_Estado_Agendamento ea ON f.SK_Estado_Agendamento = ea.SK_Estado_Agendamento
            JOIN Dim_Turno t ON f.SK_Turno = t.SK_Turno
            WHERE 1=1
        """
        params = []

        if ano_letivo:
            query += " AND d.Ano_Letivo = %s"
            params.append(ano_letivo)
        if semestre is not None:
            query += " AND d.Semestre = %s"
            params.append(semestre)
        if edificio:
            query += " AND e.Edificio = %s"
            params.append(edificio)
        if espaco:
            query += " AND e.Nome_Espaco = %s"
            params.append(espaco)
        if departamento:
            query += " AND e.Unidade_Responsavel = %s"
            params.append(departamento)
        if data_inicio:
            query += " AND d.DataCompleta >= %s"
            params.append(data_inicio)
        if data_fim:
            query += " AND d.DataCompleta <= %s"
            params.append(data_fim)

        df = pd.read_sql(query, conn, params=params)
        if "DataCompleta" in df.columns:
            df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])
        return df
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_etl_quality_metrics() -> dict:
    """Retorna métricas de qualidade do ETL (contagens, erros)."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Facto_Ocupacao")
        total = cursor.fetchone()[0]

        # Registos com SK=0 (dados ausentes) contam como "problemas"
        cursor.execute("""
            SELECT COUNT(*) FROM Facto_Ocupacao
            WHERE SK_Espaco = 0 OR SK_Unidade_Curricular = 0
                  OR SK_Responsavel = 0 OR SK_Data = 0
        """)
        with_defaults = cursor.fetchone()[0]

        valid = total - with_defaults

        return {
            "total": total,
            "valid": valid,
            "errors": with_defaults,
        }
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_ocupacao_por_hora(
    ano_letivo: str = None,
    semestre: int = None,
    departamento: str = None,
) -> pd.DataFrame:
    """Retorna heatmap data: ocupações por hora e dia da semana."""
    conn = _get_connection()
    try:
        query = """
            SELECT
                d.DiaSemana,
                h.Hora,
                COUNT(*) as Total_Ocupacoes
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            JOIN Dim_Hora h ON f.SK_Hora_Inicio = h.SK_Hora
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            WHERE d.Tipo_Dia = 'Dia Útil/Letivo'
        """
        params = []
        if ano_letivo:
            query += " AND d.Ano_Letivo = %s"
            params.append(ano_letivo)
        if semestre is not None:
            query += " AND d.Semestre = %s"
            params.append(semestre)
        if departamento:
            query += " AND e.Unidade_Responsavel = %s"
            params.append(departamento)

        query += " GROUP BY d.DiaSemana, h.Hora ORDER BY h.Hora"
        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()
