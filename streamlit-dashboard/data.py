"""
data.py — V2 data access layer.
Dynamic parameterised query builder + cascading filter lookups + period-of-day logic.
"""
import streamlit as st
import pandas as pd
import pymysql
from config import DB_CONFIG


def _get_connection():
    return pymysql.connect(**DB_CONFIG)


# ── Column alias → (table_alias, column_name, dim_table, dim_alias, join_condition) ──
_FILTER_COLUMNS = {
    "ano_letivo":      ("d", "Ano_Escolar",       "Dim_Data",        "d",  "f.SK_Data = d.SK_Data"),
    "semestre":        ("d", "Semestre",           "Dim_Data",        "d",  "f.SK_Data = d.SK_Data"),
    "departamento":    ("e", "Escola_Responsavel", "Dim_Espaco",      "e",  "f.SK_Espaco = e.SK_Espaco"),
    "edificio":        ("e", "Edificio",           "Dim_Espaco",      "e",  "f.SK_Espaco = e.SK_Espaco"),
    "categoria_espaco":("e", "Categoria_Espaco",   "Dim_Espaco",      "e",  "f.SK_Espaco = e.SK_Espaco"),
    "espaco":          ("e", "Nome_Espaco",        "Dim_Espaco",      "e",  "f.SK_Espaco = e.SK_Espaco"),
    "ciclo_estudo":    ("uc","Ciclo_Estudo",       "Dim_Unidade_Curricular", "uc", "f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular"),
    "curso":           ("c", "Nome_Curso",         "Dim_Curso",       "c",  "f.SK_Curso = c.SK_Curso"),
    "uc":              ("uc","Designacao_UC",      "Dim_Unidade_Curricular", "uc", "f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular"),
}


@st.cache_data(ttl=300)
def get_cascade_options(target_column: str, parent_filters: dict = None, only_labs: bool = False) -> list:
    """
    Return distinct values for `target_column` after applying parent filters.
    parent_filters = {"departamento": "DEI", "edificio": "Edificio A", ...}
    """
    col_info = _FILTER_COLUMNS.get(target_column)
    if not col_info:
        return []
    alias, column, dim_table, dim_alias, join_on = col_info

    conn = _get_connection()
    try:
        joins = set()
        from_clause = "Facto_Ocupacao f"
        where_clauses = [f"{alias}.{column} != 'N/D'"]
        params = []

        def _ensure_join(dim_t, dim_a):
            key = (dim_t, dim_a)
            if key not in joins:
                joins.add(key)
                nonlocal from_clause
                from_clause += f" JOIN {dim_t} {dim_a} ON f.SK_{dim_t[4:]} = {dim_a}.SK_{dim_t[4:]}"

        _ensure_join(dim_table, dim_alias)

        if parent_filters:
            for pcol, pval in parent_filters.items():
                if pcol not in _FILTER_COLUMNS:
                    continue
                if pcol == target_column:
                    continue
                p_info = _FILTER_COLUMNS[pcol]
                p_alias, p_col, p_dim, p_dim_alias, p_join = p_info
                _ensure_join(p_dim, p_dim_alias)
                where_clauses.append(f"{p_alias}.{p_col} = %s")
                params.append(pval)

        if only_labs:
            _ensure_join("Dim_Espaco", "e")
            where_clauses.append("e.Categoria_Espaco = 'Laboratório'")

        query = f"SELECT DISTINCT {alias}.{column} AS val FROM {from_clause} WHERE {' AND '.join(where_clauses)} ORDER BY val"
        df = pd.read_sql(query, conn, params=params)
        return df["val"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_anos_letivos() -> list:
    return get_cascade_options("ano_letivo")


@st.cache_data(ttl=300)
def get_semestres() -> list:
    return [1, 2]


@st.cache_data(ttl=300)
def get_departamentos() -> list:
    conn = _get_connection()
    try:
        query = "SELECT DISTINCT e.Escola_Responsavel AS val FROM Dim_Espaco e WHERE e.Escola_Responsavel NOT IN ('N/D','Indefinido/N.D.') ORDER BY val"
        df = pd.read_sql(query, conn)
        return df["val"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_edificios(departamento: str = None, only_labs: bool = False) -> list:
    pf = {}
    if departamento:
        pf["departamento"] = departamento
    return get_cascade_options("edificio", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=300)
def get_categorias(edificio: str = None, only_labs: bool = False) -> list:
    pf = {}
    if edificio:
        pf["edificio"] = edificio
    return get_cascade_options("categoria_espaco", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=300)
def get_espacos(edificio: str = None, categoria: str = None, only_labs: bool = False) -> list:
    pf = {}
    if edificio:
        pf["edificio"] = edificio
    if categoria:
        pf["categoria_espaco"] = categoria
    return get_cascade_options("espaco", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=300)
def get_ciclos_estudo(only_labs: bool = False) -> list:
    return get_cascade_options("ciclo_estudo", only_labs=only_labs)


@st.cache_data(ttl=300)
def get_cursos(ciclo: str = None, only_labs: bool = False) -> list:
    pf = {}
    if ciclo:
        pf["ciclo_estudo"] = ciclo
    return get_cascade_options("curso", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=300)
def get_ucs(curso: str = None, only_labs: bool = False) -> list:
    pf = {}
    if curso:
        pf["curso"] = curso
    return get_cascade_options("uc", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=300)
def get_epocas() -> list:
    conn = _get_connection()
    try:
        query = "SELECT DISTINCT ep.Descricao_Epoca AS val FROM Facto_Ocupacao f JOIN Dim_Epoca ep ON f.SK_Epoca = ep.SK_Epoca WHERE ep.Descricao_Epoca != 'N/D' ORDER BY val"
        df = pd.read_sql(query, conn)
        return df["val"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_total_rooms_count() -> int:
    """Total number of unique physical rooms in Dim_Espaco (excluding N/D)."""
    conn = _get_connection()
    try:
        query = "SELECT COUNT(DISTINCT Nome_Espaco) FROM Dim_Espaco WHERE Nome_Espaco != 'N/D'"
        df = pd.read_sql(query, conn)
        return int(df.iloc[0, 0])
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_dias_semana() -> list:
    """Distinct weekdays present in the fact table."""
    conn = _get_connection()
    try:
        query = "SELECT DISTINCT d.DiaSemana AS val FROM Facto_Ocupacao f JOIN Dim_Data d ON f.SK_Data = d.SK_Data WHERE d.DiaSemana NOT IN ('N/D','Domingo') ORDER BY FIELD(d.DiaSemana,'Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado')"
        df = pd.read_sql(query, conn)
        return df["val"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_semanas(ano_letivo: str = None, semestre: int = None) -> list:
    """Distinct week numbers available in the fact table, optionally filtered."""
    conn = _get_connection()
    try:
        query = "SELECT DISTINCT d.Numero_Semana AS val FROM Facto_Ocupacao f JOIN Dim_Data d ON f.SK_Data = d.SK_Data WHERE d.Numero_Semana != 0"
        params = []
        if ano_letivo:
            query += " AND d.Ano_Escolar = %s"; params.append(ano_letivo)
        if semestre is not None:
            query += " AND d.Semestre = %s"; params.append(semestre)
        query += " ORDER BY val"
        df = pd.read_sql(query, conn, params=params)
        return df["val"].tolist()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_occupancy_by_slot(
    ano_letivo: str = None,
    semestre: int = None,
    departamento: str = None,
    edificio: str = None,
    categoria_espaco: str = None,
) -> pd.DataFrame:
    """
    Return occupancy ratio per (DiaSemana, Hora_Inicio) slot.
    Ratio = occupied rooms in slot / total rooms in the filtered set.
    """
    conn = _get_connection()
    try:
        base_joins = """
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            JOIN Dim_Hora h1 ON f.SK_Hora_Inicio = h1.SK_Hora
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
        """
        where_clauses = ["1=1"]
        params = []

        if ano_letivo:
            where_clauses.append("d.Ano_Escolar = %s"); params.append(ano_letivo)
        if semestre is not None:
            where_clauses.append("d.Semestre = %s"); params.append(semestre)
        if departamento:
            where_clauses.append("e.Escola_Responsavel = %s"); params.append(departamento)
        if edificio:
            where_clauses.append("e.Edificio = %s"); params.append(edificio)
        if categoria_espaco:
            where_clauses.append("e.Categoria_Espaco = %s"); params.append(categoria_espaco)

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT
                d.DiaSemana,
                h1.Hora AS Hora_Inicio,
                COUNT(DISTINCT f.SK_Espaco) AS Salas_Ocupadas
            {base_joins}
            WHERE {where_sql}
            GROUP BY d.DiaSemana, h1.Hora
            ORDER BY FIELD(d.DiaSemana,'Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado'), h1.Hora
        """
        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()


@st.cache_data(ttl=120)
def get_filtered_data(
    ano_letivo: str = None,
    semestre: int = None,
    departamento: str = None,
    edificio: str = None,
    categoria_espaco: str = None,
    espaco: str = None,
    ciclo_estudo: str = None,
    curso: str = None,
    uc: str = None,
    epoca: str = None,
    hide_online: bool = False,
    hide_concurrent: bool = False,
    hide_ghost: bool = False,
    only_labs: bool = False,
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
                d.Ano_Escolar,
                d.Mes,
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
                c.Nome_Curso,
                r.Docente_Responsavel,
                ta.Designacao_Atividade,
                ea.Estado,
                t.Designacao_Turno,
                CASE
                    WHEN h1.Hora BETWEEN 8 AND 12 THEN 'Manhã'
                    WHEN h1.Hora BETWEEN 13 AND 17 THEN 'Tarde'
                    WHEN h1.Hora >= 18 THEN 'Noite'
                    ELSE 'Indefinido'
                END AS Periodo_Dia
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            JOIN Dim_Hora h1 ON f.SK_Hora_Inicio = h1.SK_Hora
            JOIN Dim_Hora h2 ON f.SK_Hora_Fim = h2.SK_Hora
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            JOIN Dim_Curso c ON f.SK_Curso = c.SK_Curso
            JOIN Dim_Responsavel r ON f.SK_Responsavel = r.SK_Responsavel
            JOIN Dim_Tipo_Atividade ta ON f.SK_Tipo_Atividade = ta.SK_Tipo_Atividade
            JOIN Dim_Estado_Agendamento ea ON f.SK_Estado_Agendamento = ea.SK_Estado_Agendamento
            JOIN Dim_Turno t ON f.SK_Turno = t.SK_Turno
            JOIN Dim_Epoca ep ON f.SK_Epoca = ep.SK_Epoca
            WHERE 1=1
        """
        params = []

        if ano_letivo:
            query += " AND d.Ano_Escolar = %s"; params.append(ano_letivo)
        if semestre is not None:
            query += " AND d.Semestre = %s"; params.append(semestre)
        if departamento:
            query += " AND e.Escola_Responsavel = %s"; params.append(departamento)
        if edificio:
            query += " AND e.Edificio = %s"; params.append(edificio)
        if categoria_espaco:
            query += " AND e.Categoria_Espaco = %s"; params.append(categoria_espaco)
        if espaco:
            query += " AND e.Nome_Espaco = %s"; params.append(espaco)
        if ciclo_estudo:
            query += " AND uc.Ciclo_Estudo = %s"; params.append(ciclo_estudo)
        if curso:
            query += " AND c.Nome_Curso = %s"; params.append(curso)
        if uc:
            query += " AND uc.Designacao_UC = %s"; params.append(uc)
        if epoca:
            query += " AND ep.Descricao_Epoca = %s"; params.append(epoca)
        if only_labs:
            query += " AND e.Categoria_Espaco = 'Laboratório'"

        df = pd.read_sql(query, conn, params=params)
        if "DataCompleta" in df.columns:
            df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])

        if "Docente_Responsavel" in df.columns:
            df["Docente_Responsavel"] = df["Docente_Responsavel"].apply(
                lambda x: "Indefinido/N.D." if isinstance(x, str) and len(x.strip()) <= 1 else x
            )

        if hide_online and "is_online" in df.columns:
            df = df[df["is_online"] != 1]
        if hide_concurrent and "Flag_Evento_Agregado" in df.columns:
            df = df[df["Flag_Evento_Agregado"] != 1]
        if hide_ghost and "Numero_Presencas" in df.columns:
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
        return {"total": total, "valid": valid, "errors": with_defaults}
    finally:
        conn.close()


@st.cache_data(ttl=120)
def get_space_detail_data(
    space_name: str,
    ano_escolar: str = None,
    semestre: int = None,
) -> pd.DataFrame:
    """
    Return all fact rows for a single specific space,
    with operational timetable details (day, hours, course, UC, lecturer, activity).
    """
    conn = _get_connection()
    try:
        query = """
            SELECT
                d.DataCompleta,
                d.DiaSemana,
                h1.Hora AS Hora_Inicio,
                h1.Minuto AS Minuto_Inicio,
                h2.Hora AS Hora_Fim,
                h2.Minuto AS Minuto_Fim,
                f.Duracao_Minutos,
                f.Numero_Presencas,
                f.Flag_Evento_Agregado,
                e.Edificio,
                e.Nome_Espaco,
                c.Nome_Curso,
                uc.Codigo_UC,
                uc.Designacao_UC,
                r.Docente_Responsavel,
                ta.Designacao_Atividade,
                ea.Estado,
                t.Designacao_Turno,
                ep.Descricao_Epoca,
                d.Ano_Escolar,
                d.Semestre
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            JOIN Dim_Hora h1 ON f.SK_Hora_Inicio = h1.SK_Hora
            JOIN Dim_Hora h2 ON f.SK_Hora_Fim = h2.SK_Hora
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            JOIN Dim_Curso c ON f.SK_Curso = c.SK_Curso
            JOIN Dim_Responsavel r ON f.SK_Responsavel = r.SK_Responsavel
            JOIN Dim_Tipo_Atividade ta ON f.SK_Tipo_Atividade = ta.SK_Tipo_Atividade
            JOIN Dim_Estado_Agendamento ea ON f.SK_Estado_Agendamento = ea.SK_Estado_Agendamento
            JOIN Dim_Turno t ON f.SK_Turno = t.SK_Turno
            JOIN Dim_Epoca ep ON f.SK_Epoca = ep.SK_Epoca
            WHERE e.Nome_Espaco = %s
        """
        params = [space_name]
        if ano_escolar:
            query += " AND d.Ano_Escolar = %s"
            params.append(ano_escolar)
        if semestre is not None:
            query += " AND d.Semestre = %s"
            params.append(semestre)

        query += " ORDER BY d.DataCompleta, h1.Hora, h1.Minuto"

        df = pd.read_sql(query, conn, params=params)
        if "DataCompleta" in df.columns:
            df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])
        if "Docente_Responsavel" in df.columns:
            df["Docente_Responsavel"] = df["Docente_Responsavel"].apply(
                lambda x: "Indefinido/N.D." if isinstance(x, str) and len(x.strip()) <= 1 else x
            )
        return df
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_ghost_sessions_trend(
    ano_escolar: str = None,
    semestre: int = None,
) -> pd.DataFrame:
    """Monthly count of ghost sessions (Numero_Presencas = 0) for trend analysis."""
    conn = _get_connection()
    try:
        query = """
            SELECT
                d.Ano_Escolar,
                d.Mes,
                COUNT(*) AS Ghost_Count
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            WHERE f.Numero_Presencas = 0
        """
        params = []
        if ano_escolar:
            query += " AND d.Ano_Escolar = %s"; params.append(ano_escolar)
        if semestre is not None:
            query += " AND d.Semestre = %s"; params.append(semestre)

        query += " GROUP BY d.Ano_Escolar, d.Mes ORDER BY d.Ano_Escolar, d.Mes"
        df = pd.read_sql(query, conn, params=params)
        df["Periodo"] = df["Ano_Escolar"].astype(str) + " - Mês " + df["Mes"].astype(str)
        return df
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_unmapped_records_count() -> dict:
    """Count of records where key dimensions are mapped to 'N/D' or surrogate defaults."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        queries = {
            "UC Sem Mapeamento": """
                SELECT COUNT(*) FROM Facto_Ocupacao f
                JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
                WHERE uc.Designacao_UC IN ('N/D', 'SEM_UNIDADE / RESERVA_ADMIN')
            """,
            "Curso Sem Mapeamento": """
                SELECT COUNT(*) FROM Facto_Ocupacao f
                JOIN Dim_Curso c ON f.SK_Curso = c.SK_Curso
                WHERE c.Nome_Curso = 'N/D' OR c.Codigo_Curso = 'N/D'
            """,
            "Responsável Indefinido": """
                SELECT COUNT(*) FROM Facto_Ocupacao f
                JOIN Dim_Responsavel r ON f.SK_Responsavel = r.SK_Responsavel
                WHERE r.Docente_Responsavel IN ('N/D', 'Indefinido/N.D.')
            """,
            "Ghost Sessions (0 Presenças)": """
                SELECT COUNT(*) FROM Facto_Ocupacao
                WHERE Numero_Presencas = 0
            """,
        }
        result = {}
        for label, q in queries.items():
            cursor.execute(q)
            result[label] = cursor.fetchone()[0]
        return result
    finally:
        conn.close()


@st.cache_data(ttl=300)
def get_raw_anomalies(limit: int = 100) -> pd.DataFrame:
    """
    Return raw fact rows where anomalies exist (ghost sessions or unmapped dimensions),
    for audit inspection. Limited to `limit` rows.
    """
    conn = _get_connection()
    try:
        query = f"""
            SELECT
                f.ID_Ocupacao,
                d.DataCompleta,
                d.DiaSemana,
                h1.Hora AS Hora_Inicio,
                h2.Hora AS Hora_Fim,
                e.Edificio,
                e.Nome_Espaco,
                uc.Designacao_UC,
                uc.Ciclo_Estudo,
                c.Nome_Curso,
                r.Docente_Responsavel,
                ta.Designacao_Atividade,
                f.Duracao_Minutos,
                f.Numero_Presencas,
                CASE WHEN f.Numero_Presencas = 0 THEN 'Ghost' ELSE NULL END AS Ghost_Flag,
                CASE WHEN uc.Designacao_UC IN ('N/D','SEM_UNIDADE / RESERVA_ADMIN') THEN 'Unmapped_UC' ELSE NULL END AS UC_Flag,
                CASE WHEN c.Nome_Curso = 'N/D' THEN 'Unmapped_Curso' ELSE NULL END AS Curso_Flag,
                CASE WHEN r.Docente_Responsavel IN ('N/D','Indefinido/N.D.') THEN 'Unmapped_Resp' ELSE NULL END AS Resp_Flag
            FROM Facto_Ocupacao f
            JOIN Dim_Data d ON f.SK_Data = d.SK_Data
            JOIN Dim_Hora h1 ON f.SK_Hora_Inicio = h1.SK_Hora
            JOIN Dim_Hora h2 ON f.SK_Hora_Fim = h2.SK_Hora
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            JOIN Dim_Curso c ON f.SK_Curso = c.SK_Curso
            JOIN Dim_Responsavel r ON f.SK_Responsavel = r.SK_Responsavel
            JOIN Dim_Tipo_Atividade ta ON f.SK_Tipo_Atividade = ta.SK_Tipo_Atividade
            WHERE f.Numero_Presencas = 0
               OR uc.Designacao_UC IN ('N/D','SEM_UNIDADE / RESERVA_ADMIN')
               OR c.Nome_Curso = 'N/D'
               OR r.Docente_Responsavel IN ('N/D','Indefinido/N.D.')
            ORDER BY d.DataCompleta DESC
            LIMIT {int(limit)}
        """
        df = pd.read_sql(query, conn)
        if "DataCompleta" in df.columns:
            df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])
        if "Docente_Responsavel" in df.columns:
            df["Docente_Responsavel"] = df["Docente_Responsavel"].apply(
                lambda x: "Indefinido/N.D." if isinstance(x, str) and len(x.strip()) <= 1 else x
            )
        return df
    finally:
        conn.close()
        
@st.cache_data(ttl=60)
def get_free_rooms_by_interval(
    data_pesquisa: str,       # Formato 'YYYY-MM-DD'
    hora_inicio: int,         # Ex: 14
    hora_fim: int,            # Ex: 17
    departamento: str = None,
    edificio: str = None,
    categoria_espaco: str = None
) -> pd.DataFrame:
    """
    Retorna todas as salas que NÃO têm qualquer agendamento 
    que se sobreponha ao intervalo entre hora_inicio e hora_fim.
    """
    conn = _get_connection()
    try:
        # 1. Parâmetros da subquery (as condições temporais)
        subquery_where = [
            "d.DataCompleta = %s",
            "h1.Hora < %s",  # Hora_Inicio do evento < Hora_Fim da pesquisa
            "h2.Hora > %s"   # Hora_Fim do evento > Hora_Inicio da pesquisa
        ]
        params = [data_pesquisa, hora_fim, hora_inicio]

        # 2. Parâmetros da query principal (filtros geográficos/tipologia)
        main_where = [
            "ocupadas.SK_Espaco IS NULL",
            "e_total.Nome_Espaco != 'N/D'",
            "e_total.is_online != 1"
        ]

        if departamento:
            main_where.append("e_total.Escola_Responsavel = %s")
            params.append(departamento)
        if edificio:
            main_where.append("e_total.Edificio = %s")
            params.append(edificio)
        if categoria_espaco:
            main_where.append("e_total.Categoria_Espaco = %s")
            params.append(categoria_espaco)

        # Montagem da Query corrigida
        query = f"""
            SELECT 
                e_total.Edificio,
                e_total.Nome_Espaco AS Sala,
                e_total.Categoria_Espaco AS Categoria,
                e_total.Escola_Responsavel AS Departamento
            FROM Dim_Espaco e_total
            LEFT JOIN (
                SELECT DISTINCT f.SK_Espaco
                FROM Facto_Ocupacao f
                JOIN Dim_Data d ON f.SK_Data = d.SK_Data
                JOIN Dim_Hora h1 ON f.SK_Hora_Inicio = h1.SK_Hora
                JOIN Dim_Hora h2 ON f.SK_Hora_Fim = h2.SK_Hora
                WHERE {' AND '.join(subquery_where)}
            ) ocupadas ON e_total.SK_Espaco = ocupadas.SK_Espaco
            WHERE {' AND '.join(main_where)}
            ORDER BY e_total.Edificio, e_total.Nome_Espaco
        """
        
        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()
        
@st.cache_data(ttl=300)
def get_filtered_rooms_count(
    departamento: str = None,
    edificio: str = None,
    categoria_espaco: str = None
) -> int:
    """Retorna o número total de espaços físicos que cumprem os filtros selecionados."""
    conn = _get_connection()
    try:
        where_clauses = ["Nome_Espaco != 'N/D'", "is_online != 1"]
        params = []
        
        if departamento:
            where_clauses.append("Escola_Responsavel = %s")
            params.append(departamento)
        if edificio:
            where_clauses.append("Edificio = %s")
            params.append(edificio)
        if categoria_espaco:
            where_clauses.append("Categoria_Espaco = %s")
            params.append(categoria_espaco)
            
        query = f"SELECT COUNT(DISTINCT Nome_Espaco) FROM Dim_Espaco WHERE {' AND '.join(where_clauses)}"
        df = pd.read_sql(query, conn, params=params)
        return int(df.iloc[0, 0])
    finally:
        conn.close()