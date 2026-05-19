"""
data.py — Camada de acesso a dados do Dashboard.
Responsável por queries ao Data Warehouse MySQL e caching via st.cache_data.
"""
import streamlit as st
import pandas as pd
import pymysql
from config import DB_CONFIG


def _get_connection():
    return pymysql.connect(**DB_CONFIG)


@st.cache_data(ttl=300)
def get_anos_letivos() -> list:
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT d.Ano_Escolar AS Ano_Letivo
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            WHERE d.Ano_Escolar != 'N/D'
            ORDER BY d.Ano_Escolar DESC
        """
        df = pd.read_sql(query, conn)
        return df["Ano_Letivo"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_semestres() -> list:
    return [1, 2]


@st.cache_data(ttl=300)
def get_edificios() -> list:
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
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT e.Escola_Responsavel AS Departamento
            FROM Dim_Espaco e
            WHERE e.Escola_Responsavel NOT IN ('N/D', 'Indefinido/N.D.')
            ORDER BY e.Escola_Responsavel
        """
        df = pd.read_sql(query, conn)
        return df["Departamento"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_ciclos_estudo() -> list:
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT uc.Ciclo_Estudo
            FROM Facto_Ocupacao f
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            WHERE uc.Ciclo_Estudo != 'N/D'
            ORDER BY uc.Ciclo_Estudo
        """
        df = pd.read_sql(query, conn)
        return df["Ciclo_Estudo"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_epocas() -> list:
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT ep.Descricao_Epoca
            FROM Facto_Ocupacao f
            JOIN Dim_Epoca ep ON f.SK_Epoca = ep.SK_Epoca
            WHERE ep.Descricao_Epoca != 'N/D'
            ORDER BY ep.Descricao_Epoca
        """
        df = pd.read_sql(query, conn)
        return df["Descricao_Epoca"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_ciclos_estudo() -> list:
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT uc.Ciclo_Estudo
            FROM Facto_Ocupacao f
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            WHERE uc.Ciclo_Estudo != 'N/D'
            ORDER BY uc.Ciclo_Estudo
        """
        df = pd.read_sql(query, conn)
        return df["Ciclo_Estudo"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_epocas() -> list:
    conn = _get_connection()
    try:
        query = """
            SELECT DISTINCT ep.Descricao_Epoca
            FROM Facto_Ocupacao f
            JOIN Dim_Epoca ep ON f.SK_Epoca = ep.SK_Epoca
            WHERE ep.Descricao_Epoca != 'N/D'
            ORDER BY ep.Descricao_Epoca
        """
        df = pd.read_sql(query, conn)
        return df["Descricao_Epoca"].tolist()
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
    epoca: str = None,
    ciclo_estudo: str = None,
    hide_online: bool = False,
    deduplicate_concurrent: bool = False,
    hide_ghost_sessions: bool = False,
) -> pd.DataFrame:
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
                d.Ano_Escolar,
                d.Mes,
                d.Dia,
                d.DiaSemana,
                d.Semestre,
                d.Numero_Semana,
                d.Tipo_Dia,
                ep.Descricao_Epoca,
                h1.Hora AS Hora_Inicio,
                h1.Minuto AS Minuto_Inicio,
                h2.Hora AS Hora_Fim,
                h2.Minuto AS Minuto_Fim,
                e.Edificio,
                e.Nome_Espaco,
                e.Categoria_Espaco,
                e.Escola_Responsavel,
                e.is_online,
                uc.Codigo_UC,
                uc.Designacao_UC,
                uc.Ciclo_Estudo,
                r.Docente_Responsavel,
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
            JOIN Dim_Epoca ep ON f.SK_Epoca = ep.SK_Epoca
            WHERE 1=1
        """
        params = []

        if ano_letivo:
            query += " AND d.Ano_Escolar = %s"
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
            query += " AND e.Escola_Responsavel = %s"
            params.append(departamento)
        if data_inicio:
            query += " AND d.DataCompleta >= %s"
            params.append(data_inicio)
        if data_fim:
            query += " AND d.DataCompleta <= %s"
            params.append(data_fim)
        if epoca:
            query += " AND ep.Descricao_Epoca = %s"
            params.append(epoca)
        if ciclo_estudo:
            query += " AND uc.Ciclo_Estudo = %s"
            params.append(ciclo_estudo)

        df = pd.read_sql(query, conn, params=params)
        if "DataCompleta" in df.columns:
            df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])

        if hide_online and "is_online" in df.columns:
            df = df[df["is_online"] != 1]
        if deduplicate_concurrent and "Flag_Evento_Agregado" in df.columns:
            df = df[df["Flag_Evento_Agregado"] != 1]
        if hide_ghost_sessions and "Numero_Presencas" in df.columns:
            df = df[df["Numero_Presencas"] > 0]

        return df
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_etl_quality_metrics() -> dict:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Facto_Ocupacao")
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM Facto_Ocupacao f
            LEFT JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            LEFT JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            LEFT JOIN Dim_Curso c ON f.SK_Curso = c.SK_Curso
            LEFT JOIN Dim_Responsavel r ON f.SK_Responsavel = r.SK_Responsavel
            WHERE e.Edificio = 'N/D'
               OR e.Nome_Espaco = 'N/D'
               OR uc.Designacao_UC IN ('N/D', 'SEM_UNIDADE / RESERVA_ADMIN')
               OR uc.Ciclo_Estudo = 'N/D'
               OR c.Nome_Curso = 'N/D'
               OR c.Codigo_Curso = 'N/D'
               OR r.Docente_Responsavel IN ('N/D', 'Indefinido/N.D.')
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
            query += " AND d.Ano_Escolar = %s"
            params.append(ano_letivo)
        if semestre is not None:
            query += " AND d.Semestre = %s"
            params.append(semestre)
        if departamento:
            query += " AND e.Escola_Responsavel = %s"
            params.append(departamento)

        query += " GROUP BY d.DiaSemana, h.Hora ORDER BY h.Hora"
        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()
