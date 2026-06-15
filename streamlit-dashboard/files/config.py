"""
config.py — Centralized configuration: DB, UI constants, cache TTLs, sentinel values.
"""
from __future__ import annotations

# ── Application ──────────────────────────────────────────────────────
APP_TITLE = "ESTG Dashboard"
PAGE_TITLE = "ESTG — Ocupação de Espaços"
FAVICON = "🏫"

# ── Database ─────────────────────────────────────────────────────────
DB_CONFIG: dict = {
    "host": "localhost",
    "port": 3306,
    "user": "dashboard_user",
    "password": "secret",
    "database": "estg_dw",
    "charset": "utf8mb4",
}

# ── Cache TTLs (seconds) ──────────────────────────────────────────────
CACHE_TTL_HOT  = 60    # real-time: free rooms, raw anomalies
CACHE_TTL_WARM = 120   # semi-dynamic: filtered fact data
CACHE_TTL_COLD = 300   # mostly static: dim lookups, quality metrics

# ── Sentinel / placeholder values ─────────────────────────────────────
class Sentinel:
    """String constants used as 'unknown' markers in the data warehouse."""
    ND          = "N/D"
    INDEFINIDO  = "Indefinido/N.D."
    SEM_UNIDADE = "SEM_UNIDADE / RESERVA_ADMIN"
    NO_FILTER   = "Todos"
    NO_FILTER_F = "Todas"
    ALL_DEPTS   = "— Todos os departamentos —"
    NO_ROOM     = "— Selecione um espaço —"

    BAD_DOCENTES: tuple = ("N/D", "Indefinido/N.D.")
    BAD_UCS: tuple      = ("N/D", "SEM_UNIDADE / RESERVA_ADMIN")

# ── Category constants ────────────────────────────────────────────────
LAB_CATEGORY = "Laboratório"

WEEKDAY_ORDER = (
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira", "Sexta-feira", "Sábado",
)

COLORS = {
    "kpi_bg":    "#FFFFFF",
    "kpi_label": "#64748B",
    "kpi_value": "#1B2139",
}

DIMENSION_COVERAGE_COLS: dict = {
    "Edifício":       "Edificio",
    "Espaço":         "Nome_Espaco",
    "Categoria":      "Categoria_Espaco",
    "UC":             "Designacao_UC",
    "Ciclo Estudo":   "Ciclo_Estudo",
    "Curso":          "Nome_Curso",
    "Tipo Atividade": "Designacao_Atividade",
    "Responsável":    "Docente_Responsavel",
    "Estado":         "Estado",
    "Turno":          "Designacao_Turno",
}
