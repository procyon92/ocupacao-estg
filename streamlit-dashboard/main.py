"""
main.py — Ponto de entrada da aplicação Streamlit.
Implementa o layout de sidebar + content area conforme Frame.png.

Executar:  streamlit run main.py
"""
import sys
import os

# Garantir que o diretório do dashboard está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from config import APP_TITLE, PAGE_TITLE, FAVICON, COLORS
from auth import check_auth, login_page, logout
from data import get_anos_letivos, get_semestres, get_edificios, get_espacos, get_departamentos, get_ciclos_estudo, get_epocas, get_ciclos_estudo, get_epocas
from pages import page_dashboard, page_ocupacao, page_espacos, page_relatorios, page_etl_logs

# ─── Configuração da Página ──────────────────────────────────────────
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS Global ──────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Import Google Font ─────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ── Global ─────────────────────────────────────────────────── */
    html, body, [data-testid="stApp"] {
        font-family: 'Inter', sans-serif !important;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* ── Sidebar ────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B2139 0%, #141929 100%) !important;
        min-width: 230px !important;
        max-width: 230px !important;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        color: rgba(255,255,255,0.75) !important;
        font-size: 0.92rem !important;
        font-weight: 500 !important;
        padding: 0.6rem 1rem !important;
        border-radius: 10px !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.08) !important;
        color: white !important;
    }
    [data-testid="stSidebar"] .stRadio label[data-checked="true"],
    [data-testid="stSidebar"] .stRadio [aria-checked="true"] + label {
        background: #3B63FB !important;
        color: white !important;
        font-weight: 600 !important;
    }

    /* ── Hide Streamlit Branding ────────────────────────────────── */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="collapsedControl"] {display: none;}

    /* ── Metric Cards (KPIs) ────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: #F6F8FC;
        border-radius: 14px;
        padding: 1.2rem 1.5rem;
        border: 1px solid #E8EDF5;
    }

    /* ── Buttons ────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 0.55rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59,99,251,0.2);
    }

    /* ── Selectbox / DateInput ──────────────────────────────────── */
    .stSelectbox, .stDateInput, .stMultiSelect {
        font-size: 0.88rem !important;
    }
    .stSelectbox > div > div,
    .stDateInput > div > div,
    .stMultiSelect > div > div {
        border-radius: 10px !important;
        border-color: #E2E8F0 !important;
    }

    /* ── Radio ──────────────────────────────────────────────────── */
    .main .stRadio > div {
        gap: 0.3rem !important;
    }
    .main .stRadio label {
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        padding: 0.4rem 1rem !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }

    /* ── Plotly Charts Container ────────────────────────────────── */
    [data-testid="stPlotlyChart"] {
        background: white;
        border-radius: 16px;
        padding: 0.8rem;
        border: 1px solid #E8EDF5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── DataFrames ─────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* ── Download Buttons ───────────────────────────────────────── */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #3B63FB, #2246D4) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
    }
    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #2246D4, #1A37B0) !important;
        transform: translateY(-1px);
    }

    /* ── Sidebar navigation title ───────────────────────────────── */
    .sidebar-title {
        font-size: 1.3rem;
        font-weight: 800;
        color: white;
        padding: 1.5rem 1rem 1rem;
        line-height: 1.3;
    }
    .sidebar-divider {
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 0.8rem 0 0.5rem;
    }

    /* ── Header area ────────────────────────────────────────────── */
    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
    }
    .dashboard-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #1B2139;
    }
</style>
""", unsafe_allow_html=True)


# ─── Autenticação ────────────────────────────────────────────────────
if not check_auth():
    login_page()
    st.stop()


# ─── Sidebar: Navegação ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(f'<div class="sidebar-title">{APP_TITLE}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    page = st.radio(
        "Navegação",
        ["Dashboard", "Ocupação", "Espaços", "Relatórios", "ETL / Logs"],
        label_visibility="collapsed",
        key="nav_page",
    )

    st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)

    # User info + logout
    st.markdown("---")
    user = st.session_state.get("username", "—")
    st.markdown(f"👤 **{user}**")
    if st.button("🚪 Terminar Sessão", use_container_width=True):
        logout()


# ─── Header + Filtros Globais ────────────────────────────────────────
# Filtros na barra superior conforme Frame.png
header_cols = st.columns([3, 2, 2, 2])

with header_cols[0]:
    st.markdown(f'<div class="dashboard-title">{page}</div>', unsafe_allow_html=True)

with header_cols[1]:
    anos = get_anos_letivos()
    ano_selecionado = st.selectbox(
        "Ano Letivo",
        ["Todos"] + anos,
        key="filter_ano",
        label_visibility="collapsed",
    )

with header_cols[2]:
    edificios = get_edificios()
    edf_selecionado = st.selectbox(
        "Edifício",
        ["Todos os edifícios"] + edificios,
        key="filter_edificio",
        label_visibility="collapsed",
    )

with header_cols[3]:
    espacos_list = get_espacos(
        edf_selecionado if edf_selecionado != "Todos os edifícios" else None
    )
    espaco_selecionado = st.selectbox(
        "Espaço",
        ["Todos os espaços"] + espacos_list,
        key="filter_espaco",
        label_visibility="collapsed",
    )

# Filtros secundários (expandíveis)
with st.expander("🔍 Filtros Avançados", expanded=False):
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        semestre_opt = st.selectbox("Semestre", ["Todos", 1, 2], key="filter_semestre")
    with fc2:
        departamentos = get_departamentos()
        dept_selecionado = st.selectbox(
            "Departamento",
            ["Todos"] + departamentos,
            key="filter_dept",
        )
    with fc3:
        ciclos = get_ciclos_estudo()
        ciclo_selecionado = st.selectbox(
            "Ciclo Estudo",
            ["Todos"] + ciclos,
            key="filter_ciclo",
        )
    with fc4:
        epocas = get_epocas()
        epoca_selecionada = st.selectbox(
            "Época",
            ["Todos"] + epocas,
            key="filter_epoca",
        )

    fc5, fc6, fc7 = st.columns(3)
    with fc5:
        hide_online = st.checkbox("Excluir Sessões Online", key="toggle_online", value=False)
    with fc6:
        dedup_concurrent = st.checkbox("Deduplicar Concurrentes", key="toggle_dedup", value=False)
    with fc7:
        hide_ghost = st.checkbox("Ocultar Ghost Sessions", key="toggle_ghost", value=False)

    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
    fc8, fc9 = st.columns(2)
    with fc8:
        date_range = st.date_input(
            "Período",
            value=[],
            key="filter_dates",
        )

# ─── Montar Dicionário de Filtros ────────────────────────────────────
filters = {}
if ano_selecionado != "Todos":
    filters["ano_letivo"] = ano_selecionado
if semestre_opt != "Todos":
    filters["semestre"] = int(semestre_opt)
if edf_selecionado != "Todos os edifícios":
    filters["edificio"] = edf_selecionado
if espaco_selecionado != "Todos os espaços":
    filters["espaco"] = espaco_selecionado
if dept_selecionado != "Todos":
    filters["departamento"] = dept_selecionado
if ciclo_selecionado != "Todos":
    filters["ciclo_estudo"] = ciclo_selecionado
if epoca_selecionada != "Todos":
    filters["epoca"] = epoca_selecionada
filters["hide_online"] = hide_online
filters["deduplicate_concurrent"] = dedup_concurrent
filters["hide_ghost_sessions"] = hide_ghost
if date_range and len(date_range) == 2:
    filters["data_inicio"] = str(date_range[0])
    filters["data_fim"] = str(date_range[1])

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ─── Routing ─────────────────────────────────────────────────────────
if page == "Dashboard":
    page_dashboard(filters)
elif page == "Ocupação":
    page_ocupacao(filters)
elif page == "Espaços":
    page_espacos(filters)
elif page == "Relatórios":
    page_relatorios(filters)
elif page == "ETL / Logs":
    page_etl_logs(filters)
