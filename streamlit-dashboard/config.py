from __future__ import annotations

# Aplicação
APP_TITLE = "ESTG Dashboard"
PAGE_TITLE = "ESTG — Ocupação de Espaços"
FAVICON = "🏫"

# Base de dados
DB_CONFIG: dict = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "dw_ocupacao",
    "charset": "utf8mb4",
}

# TTLs de cache (em segundos) (Time to Live/Tempo de Vida)
CACHE_TTL_HOT  = 60
CACHE_TTL_WARM = 120
CACHE_TTL_COLD = 300

# Valores omissos
class Omisso:
    ND          = "N/D"
    INDEFINIDO  = "Indefinido/N.D."
    SEM_UNIDADE = "SEM_UNIDADE / RESERVA_ADMIN"
    NO_FILTER   = "Todos"
    NO_FILTER_F = "Todas"
    ALL_DEPTS   = "— Todos os departamentos —"
    NO_ROOM     = "— Selecione um espaço —"

    # Grupos de valores omissos usados em filtros IN (%s, %s)
    BAD_DOCENTES: tuple = ("N/D", "Indefinido/N.D.")
    BAD_UCS: tuple      = ("N/D", "SEM_UNIDADE / RESERVA_ADMIN")

# Autenticação
AUTH_CREDENTIALS: dict[str, str] = {
    "admin": "estg2025",
}

# Alias para compatibilidade com versões antigas de auth.py que usam AUTH_USERS
AUTH_USERS = AUTH_CREDENTIALS

# Constantes de negócio

# Minutos disponíveis por dia (8h às 24h) — base para calcular ocupação relativa
DAILY_CAPACITY_MINUTES = 960

LAB_CATEGORY = "Laboratório"

# Ordem dos dias da semana para gráficos e queries ORDER BY FIELD(...)
WEEKDAY_ORDER = (
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira", "Sexta-feira", "Sábado",
)

# Versão completa para as vistas de calendário
WEEKDAY_ORDER_FULL = (
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira", "Sexta-feira", "Sábado", "Domingo",
)

# Abreviações dos dias — índice corresponde a WEEKDAY_ORDER_FULL
WEEKDAY_SHORT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

# Dicionário de tradução dia completo → abreviação
WEEKDAY_PT = {
    "Segunda-feira": "Seg", "Terça-feira": "Ter", "Quarta-feira": "Qua",
    "Quinta-feira": "Qui", "Sexta-feira": "Sex", "Sábado": "Sáb", "Domingo": "Dom",
}

# Cores
COLORS = {
    # Cartões KPI
    "kpi_bg":       "#FFFFFF",
    "kpi_label":    "#64748B",
    "kpi_value":    "#1B2139",
    # Gráficos — usados em plots.py
    "primary":      "#3B63FB",
    "chart_grid":   "#E8EDF5",
    "donut_palette": [
        "#3B63FB", "#10B981", "#F59E0B", "#EF4444",
        "#8B5CF6", "#06B6D4", "#F97316", "#EC4899",
        "#14B8A6", "#84CC16", "#6366F1", "#FB923C",
    ],
    # Paleta para turnos/UCs nos calendários — roda se houver mais UCs do que cores
    "turno_palette": [
        "#3B63FB", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444",
        "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1",
        "#84CC16", "#06B6D4", "#A855F7", "#FB923C", "#22D3EE",
    ],
}

# Mapeamento nome legível → coluna no DataFrame, usado na página de qualidade do ETL
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