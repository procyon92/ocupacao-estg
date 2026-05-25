"""
main.py — V3 entry point.
Top horizontal navigation + sidebar contextual filters + profile routing.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime
from config import APP_TITLE, PAGE_TITLE, FAVICON, COLORS
from auth import check_auth, login_page, logout
from data import (
    get_anos_letivos, get_departamentos, get_edificios,
    get_categorias, get_espacos, get_ciclos_estudo, get_cursos, get_ucs, get_epocas,
)
from pages import render_profile_a_general, render_profile_b_labs, render_profile_c_spaces, render_profile_d_quality

# ─── Page config ──────────────────────────────────────────────────
st.set_page_config(page_title=PAGE_TITLE, page_icon=FAVICON, layout="wide", initial_sidebar_state="expanded")

# ─── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [data-testid="stApp"] { font-family: 'Inter', sans-serif !important; }
    .main .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B2139 0%, #141929 100%) !important;
        min-width: 230px !important; max-width: 230px !important; width: 230px !important;
        flex: 0 0 230px !important; display: flex; flex-direction: column; height: 100vh;
    }
    [data-testid="stSidebar"] > div:first-child {
        display: flex; flex-direction: column; flex: 1; overflow-y: auto; min-height: 0;
    }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stCheckbox label { color: rgba(255,255,255,0.85) !important; font-size: 0.82rem !important; font-weight: 500 !important; }
    [data-testid="collapsedControl"] { display: none; }
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    [data-testid="stMetric"] { background: #F6F8FC; border-radius: 14px; padding: 1.2rem 1.5rem; border: 1px solid #E8EDF5; }
    .stButton > button { border-radius: 10px !important; font-weight: 600 !important; font-size: 0.88rem !important; padding: 0.55rem 1.5rem !important; transition: all 0.2s ease !important; }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(59,99,251,0.2); }
    [data-testid="stSidebar"] .stButton button[kind="secondary"] { background: rgba(255,255,255,0.12) !important; color: white !important; border: 1px solid rgba(255,255,255,0.2) !important; }
    [data-testid="stSidebar"] .stButton button[kind="secondary"]:hover { background: rgba(255,255,255,0.2) !important; border-color: rgba(255,255,255,0.35) !important; }
    [data-testid="stSidebar"] .stSelectbox > div > div { border-radius: 8px !important; border-color: rgba(255,255,255,0.15) !important; background: rgba(255,255,255,0.08) !important; }
    [data-testid="stSidebar"] .stCheckbox { margin-top: -0.4rem; }
    .stSelectbox, .stDateInput, .stMultiSelect { font-size: 0.88rem !important; }
    .main .stRadio > div { gap: 0.3rem !important; }
    .main .stRadio label { border: 1px solid #E2E8F0 !important; border-radius: 8px !important; padding: 0.4rem 1rem !important; font-size: 0.82rem !important; font-weight: 500 !important; transition: all 0.2s ease !important; }
    [data-testid="stPlotlyChart"] { background: white; border-radius: 16px; padding: 0.8rem; border: 1px solid #E8EDF5; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
    .stDownloadButton > button { background: linear-gradient(135deg, #3B63FB, #2246D4) !important; color: white !important; border: none !important; border-radius: 10px !important; }
    .stDownloadButton > button:hover { background: linear-gradient(135deg, #2246D4, #1A37B0) !important; transform: translateY(-1px); }
    .sidebar-title { font-size: 1.1rem; font-weight: 800; color: white; padding: 1rem 0.5rem 0.5rem; line-height: 1.3; }
    .sidebar-divider { border-top: 1px solid rgba(255,255,255,0.1); margin: 0.5rem 0; }
    .dashboard-title { font-size: 1.5rem; font-weight: 800; color: #1B2139; }
    /* Top navigation segmented control */
    [data-testid="stHorizontalNav"] { margin-bottom: 0.5rem; }
    [data-testid="stHorizontalNav"] button { font-weight: 500 !important; }
    /* Sidebar filter section header */
    .sidebar-filter-header { font-size: 0.9rem; font-weight: 600; color: white; padding: 0.5rem 0; }
    .sidebar-filter-divider { border-top: 1px solid rgba(255,255,255,0.08); margin: 0.6rem 0; }
</style>
""", unsafe_allow_html=True)

# ─── Auth ─────────────────────────────────────────────────────────
if not check_auth():
    login_page()
    st.stop()

# ─── Top Horizontal Navigation ───────────────────────────────────
nav_cols = st.columns([1, 4, 1])
with nav_cols[0]:
    st.markdown(f"**{APP_TITLE}**")
with nav_cols[1]:
    profile_options = ["Visão Geral ESTG", "Laboratórios", "Espaços", "Qualidade"]
    profile = st.segmented_control(
        "Navegação",
        options=profile_options,
        default=profile_options[0],
        label_visibility="collapsed",
        key="v3_nav",
        selection_mode="single",
    )
with nav_cols[2]:
    st.markdown(f"👤 {st.session_state.get('username', '—')}")

st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

# ─── Smart defaults ──────────────────────────────────────────────
_ANOS = get_anos_letivos()
_DEFAULT_ANO = _ANOS[0] if _ANOS else None
_MONTH = datetime.now().month
_DEFAULT_SEM = 1 if _MONTH in [9,10,11,12,1,2] else 2 if _MONTH in [3,4,5,6,7] else None

def _ano_index(anos):
    val = st.session_state.get("v2_filter_ano_letivo", _DEFAULT_ANO)
    if val in anos:
        return anos.index(val) + 1
    return 0

def _sem_index():
    val = st.session_state.get("v2_filter_semestre", _DEFAULT_SEM)
    if val in [1, 2]:
        return [1, 2].index(val) + 1
    return 0

# ─── Reset filters callback ──────────────────────────────────────
def _reset_filters():
    anos = get_anos_letivos()
    st.session_state["v2_filter_ano_letivo"] = anos[0] if anos else "Todos"
    month = datetime.now().month
    st.session_state["v2_filter_semestre"] = 1 if month in [9,10,11,12,1,2] else 2 if month in [3,4,5,6,7] else "Todos"
    for key in ["v2_filter_departamento", "v2_filter_edificio", "v2_filter_categoria_espaco",
                "v2_filter_espaco", "v2_filter_ciclo_estudo", "v2_filter_curso",
                "v2_filter_uc", "v2_filter_epoca"]:
        st.session_state[key] = "Todos"
    for key in ["v2_toggle_online", "v2_toggle_ghost", "v2_toggle_concurrent"]:
        st.session_state[key] = False

# ─── Sidebar: Contextual Filters + User ──────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">🔍 Filtros</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    is_lab_profile = (profile == "Laboratórios")

    # ── Profile-specific filter renderers ─────────────────────────
    if profile == "Visão Geral ESTG":
        def _render():
            ano_val = st.selectbox("Ano Letivo", ["Todos"] + _ANOS, index=_ano_index(_ANOS), key="v2_filter_ano_letivo")
            sem_val = st.selectbox("Semestre", ["Todos", 1, 2], index=_sem_index(), key="v2_filter_semestre")
            dept_val = st.selectbox("Departamento", ["Todos"] + get_departamentos(), key="v2_filter_departamento")
            epoca_val = st.selectbox("Época", ["Todos"] + get_epocas(), key="v2_filter_epoca")
            cat_val = st.selectbox("Categoria", ["Todos"] + get_categorias(), key="v2_filter_categoria_espaco")
            edf_val = st.selectbox("Edifício", ["Todos"] + get_edificios(departamento=dept_val if dept_val != "Todos" else None), key="v2_filter_edificio")
            esp_val = st.selectbox("Espaço", ["Todos"] + get_espacos(edificio=edf_val if edf_val != "Todos" else None, categoria=cat_val if cat_val != "Todos" else None), key="v2_filter_espaco")
            ciclo_val = st.selectbox("Ciclo Estudo", ["Todos"] + get_ciclos_estudo(), key="v2_filter_ciclo_estudo")
            curso_val = st.selectbox("Curso", ["Todos"] + get_cursos(ciclo=ciclo_val if ciclo_val != "Todos" else None), key="v2_filter_curso")
            uc_val = st.selectbox("UC", ["Todos"] + get_ucs(curso=curso_val if curso_val != "Todos" else None), key="v2_filter_uc")
            st.markdown('<div class="sidebar-filter-divider"></div>', unsafe_allow_html=True)
            hide_online = st.checkbox("Excluir Online", value=False, key="v2_toggle_online")
            hide_ghost = st.checkbox("Ocultar Ghost", value=False, key="v2_toggle_ghost")
            hide_concurrent = st.checkbox("Deduplicar Concurrentes", value=False, key="v2_toggle_concurrent")
            return {k: v for k, v in locals().items() if k.startswith(("ano_", "sem_", "dept_", "epoca_", "cat_", "edf_", "esp_", "ciclo_", "curso_", "uc_", "hide_"))}
        _locals = _render()

    elif profile == "Laboratórios":
        def _render():
            ano_val = st.selectbox("Ano Letivo", ["Todos"] + _ANOS, index=_ano_index(_ANOS), key="v2_filter_ano_letivo")
            sem_val = st.selectbox("Semestre", ["Todos", 1, 2], index=_sem_index(), key="v2_filter_semestre")
            dept_val = st.selectbox("Departamento", ["Todos"] + get_departamentos(), key="v2_filter_departamento")
            epoca_val = st.selectbox("Época", ["Todos"] + get_epocas(), key="v2_filter_epoca")
            cat_val = st.selectbox("Categoria", ["Laboratório"], disabled=True, key="v2_filter_categoria_espaco")
            edf_val = st.selectbox("Edifício", ["Todos"] + get_edificios(departamento=dept_val if dept_val != "Todos" else None, only_labs=True), key="v2_filter_edificio")
            esp_val = st.selectbox("Espaço", ["Todos"] + get_espacos(edificio=edf_val if edf_val != "Todos" else None, only_labs=True), key="v2_filter_espaco")
            ciclo_val = st.selectbox("Ciclo Estudo", ["Todos"] + get_ciclos_estudo(only_labs=True), key="v2_filter_ciclo_estudo")
            curso_val = st.selectbox("Curso", ["Todos"] + get_cursos(ciclo=ciclo_val if ciclo_val != "Todos" else None, only_labs=True), key="v2_filter_curso")
            uc_val = st.selectbox("UC", ["Todos"] + get_ucs(curso=curso_val if curso_val != "Todos" else None, only_labs=True), key="v2_filter_uc")
            st.markdown('<div class="sidebar-filter-divider"></div>', unsafe_allow_html=True)
            hide_online = st.checkbox("Excluir Online", value=False, key="v2_toggle_online")
            hide_ghost = st.checkbox("Ocultar Ghost", value=False, key="v2_toggle_ghost")
            hide_concurrent = st.checkbox("Deduplicar Concurrentes", value=False, key="v2_toggle_concurrent")
            return {k: v for k, v in locals().items() if k.startswith(("ano_", "sem_", "dept_", "epoca_", "cat_", "edf_", "esp_", "ciclo_", "curso_", "uc_", "hide_"))}
        _locals = _render()

    elif profile == "Espaços":
        def _render():
            ano_val = st.selectbox("Ano Letivo", ["Todos"] + _ANOS, index=_ano_index(_ANOS), key="v2_filter_ano_letivo")
            sem_val = st.selectbox("Semestre", ["Todos", 1, 2], index=_sem_index(), key="v2_filter_semestre")
            st.markdown('<div class="sidebar-filter-divider"></div>', unsafe_allow_html=True)
            hide_online = st.checkbox("Excluir Online", value=False, key="v2_toggle_online")
            hide_ghost = st.checkbox("Ocultar Ghost", value=False, key="v2_toggle_ghost")
            return {k: v for k, v in locals().items() if k.startswith(("ano_", "sem_", "hide_"))}
        _locals = _render()

    elif profile == "Qualidade":
        def _render():
            ano_val = st.selectbox("Ano Letivo", ["Todos"] + _ANOS, index=_ano_index(_ANOS), key="v2_filter_ano_letivo")
            sem_val = st.selectbox("Semestre", ["Todos", 1, 2], index=_sem_index(), key="v2_filter_semestre")
            return {k: v for k, v in locals().items() if k.startswith(("ano_", "sem_"))}
        _locals = _render()

    # ── Reset + User footer ──────────────────────────────────────
    st.markdown('<div class="sidebar-filter-divider"></div>', unsafe_allow_html=True)
    st.button("Limpar Filtros", use_container_width=True, on_click=_reset_filters)
    st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(f"**{st.session_state.get('username', '—')}**")
    if st.button("Terminar Sessao", use_container_width=True, type="primary"):
        logout()
    st.markdown("---")

# ─── Build filters dict ──────────────────────────────────────────
filters = {}
_val = _locals.get
if _val("ano_val", "Todos") != "Todos": filters["ano_letivo"] = _val("ano_val")
if _val("sem_val", "Todos") != "Todos": filters["semestre"] = int(_val("sem_val"))
if _val("dept_val", "Todos") != "Todos": filters["departamento"] = _val("dept_val")
if _val("cat_val", "Todos") != "Todos": filters["categoria_espaco"] = _val("cat_val")
if _val("edf_val", "Todos") != "Todos": filters["edificio"] = _val("edf_val")
if _val("esp_val", "Todos") != "Todos": filters["espaco"] = _val("esp_val")
if _val("ciclo_val", "Todos") != "Todos": filters["ciclo_estudo"] = _val("ciclo_val")
if _val("curso_val", "Todos") != "Todos": filters["curso"] = _val("curso_val")
if _val("uc_val", "Todos") != "Todos": filters["uc"] = _val("uc_val")
if _val("epoca_val", "Todos") != "Todos": filters["epoca"] = _val("epoca_val")
filters["hide_online"] = _val("hide_online", False)
filters["hide_concurrent"] = _val("hide_concurrent", False)
filters["hide_ghost"] = _val("hide_ghost", False)
filters["only_labs"] = is_lab_profile

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ─── Route to profile ────────────────────────────────────────────
if profile == "Visão Geral ESTG":
    render_profile_a_general(filters)
elif profile == "Laboratórios":
    render_profile_b_labs(filters)
elif profile == "Espaços":
    render_profile_c_spaces(filters)
elif profile == "Qualidade":
    render_profile_d_quality(filters)