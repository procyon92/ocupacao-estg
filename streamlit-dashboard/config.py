"""
config.py — Configuração centralizada do Dashboard.
Define constantes de estilo, paleta de cores, e credenciais de BD.
"""
import os
from dotenv import load_dotenv

# Carrega .env da raiz do ETL
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ─── Conexão MySQL ───────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "dw_ocupacao"),
    "charset": "utf8mb4",
}

# ─── Paleta de Cores ─────────────────────────────────────────────────
COLORS = {
    # Sidebar
    "sidebar_bg": "#1B2139",
    "sidebar_text": "#FFFFFF",
    "sidebar_active": "#3B63FB",
    # KPIs
    "kpi_bg": "#F6F8FC",
    "kpi_label": "#7B8AA6",
    "kpi_value": "#1B2139",
    # Charts
    "primary": "#3B63FB",
    "secondary": "#22D3EE",
    "accent": "#F59E0B",
    "success": "#10B981",
    "danger": "#EF4444",
    "warning": "#F59E0B",
    "chart_bg": "#F6F8FC",
    "chart_grid": "#E2E8F0",
    # Status badges
    "badge_green": "#D1FAE5",
    "badge_green_text": "#065F46",
    "badge_yellow": "#FEF3C7",
    "badge_yellow_text": "#92400E",
    "badge_red": "#FEE2E2",
    "badge_red_text": "#991B1B",
    # Donut
    "donut_palette": [
        "#3B63FB", "#22D3EE", "#F59E0B", "#10B981",
        "#EF4444", "#8B5CF6", "#EC4899", "#6366F1",
        "#14B8A6", "#F97316", "#84CC16", "#06B6D4",
    ],
    # Quality section
    "quality_green": "#D1FAE5",
    "quality_yellow": "#FEF3C7",
    "quality_red": "#FEE2E2",
}

# ─── Layout ──────────────────────────────────────────────────────────
APP_TITLE = "Gestão de Ocupação"
PAGE_TITLE = "Dashboard — Análise de Ocupação ESTG"
FAVICON = "📊"

# ─── Credenciais de Acesso (Demonstração) ────────────────────────────
AUTH_USERS = {
    "admin": "estg2025",
    "docente": "estg2025",
}
