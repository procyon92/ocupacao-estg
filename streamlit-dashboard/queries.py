from __future__ import annotations
import logging
import pymysql
import pandas as pd
import streamlit as st
from db import get_connection
from config import (
    Omisso, LAB_CATEGORY, WEEKDAY_ORDER,
    CACHE_TTL_HOT, CACHE_TTL_WARM, CACHE_TTL_COLD,
)

logger = logging.getLogger(__name__)

# Helpers

_WEEKDAY_FIELD = ", ".join(f"'{d}'" for d in WEEKDAY_ORDER)

def _weekday_order_clause(col: str = "d.DiaSemana") -> str:
    # Garante que os dias da semana aparecem na ordem certa (Seg → Sex)
    return f"FIELD({col}, {_WEEKDAY_FIELD})"


def _safe_read(sql: str, conn, params=None) -> pd.DataFrame:
    # Corre a query e devolve um DataFrame; se der erro, mostra mensagem e devolve DF vazio
    try:
        p = tuple(params) if params else None
        return pd.read_sql(sql, conn, params=p)
    except pymysql.Error as exc:
        logger.exception("Query failed: %s", exc)
        st.error(f"Erro de base de dados: {exc}")
        return pd.DataFrame()


# Mapa de filtros em cascata
# Cada entrada define como ligar um filtro à tabela de factos:
# (alias_select, coluna, tabela_dim, alias_dim, fk_na_facto)
_FILTER_COLUMNS: dict[str, tuple[str, str, str, str, str]] = {
    "ano_letivo":       ("d",  "Ano_Escolar",       "Dim_Data",               "d",  "SK_Data"),
    "semestre":         ("d",  "Semestre",           "Dim_Data",               "d",  "SK_Data"),
    "escola":           ("e",  "Escola_Responsavel", "Dim_Espaco",             "e",  "SK_Espaco"),
    "edificio":         ("e",  "Edificio",           "Dim_Espaco",             "e",  "SK_Espaco"),
    "categoria_espaco": ("e",  "Categoria_Espaco",   "Dim_Espaco",             "e",  "SK_Espaco"),
    "espaco":           ("e",  "Nome_Espaco",        "Dim_Espaco",             "e",  "SK_Espaco"),
    "ciclo_estudo":     ("uc", "Ciclo_Estudo",       "Dim_Unidade_Curricular", "uc", "SK_Unidade_Curricular"),
    "curso":            ("c",  "Nome_Curso",         "Dim_Curso",              "c",  "SK_Curso"),
    "uc":               ("uc", "Designacao_UC",      "Dim_Unidade_Curricular", "uc", "SK_Unidade_Curricular"),
}


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_cascade_options(
    target_column: str,
    parent_filters: dict | None = None,
    only_labs: bool = False,
) -> list:
    # Devolve os valores distintos de uma coluna, filtrando pelos pais já selecionados
    col_info = _FILTER_COLUMNS.get(target_column)
    if not col_info:
        return []

    alias, column, dim_table, dim_alias, fk_col = col_info
    conn = get_connection()
    try:
        joined: set[tuple[str, str]] = set()
        from_parts = ["Facto_Ocupacao f"]
        where: list[str] = [f"{alias}.{column} != %s"]
        params: list = [Omisso.ND]

        def _join(tbl: str, al: str, fk: str) -> None:
            # Só faz o JOIN se ainda não foi feito (evita duplicados)
            if (tbl, al) not in joined:
                joined.add((tbl, al))
                from_parts.append(f"JOIN {tbl} {al} ON f.{fk} = {al}.{fk}")

        _join(dim_table, dim_alias, fk_col)

        for pcol, pval in (parent_filters or {}).items():
            if pcol == target_column or pcol not in _FILTER_COLUMNS:
                continue
            p_alias, p_col, p_dim, p_dim_alias, p_fk = _FILTER_COLUMNS[pcol]
            _join(p_dim, p_dim_alias, p_fk)
            where.append(f"{p_alias}.{p_col} = %s")
            params.append(pval)

        if only_labs:
            _join("Dim_Espaco", "e", "SK_Espaco")
            where.append("e.Categoria_Espaco = %s")
            params.append(LAB_CATEGORY)

        sql = (
            f"SELECT DISTINCT {alias}.{column} AS val "
            f"FROM {' '.join(from_parts)} "
            f"WHERE {' AND '.join(where)} "
            f"ORDER BY val"
        )
        df = _safe_read(sql, conn, params)
        return df["val"].tolist() if "val" in df.columns else []
    finally:
        conn.close()


# Lookups de dimensões

@st.cache_data(ttl=CACHE_TTL_COLD)
def get_anos_letivos() -> list[str]:
    return get_cascade_options("ano_letivo")


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_escolas() -> list[str]:
    conn = get_connection()
    try:
        sql = (
            "SELECT DISTINCT Escola_Responsavel AS val FROM Dim_Espaco "
            "WHERE Escola_Responsavel NOT IN (%s, %s) ORDER BY val"
        )
        df = _safe_read(sql, conn, [Omisso.ND, Omisso.INDEFINIDO])
        return df["val"].tolist() if "val" in df.columns else []
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_departamentos() -> dict[str, str]:
    # Devolve {label_curto: valor_completo_no_DW} para usar nos filtros
    conn = get_connection()
    try:
        sql = (
            "SELECT DISTINCT TRIM(Departamento) AS val FROM Dim_Espaco "
            # Exclui nulos, strings vazias, e valores omissos
            "WHERE Departamento IS NOT NULL "
            "  AND TRIM(Departamento) != '' "
            "  AND TRIM(Departamento) NOT IN (%s, %s) "
            "ORDER BY val"
        )
        df = _safe_read(sql, conn, [Omisso.ND, Omisso.INDEFINIDO])
        result: dict[str, str] = {}
        for v in df.get("val", pd.Series()).tolist():
            # Remove o prefixo "Departamento de/do" para o label ficar mais limpo
            label = v.replace("Departamento de ", "").replace("Departamento do ", "").strip()
            result[label] = v
        return result
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_edificios(escola: str | None = None, only_labs: bool = False) -> list[str]:
    pf = {"escola": escola} if escola else {}
    return get_cascade_options("edificio", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_categorias(edificio: str | None = None, only_labs: bool = False) -> list[str]:
    pf = {"edificio": edificio} if edificio else {}
    return get_cascade_options("categoria_espaco", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_espacos(
    edificio: str | None = None,
    categoria: str | None = None,
    departamento: str | None = None,
    only_labs: bool = False,
) -> list[str]:
    # Implementação única para espaços — evita ter a lógica duplicada em vários sítios
    conn = get_connection()
    try:
        where: list[str] = ["Nome_Espaco != %s", "is_online != 1"]
        params: list = [Omisso.ND]
        if edificio:
            where.append("Edificio = %s");          params.append(edificio)
        if categoria:
            where.append("Categoria_Espaco = %s");  params.append(categoria)
        if departamento:
            where.append("Departamento = %s");      params.append(departamento)
        if only_labs:
            where.append("Categoria_Espaco = %s");  params.append(LAB_CATEGORY)
        sql = (
            f"SELECT DISTINCT Nome_Espaco AS val FROM Dim_Espaco "
            f"WHERE {' AND '.join(where)} ORDER BY val"
        )
        df = _safe_read(sql, conn, params)
        return df["val"].tolist() if "val" in df.columns else []
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_ciclos_estudo(only_labs: bool = False) -> list[str]:
    return get_cascade_options("ciclo_estudo", only_labs=only_labs)


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_cursos(ciclo: str | None = None, only_labs: bool = False) -> list[str]:
    pf = {"ciclo_estudo": ciclo} if ciclo else {}
    return get_cascade_options("curso", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_ucs(curso: str | None = None, only_labs: bool = False) -> list[str]:
    pf = {"curso": curso} if curso else {}
    return get_cascade_options("uc", parent_filters=pf, only_labs=only_labs)


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_epocas() -> list[str]:
    conn = get_connection()
    try:
        sql = (
            "SELECT DISTINCT ep.Descricao_Epoca AS val "
            "FROM Facto_Ocupacao f "
            "JOIN Dim_Epoca ep ON f.SK_Epoca = ep.SK_Epoca "
            "WHERE ep.Descricao_Epoca != %s ORDER BY val"
        )
        df = _safe_read(sql, conn, [Omisso.ND])
        return df["val"].tolist() if "val" in df.columns else []
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_dias_semana() -> list[str]:
    conn = get_connection()
    try:
        sql = (
            "SELECT DISTINCT d.DiaSemana AS val "
            "FROM Facto_Ocupacao f JOIN Dim_Data d ON f.SK_Data = d.SK_Data "
            "WHERE d.DiaSemana NOT IN (%s, 'Domingo') "
            f"ORDER BY {_weekday_order_clause('d.DiaSemana')}"
        )
        df = _safe_read(sql, conn, [Omisso.ND])
        return df["val"].tolist() if "val" in df.columns else []
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_semanas(ano_letivo: str | None = None, semestre: int | None = None) -> list[int]:
    # Semana 0 excluída — corresponde a dias antes do início do semestre
    conn = get_connection()
    try:
        sql = (
            "SELECT DISTINCT d.Numero_Semana_Escolar AS val "
            "FROM Facto_Ocupacao f JOIN Dim_Data d ON f.SK_Data = d.SK_Data "
            "WHERE d.Numero_Semana_Escolar > 0"
        )
        params: list = []
        if ano_letivo:
            sql += " AND d.Ano_Escolar = %s"; params.append(ano_letivo)
        if semestre is not None:
            sql += " AND d.Semestre = %s"; params.append(semestre)
        sql += " ORDER BY val"
        df = _safe_read(sql, conn, params)
        return df["val"].tolist() if "val" in df.columns else []
    finally:
        conn.close()


# Contagem de salas

@st.cache_data(ttl=CACHE_TTL_COLD)
def get_filtered_rooms_count(
    escola: str | None = None,
    edificio: str | None = None,
    departamento: str | None = None,
    categoria_espaco: str | None = None,
) -> int:
    conn = get_connection()
    try:
        where: list[str] = ["Nome_Espaco != %s", "is_online != 1"]
        params: list = [Omisso.ND]
        if escola:           where.append("Escola_Responsavel = %s"); params.append(escola)
        if departamento:     where.append("Departamento = %s");       params.append(departamento)
        if edificio:         where.append("Edificio = %s");           params.append(edificio)
        if categoria_espaco: where.append("Categoria_Espaco = %s");   params.append(categoria_espaco)
        sql = (
            f"SELECT COUNT(DISTINCT Edificio, Nome_Espaco) "
            f"FROM Dim_Espaco WHERE {' AND '.join(where)}"
        )
        df = _safe_read(sql, conn, params)
        return int(df.iloc[0, 0]) if not df.empty else 0
    finally:
        conn.close()


# Queries à tabela de factos

# SELECT base reutilizado em get_filtered_data — junta todas as dimensões de uma vez
_FACT_SELECT = """
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
        d.Numero_Semana_Escolar,
        d.Tipo_Dia,
        ep.Descricao_Epoca,
        h1.Hora   AS Hora_Inicio,
        h1.Minuto AS Minuto_Inicio,
        h2.Hora   AS Hora_Fim,
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
            WHEN h1.Hora BETWEEN 8  AND 12 THEN 'Manhã'
            WHEN h1.Hora BETWEEN 13 AND 17 THEN 'Tarde'
            WHEN h1.Hora >= 18             THEN 'Noite'
            ELSE 'Indefinido'
        END AS Periodo_Dia
    FROM Facto_Ocupacao f
    JOIN Dim_Data d                  ON f.SK_Data                  = d.SK_Data
    JOIN Dim_Hora h1                 ON f.SK_Hora_Inicio           = h1.SK_Hora
    JOIN Dim_Hora h2                 ON f.SK_Hora_Fim              = h2.SK_Hora
    JOIN Dim_Espaco e                ON f.SK_Espaco                = e.SK_Espaco
    JOIN Dim_Unidade_Curricular uc   ON f.SK_Unidade_Curricular    = uc.SK_Unidade_Curricular
    JOIN Dim_Curso c                 ON f.SK_Curso                 = c.SK_Curso
    JOIN Dim_Responsavel r           ON f.SK_Responsavel           = r.SK_Responsavel
    JOIN Dim_Tipo_Atividade ta       ON f.SK_Tipo_Atividade        = ta.SK_Tipo_Atividade
    JOIN Dim_Estado_Agendamento ea   ON f.SK_Estado_Agendamento    = ea.SK_Estado_Agendamento
    JOIN Dim_Turno t                 ON f.SK_Turno                 = t.SK_Turno
    JOIN Dim_Epoca ep                ON f.SK_Epoca                 = ep.SK_Epoca
    WHERE 1=1
"""


@st.cache_data(ttl=CACHE_TTL_WARM)
def get_filtered_data(
    ano_letivo: str | None = None,
    semestre: int | None = None,
    escola: str | None = None,
    departamento: str | None = None,
    edificio: str | None = None,
    categoria_espaco: str | None = None,
    espaco: str | None = None,
    ciclo_estudo: str | None = None,
    curso: str | None = None,
    uc: str | None = None,
    epoca: str | None = None,
    semana_escolar: int | None = None,
    only_labs: bool = False,
) -> pd.DataFrame:
    # Filtros de pós-query (hide_online, hide_ghost, etc.) ficam em transforms.apply_post_filters()
    conn = get_connection()
    try:
        sql = _FACT_SELECT
        params: list = []

        if ano_letivo:        sql += " AND d.Ano_Escolar = %s";              params.append(ano_letivo)
        if semestre:          sql += " AND d.Semestre = %s";                  params.append(semestre)
        if escola:            sql += " AND e.Escola_Responsavel = %s";        params.append(escola)
        if departamento:      sql += " AND e.Departamento = %s";              params.append(departamento)
        if edificio:          sql += " AND e.Edificio = %s";                  params.append(edificio)
        if categoria_espaco:  sql += " AND e.Categoria_Espaco = %s";          params.append(categoria_espaco)
        if espaco:            sql += " AND e.Nome_Espaco = %s";               params.append(espaco)
        if ciclo_estudo:      sql += " AND uc.Ciclo_Estudo = %s";             params.append(ciclo_estudo)
        if curso:             sql += " AND c.Nome_Curso = %s";                params.append(curso)
        if uc:                sql += " AND uc.Designacao_UC = %s";            params.append(uc)
        if epoca:             sql += " AND ep.Descricao_Epoca = %s";          params.append(epoca)
        if semana_escolar:    sql += " AND d.Numero_Semana_Escolar = %s";     params.append(semana_escolar)
        if only_labs:         sql += " AND e.Categoria_Espaco = %s";          params.append(LAB_CATEGORY)

        return _safe_read(sql, conn, params)
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_WARM)
def get_space_detail_data(
    space_name: str,
    ano_escolar: str | None = None,
    semestre: int | None = None,
    semana_escolar: int | None = None,
) -> pd.DataFrame:
    conn = get_connection()
    try:
        sql = """
            SELECT
                d.DataCompleta, d.DiaSemana,
                h1.Hora   AS Hora_Inicio, h1.Minuto AS Minuto_Inicio,
                h2.Hora   AS Hora_Fim,   h2.Minuto AS Minuto_Fim,
                f.Duracao_Minutos, f.Numero_Presencas, f.Flag_Evento_Agregado,
                e.Edificio, e.Nome_Espaco,
                c.Nome_Curso,
                uc.Codigo_UC, uc.Designacao_UC,
                r.Docente_Responsavel,
                ta.Designacao_Atividade,
                ea.Estado,
                t.Designacao_Turno,
                ep.Descricao_Epoca,
                d.Ano_Escolar, d.Semestre,
                d.Numero_Semana_Escolar
            FROM Facto_Ocupacao f
            JOIN Dim_Data d                ON f.SK_Data                = d.SK_Data
            JOIN Dim_Hora h1               ON f.SK_Hora_Inicio         = h1.SK_Hora
            JOIN Dim_Hora h2               ON f.SK_Hora_Fim            = h2.SK_Hora
            JOIN Dim_Espaco e              ON f.SK_Espaco              = e.SK_Espaco
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular  = uc.SK_Unidade_Curricular
            JOIN Dim_Curso c               ON f.SK_Curso               = c.SK_Curso
            JOIN Dim_Responsavel r         ON f.SK_Responsavel         = r.SK_Responsavel
            JOIN Dim_Tipo_Atividade ta     ON f.SK_Tipo_Atividade      = ta.SK_Tipo_Atividade
            JOIN Dim_Estado_Agendamento ea ON f.SK_Estado_Agendamento  = ea.SK_Estado_Agendamento
            JOIN Dim_Turno t               ON f.SK_Turno               = t.SK_Turno
            JOIN Dim_Epoca ep              ON f.SK_Epoca               = ep.SK_Epoca
            WHERE e.Nome_Espaco = %s
        """
        params: list = [space_name]
        if ano_escolar:
            sql += " AND d.Ano_Escolar = %s";           params.append(ano_escolar)
        if semestre is not None:
            sql += " AND d.Semestre = %s";              params.append(semestre)
        if semana_escolar is not None:
            sql += " AND d.Numero_Semana_Escolar = %s"; params.append(semana_escolar)
        sql += " ORDER BY d.DataCompleta, h1.Hora, h1.Minuto"
        return _safe_read(sql, conn, params)
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_occupancy_by_slot(
    ano_letivo: str | None = None,
    semestre: int | None = None,
    escola: str | None = None,
    edificio: str | None = None,
    categoria_espaco: str | None = None,
) -> pd.DataFrame:
    conn = get_connection()
    try:
        sql = """
            SELECT d.DiaSemana, h1.Hora AS Hora_Inicio,
                   COUNT(DISTINCT f.SK_Espaco) AS Salas_Ocupadas
            FROM Facto_Ocupacao f
            JOIN Dim_Data d   ON f.SK_Data = d.SK_Data
            JOIN Dim_Hora h1  ON f.SK_Hora_Inicio = h1.SK_Hora
            JOIN Dim_Espaco e ON f.SK_Espaco = e.SK_Espaco
            WHERE 1=1
        """
        params: list = []
        if ano_letivo:       sql += " AND d.Ano_Escolar = %s";        params.append(ano_letivo)
        if semestre:         sql += " AND d.Semestre = %s";            params.append(semestre)
        if escola:           sql += " AND e.Escola_Responsavel = %s";  params.append(escola)
        if edificio:         sql += " AND e.Edificio = %s";            params.append(edificio)
        if categoria_espaco: sql += " AND e.Categoria_Espaco = %s";    params.append(categoria_espaco)
        sql += (
            f" GROUP BY d.DiaSemana, h1.Hora"
            f" ORDER BY {_weekday_order_clause('d.DiaSemana')}, h1.Hora"
        )
        return _safe_read(sql, conn, params)
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_HOT)
def get_free_rooms_by_interval(
    data_pesquisa: str,
    hora_inicio: int,
    hora_fim: int,
    escola: str | None = None,
    departamento: str | None = None,
    edificio: str | None = None,
    categoria_espaco: str | None = None,
) -> pd.DataFrame:
    # LEFT JOIN com subquery de salas ocupadas — o que ficar NULL está livre
    conn = get_connection()
    try:
        subquery_params: list = [data_pesquisa, hora_fim, hora_inicio]
        main_params: list = [Omisso.ND]
        main_where: list[str] = [
            "ocupadas.SK_Espaco IS NULL",
            "e_total.Nome_Espaco != %s",
            "e_total.is_online != 1",
        ]
        if escola:           main_where.append("e_total.Escola_Responsavel = %s"); main_params.append(escola)
        if departamento:     main_where.append("e_total.Departamento = %s");       main_params.append(departamento)
        if edificio:         main_where.append("e_total.Edificio = %s");           main_params.append(edificio)
        if categoria_espaco: main_where.append("e_total.Categoria_Espaco = %s");   main_params.append(categoria_espaco)

        sql = f"""
            SELECT
                e_total.Edificio,
                e_total.Nome_Espaco        AS Sala,
                e_total.Categoria_Espaco   AS Categoria,
                e_total.Escola_Responsavel AS Escola
            FROM Dim_Espaco e_total
            LEFT JOIN (
                SELECT DISTINCT f.SK_Espaco
                FROM Facto_Ocupacao f
                JOIN Dim_Data d  ON f.SK_Data        = d.SK_Data
                JOIN Dim_Hora h1 ON f.SK_Hora_Inicio = h1.SK_Hora
                JOIN Dim_Hora h2 ON f.SK_Hora_Fim    = h2.SK_Hora
                WHERE d.DataCompleta = %s AND h1.Hora < %s AND h2.Hora > %s
            ) ocupadas ON e_total.SK_Espaco = ocupadas.SK_Espaco
            WHERE {' AND '.join(main_where)}
            ORDER BY e_total.Edificio, e_total.Nome_Espaco
        """
        return _safe_read(sql, conn, subquery_params + main_params)
    finally:
        conn.close()


# Qualidade do ETL

@st.cache_data(ttl=CACHE_TTL_COLD)
def get_etl_quality_metrics() -> dict[str, int]:
    # Conta totais e erros numa única query — evita dois round-trips à BD
    conn = get_connection()
    try:
        sql = """
            SELECT
                COUNT(*) AS total,
                SUM(CASE
                    WHEN e.Edificio = %s
                      OR e.Nome_Espaco = %s
                      OR uc.Designacao_UC IN (%s, %s)
                      OR uc.Ciclo_Estudo = %s
                      OR c.Nome_Curso = %s
                      OR c.Codigo_Curso = %s
                      OR r.Docente_Responsavel IN (%s, %s)
                    THEN 1 ELSE 0
                END) AS errors
            FROM Facto_Ocupacao f
            LEFT JOIN Dim_Espaco e              ON f.SK_Espaco             = e.SK_Espaco
            LEFT JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular
            LEFT JOIN Dim_Curso c               ON f.SK_Curso              = c.SK_Curso
            LEFT JOIN Dim_Responsavel r         ON f.SK_Responsavel        = r.SK_Responsavel
        """
        params = [
            Omisso.ND,
            Omisso.ND,
            Omisso.ND, Omisso.SEM_UNIDADE,
            Omisso.ND,
            Omisso.ND,
            Omisso.ND,
            Omisso.ND, Omisso.INDEFINIDO,
        ]
        df = _safe_read(sql, conn, params)
        if df.empty:
            return {"total": 0, "valid": 0, "errors": 0}
        total  = int(df.iloc[0]["total"])
        errors = int(df.iloc[0]["errors"] or 0)
        return {"total": total, "valid": total - errors, "errors": errors}
    except pymysql.Error as exc:
        logger.exception("ETL metrics failed: %s", exc)
        st.error(f"Erro ao carregar métricas ETL: {exc}")
        return {"total": 0, "valid": 0, "errors": 0}
    finally:
        conn.close()

@st.cache_data(ttl=CACHE_TTL_COLD)
def get_unmapped_records_count() -> dict[str, int]:
    conn = get_connection()
    # Cada entrada é (sql, params) — corre tudo com o mesmo cursor para eficiência
    _queries = {
        "UC Sem Mapeamento": (
            "SELECT COUNT(*) FROM Facto_Ocupacao f "
            "JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular = uc.SK_Unidade_Curricular "
            "WHERE uc.Designacao_UC IN (%s, %s)",
            [Omisso.ND, Omisso.SEM_UNIDADE],
        ),
        "Curso Sem Mapeamento": (
            "SELECT COUNT(*) FROM Facto_Ocupacao f "
            "JOIN Dim_Curso c ON f.SK_Curso = c.SK_Curso "
            "WHERE c.Nome_Curso = %s OR c.Codigo_Curso = %s",
            [Omisso.ND, Omisso.ND],
        ),
        "Responsável Indefinido": (
            "SELECT COUNT(*) FROM Facto_Ocupacao f "
            "JOIN Dim_Responsavel r ON f.SK_Responsavel = r.SK_Responsavel "
            "WHERE r.Docente_Responsavel IN (%s, %s)",
            [Omisso.ND, Omisso.INDEFINIDO],
        ),
        "Ghost Sessions (0 Presenças)": (
            "SELECT COUNT(*) FROM Facto_Ocupacao WHERE Numero_Presencas = 0",
            [],
        ),
    }
    result: dict[str, int] = {}
    try:
        cursor = conn.cursor()
        for label, (sql, params) in _queries.items():
            cursor.execute(sql, params)
            result[label] = cursor.fetchone()[0]
    except pymysql.Error as exc:
        logger.exception("Unmapped count failed: %s", exc)
        st.error(f"Erro ao carregar contagens: {exc}")
    finally:
        conn.close()
    return result


@st.cache_data(ttl=CACHE_TTL_COLD)
def get_ghost_sessions_trend(
    ano_escolar: str | None = None,
    semestre: int | None = None,
) -> pd.DataFrame:
    # Ghost session = aula registada com 0 presenças
    conn = get_connection()
    try:
        sql = (
            "SELECT d.Ano_Escolar, d.Mes, COUNT(*) AS Ghost_Count "
            "FROM Facto_Ocupacao f "
            "JOIN Dim_Data d ON f.SK_Data = d.SK_Data "
            "WHERE f.Numero_Presencas = 0"
        )
        params: list = []
        if ano_escolar:
            sql += " AND d.Ano_Escolar = %s"; params.append(ano_escolar)
        if semestre is not None:
            sql += " AND d.Semestre = %s"; params.append(semestre)
        sql += " GROUP BY d.Ano_Escolar, d.Mes ORDER BY d.Ano_Escolar, d.Mes"
        df = _safe_read(sql, conn, params)
        if not df.empty:
            df["Periodo"] = df["Ano_Escolar"].astype(str) + " - Mês " + df["Mes"].astype(str)
        return df
    finally:
        conn.close()


@st.cache_data(ttl=CACHE_TTL_HOT)
def get_raw_anomalies(limit: int = 100) -> pd.DataFrame:
    # LIMIT via %s — nunca interpolar diretamente na string SQL
    conn = get_connection()
    try:
        sql = """
            SELECT
                f.ID_Ocupacao,
                d.DataCompleta, d.DiaSemana,
                h1.Hora AS Hora_Inicio, h2.Hora AS Hora_Fim,
                e.Edificio, e.Nome_Espaco,
                uc.Designacao_UC, uc.Ciclo_Estudo,
                c.Nome_Curso,
                r.Docente_Responsavel,
                ta.Designacao_Atividade,
                f.Duracao_Minutos, f.Numero_Presencas,
                CASE WHEN f.Numero_Presencas = 0              THEN 'Ghost'          ELSE NULL END AS Ghost_Flag,
                CASE WHEN uc.Designacao_UC IN (%s, %s)        THEN 'Unmapped_UC'    ELSE NULL END AS UC_Flag,
                CASE WHEN c.Nome_Curso = %s                   THEN 'Unmapped_Curso' ELSE NULL END AS Curso_Flag,
                CASE WHEN r.Docente_Responsavel IN (%s, %s)   THEN 'Unmapped_Resp'  ELSE NULL END AS Resp_Flag
            FROM Facto_Ocupacao f
            JOIN Dim_Data d                ON f.SK_Data                = d.SK_Data
            JOIN Dim_Hora h1               ON f.SK_Hora_Inicio         = h1.SK_Hora
            JOIN Dim_Hora h2               ON f.SK_Hora_Fim            = h2.SK_Hora
            JOIN Dim_Espaco e              ON f.SK_Espaco              = e.SK_Espaco
            JOIN Dim_Unidade_Curricular uc ON f.SK_Unidade_Curricular  = uc.SK_Unidade_Curricular
            JOIN Dim_Curso c               ON f.SK_Curso               = c.SK_Curso
            JOIN Dim_Responsavel r         ON f.SK_Responsavel         = r.SK_Responsavel
            JOIN Dim_Tipo_Atividade ta     ON f.SK_Tipo_Atividade      = ta.SK_Tipo_Atividade
            WHERE f.Numero_Presencas = 0
               OR uc.Designacao_UC IN (%s, %s)
               OR c.Nome_Curso = %s
               OR r.Docente_Responsavel IN (%s, %s)
            ORDER BY d.DataCompleta DESC
            LIMIT %s
        """
        params = [
            # params dos CASE
            Omisso.ND, Omisso.SEM_UNIDADE,
            Omisso.ND,
            Omisso.ND, Omisso.INDEFINIDO,
            # params do WHERE
            Omisso.ND, Omisso.SEM_UNIDADE,
            Omisso.ND,
            Omisso.ND, Omisso.INDEFINIDO,
            int(limit),
        ]
        return _safe_read(sql, conn, params)
    finally:
        conn.close()