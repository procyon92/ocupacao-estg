"""
main.py — V4 entry point.
Top horizontal navigation + sidebar grouped contextual filters + profile routing.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime
from config import APP_TITLE, PAGE_TITLE, FAVICON
from auth import check_auth, login_page, logout
from data import (
    get_anos_letivos, get_departamentos, get_edificios,
    get_categorias, get_espacos, get_ciclos_estudo, get_cursos, get_ucs,
    get_epocas, get_dias_semana, get_semanas,
)
from pages import (
    render_profile_a_general, render_profile_b_labs,
    render_profile_c_spaces, render_profile_d_quality,
    render_profile_e_alerts, render_profile_f_comparison,
    render_profile_g_empty_rooms,
)

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stApp"] {
        font-family: 'Inter', sans-serif !important;
    }

    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* ───────────────── Sidebar fixa ───────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B2139 0%, #141929 100%) !important;
        min-width: 230px !important;
        max-width: 230px !important;
        width: 230px !important;
        flex: 0 0 230px !important;
        display: flex;
        flex-direction: column;
        height: 100vh;
    }

    [data-testid="stSidebar"] > div:first-child {
        display: flex;
        flex-direction: column;
        flex: 1;
        overflow-y: auto;
        min-height: 0;
    }

    /* Remove TODOS os botões de collapse da sidebar */
    button[kind="header"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* Remove header/topbar vazio do Streamlit */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* Remove espaço superior que o header deixava */
    .block-container {
        padding-top: 5rem !important;
    }

    [data-testid="stSidebar"] * {
        color: white !important;
    }

    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stCheckbox label {
        color: rgba(255,255,255,0.85) !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    [data-testid="stMetric"] {
        background: #F6F8FC;
        border-radius: 14px;
        padding: 1.2rem 1.5rem;
        border: 1px solid #E8EDF5;
    }

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

    [data-testid="stSidebar"] .stButton button[kind="secondary"] {
        background: rgba(255,255,255,0.12) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
    }

    [data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {
        background: rgba(255,255,255,0.2) !important;
        border-color: rgba(255,255,255,0.35) !important;
    }

    [data-testid="stSidebar"] .stSelectbox > div > div {
        border-radius: 8px !important;
        border-color: rgba(255,255,255,0.15) !important;
        background: rgba(255,255,255,0.08) !important;
    }

    [data-testid="stSidebar"] .stCheckbox {
        margin-top: -0.4rem;
    }

    .stSelectbox,
    .stDateInput,
    .stMultiSelect {
        font-size: 0.88rem !important;
    }

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

    [data-testid="stPlotlyChart"] {
        background: white;
        border-radius: 16px;
        padding: 0.8rem;
        border: 1px solid #E8EDF5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

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

    .sidebar-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: white;
        padding: 1rem 0.5rem 0.5rem;
        line-height: 1.3;
    }

    .sidebar-divider {
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 0.5rem 0;
    }

    .dashboard-title {
        font-size: 1.5rem;
        font-weight: 800;
        color: #1B2139;
    }

    [data-testid="stHorizontalNav"] {
        margin-bottom: 0.5rem;
    }

    [data-testid="stHorizontalNav"] button {
        font-weight: 500 !important;
    }

    .sidebar-group-header {
        font-size: 0.75rem;
        font-weight: 600;
        color: rgba(255,255,255,0.55);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 0.6rem 0 0.2rem;
        margin-top: 0.1rem;
    }

    .sidebar-group-divider {
        border-top: 1px solid rgba(255,255,255,0.06);
        margin: 0.4rem 0;
    }

    .active-filters {
        background: rgba(255,255,255,0.06);
        border-radius: 8px;
        padding: 0.5rem 0.6rem;
        font-size: 0.72rem;
        color: rgba(255,255,255,0.7);
        line-height: 1.4;
        margin: 0.3rem 0;
    }
</style>
""", unsafe_allow_html=True)

if not check_auth():
    login_page()
    st.stop()

# ─── Top Horizontal Navigation ───────────────────────────────────
nav_cols = st.columns([1, 5, 1])
with nav_cols[0]:
    st.markdown(f"**{APP_TITLE}**")
with nav_cols[1]:
    profile_options = ["Visão Geral", "Laboratórios", "Detalhe Sala", "Alertas", "Comparação", "Qualidade", "Salas Vazias"]
    profile = st.segmented_control(
        "Navegação",
        options=profile_options,
        default=profile_options[0],
        label_visibility="collapsed",
        key="v4_nav",
        selection_mode="single",
    )
with nav_cols[2]:
    st.markdown(f"👤 {st.session_state.get('username', '—')}")

st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

# ─── Smart defaults & shared helpers ─────────────────────────────
_ANOS = get_anos_letivos()
_DEFAULT_ANO = _ANOS[0] if _ANOS else None
_MONTH = datetime.now().month
_DEFAULT_SEM = 1 if _MONTH in [9,10,11,12,1,2] else 2 if _MONTH in [3,4,5,6,7] else None

def _ano_index(anos):
    val = st.session_state.get("v4_filter_ano_letivo", _DEFAULT_ANO)
    if val in anos:
        return anos.index(val) + 1
    return 0

def _sem_index():
    val = st.session_state.get("v4_filter_semestre", _DEFAULT_SEM)
    if val in [1, 2]:
        return [1, 2].index(val) + 1
    return 0

# ─── Widget manifest ─────────────────────────────────────────────
_FILTER_MANIFEST = {
    "ano_letivo":     {"key": "ano_val",     "group": "📅 Calendário",   "default": "Todos"},
    "semestre":       {"key": "sem_val",     "group": "📅 Calendário",   "default": "Todos"},
    "semana":         {"key": "semana_val",  "group": "📅 Calendário",   "default": "Todas"},
    "dias":           {"key": "dias_val",    "group": "📅 Calendário",   "default": []},
    "escola":         {"key": "dept_val",    "group": "📍 Local",        "default": "Todos"},
    "edificio":       {"key": "edf_val",     "group": "📍 Local",        "default": "Todos"},
    "categoria_espaco":{"key": "cat_val",    "group": "📍 Local",        "default": "Todos"},
    "espaco":         {"key": "esp_val",     "group": "📍 Local",        "default": "Todos"},
    "ciclo_estudo":   {"key": "ciclo_val",   "group": "🎯 Atividades",   "default": "Todos"},
    "epoca":          {"key": "epoca_val",   "group": "🎯 Atividades",   "default": "Todos"},
    "curso":          {"key": "curso_val",   "group": "🎯 Atividades",   "default": "Todos"},
    "uc":             {"key": "uc_val",      "group": "🎯 Atividades",   "default": "Todos"},
    "hide_online":    {"key": "hide_online", "group": "toggles",         "default": False},
    "hide_ghost":     {"key": "hide_ghost",  "group": "toggles",         "default": False},
    "hide_concurrent":{"key": "hide_concurrent","group": "toggles",      "default": False},
}

_toggle_session_keys = ["v4_toggle_online", "v4_toggle_ghost", "v4_toggle_concurrent"]

# ─── Profile widget presence ─────────────────────────────────────
_PROFILE_WIDGETS = {
    "Visão Geral": [
        "ano_letivo", "semestre", "semana", "dias",
        "escola", "edificio", "categoria_espaco", "espaco",
        "ciclo_estudo", "epoca", "curso", "uc",
        "hide_online", "hide_ghost", "hide_concurrent",
    ],
    "Laboratórios": [
        "ano_letivo", "semestre", "semana", "dias",
        "escola", "categoria_espaco", "edificio", "espaco",
        "ciclo_estudo", "epoca", "curso", "uc",
        "hide_online", "hide_ghost", "hide_concurrent",
    ],
    "Alertas": [
        "ano_letivo", "semestre", "semana", "dias",
        "escola", "categoria_espaco", "edificio",
        "epoca",
        "hide_online", "hide_ghost", "hide_concurrent",
    ],
    "Comparação": [
        "ano_letivo", "semestre", "semana", "dias",
        "escola", "categoria_espaco", "edificio",
        "epoca",
        "hide_online", "hide_ghost", "hide_concurrent",
    ],
    "Detalhe Sala": [
        "ano_letivo", "semestre",
        "hide_online", "hide_ghost",
    ],
    "Qualidade": [
        "ano_letivo", "semestre",
    ],
    "Salas Vazias": [
        "ano_letivo", "semestre", "edificio", "escola",
    ],
}

# ─── Active filters string builder ───────────────────────────────
def _build_active_string(locals_dict):
    parts = []
    d = locals_dict
    if d.get("ano_val", "Todos") != "Todos": parts.append(f"📅 {d['ano_val']}")
    if d.get("sem_val", "Todos") != "Todos": parts.append(f"Sem {d['sem_val']}")
    if d.get("semana_val", "Todas") != "Todas": parts.append(f"S{d['semana_val']}")
    if d.get("dias_val", []): parts.append(f"Dias: {', '.join(d['dias_val'][:2])}{'…' if len(d['dias_val'])>2 else ''}")
    if d.get("edf_val", "Todos") != "Todos": parts.append(f"🏗 {d['edf_val']}")
    if d.get("cat_val", "Todos") != "Todos": parts.append(f"📐 {d['cat_val']}")
    if d.get("dept_val", "Todos") != "Todos": parts.append(f"🏛 {d['dept_val']}")
    if d.get("ciclo_val", "Todos") != "Todos": parts.append(f"🎓 {d['ciclo_val']}")
    if d.get("epoca_val", "Todos") != "Todos": parts.append(f"📆 {d['epoca_val']}")
    return " | ".join(parts) if parts else "Sem filtros ativos"

# ─── Reset filters callback ──────────────────────────────────────
def _reset_filters():
    anos = get_anos_letivos()
    st.session_state["v4_filter_ano_letivo"] = anos[0] if anos else "Todos"
    month = datetime.now().month
    st.session_state["v4_filter_semestre"] = 1 if month in [9,10,11,12,1,2] else 2 if month in [3,4,5,6,7] else "Todos"
    for key in list(st.session_state):
        if key.startswith("v4_filter_") and key not in ("v4_filter_ano_letivo", "v4_filter_semestre"):
            wname = key.replace("v4_filter_", "")
            info = _FILTER_MANIFEST.get(wname)
            if info:
                st.session_state[key] = info["default"]
    for key in _toggle_session_keys:
        st.session_state[key] = False

# ─── Unified filter renderer ─────────────────────────────────────
def _render_filters(profile):
    fw = _PROFILE_WIDGETS[profile]
    is_lab = profile == "Laboratórios"
    _groups_rendered = set()

    for wname in fw:
        info = _FILTER_MANIFEST[wname]
        group = info["group"]

        if group != "toggles" and group not in _groups_rendered:
            _groups_rendered.add(group)
            st.markdown(f'<div class="sidebar-group-header">{group}</div>', unsafe_allow_html=True)

        sk = f"v4_filter_{wname}"
        vkey = info["key"]

        if wname == "ano_letivo":
            _locals[vkey] = st.selectbox("Ano Letivo", ["Todos"] + _ANOS, index=_ano_index(_ANOS), key=sk)
        elif wname == "semestre":
            _locals[vkey] = st.selectbox("Semestre", ["Todos", 1, 2], index=_sem_index(), key=sk)
        elif wname == "semana":
            ano = _locals.get("ano_val", "Todos")
            sem = _locals.get("sem_val", "Todos")
            opts = ["Todas"] + [str(s) for s in get_semanas(ano_letivo=ano if ano != "Todos" else None, semestre=sem if sem != "Todos" else None)]
            _locals[vkey] = st.selectbox("Semana", opts, key=sk)
        elif wname == "dias":
            _locals[vkey] = st.multiselect("Dia da Semana", get_dias_semana(), default=[], key=sk)
        elif wname == "escola":
            _locals[vkey] = st.selectbox("Escola", ["Todos"] + get_departamentos(), key=sk)
        elif wname == "edificio":
            dept = _locals.get("dept_val", "Todos")
            dept = dept if dept != "Todos" else None
            opts = ["Todos"] + get_edificios(departamento=dept, only_labs=is_lab)
            _locals[vkey] = st.selectbox("Edifício", opts, key=sk)
        elif wname == "categoria_espaco":
            if is_lab:
                _locals[vkey] = st.selectbox("Categoria", ["Laboratório"], disabled=True, key=sk)
            else:
                _locals[vkey] = st.selectbox("Categoria", ["Todos"] + get_categorias(), key=sk)
        elif wname == "espaco":
            edf = _locals.get("edf_val", "Todos")
            cat = _locals.get("cat_val", "Todos")
            opts = ["Todos"] + get_espacos(edificio=edf if edf != "Todos" else None, categoria=cat if cat != "Todos" else None, only_labs=is_lab)
            _locals[vkey] = st.selectbox("Sala", opts, key=sk)
        elif wname == "ciclo_estudo":
            _locals[vkey] = st.selectbox("Ciclo Estudo", ["Todos"] + get_ciclos_estudo(only_labs=is_lab), key=sk)
        elif wname == "epoca":
            _locals[vkey] = st.selectbox("Período/Época", ["Todos"] + get_epocas(), key=sk)
        elif wname == "curso":
            ciclo = _locals.get("ciclo_val", "Todos")
            ciclo = ciclo if ciclo != "Todos" else None
            _locals[vkey] = st.selectbox("Curso", ["Todos"] + get_cursos(ciclo=ciclo, only_labs=is_lab), key=sk)
        elif wname == "uc":
            curso = _locals.get("curso_val", "Todos")
            curso = curso if curso != "Todos" else None
            _locals[vkey] = st.selectbox("UC", ["Todos"] + get_ucs(curso=curso, only_labs=is_lab), key=sk)
        elif wname == "hide_online":
            st.markdown('<div class="sidebar-group-divider"></div>', unsafe_allow_html=True)
            _locals[vkey] = st.checkbox("Excluir Online", value=False, key="v4_toggle_online")
        elif wname == "hide_ghost":
            _locals[vkey] = st.checkbox("Ocultar Ghost", value=False, key="v4_toggle_ghost")
        elif wname == "hide_concurrent":
            _locals[vkey] = st.checkbox("Deduplicar Concurrentes", value=False, key="v4_toggle_concurrent")

# ─── Build filters dict from widget locals ───────────────────────
def _extract_filters(locals_dict):
    f = {}
    if locals_dict.get("ano_val", "Todos") != "Todos": f["ano_letivo"] = locals_dict["ano_val"]
    if locals_dict.get("sem_val", "Todos") != "Todos": f["semestre"] = int(locals_dict["sem_val"])
    if locals_dict.get("dept_val", "Todos") != "Todos": f["departamento"] = locals_dict["dept_val"]
    if locals_dict.get("cat_val", "Todos") != "Todos": f["categoria_espaco"] = locals_dict["cat_val"]
    if locals_dict.get("edf_val", "Todos") != "Todos": f["edificio"] = locals_dict["edf_val"]
    if locals_dict.get("esp_val", "Todos") != "Todos": f["espaco"] = locals_dict["esp_val"]
    if locals_dict.get("ciclo_val", "Todos") != "Todos": f["ciclo_estudo"] = locals_dict["ciclo_val"]
    if locals_dict.get("curso_val", "Todos") != "Todos": f["curso"] = locals_dict["curso_val"]
    if locals_dict.get("uc_val", "Todos") != "Todos": f["uc"] = locals_dict["uc_val"]
    if locals_dict.get("epoca_val", "Todos") != "Todos": f["epoca"] = locals_dict["epoca_val"]
    f["hide_online"] = locals_dict.get("hide_online", False)
    f["hide_concurrent"] = locals_dict.get("hide_concurrent", False)
    f["hide_ghost"] = locals_dict.get("hide_ghost", False)
    return f

# ─── Sidebar: Contextual Filters + User ──────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">🔍 Filtros</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    is_lab_profile = (profile == "Laboratórios")
    _locals = {}
    _render_filters(profile)

    # ── Active filters string ────────────────────────────────────
    st.markdown(f'<div class="active-filters">{_build_active_string(_locals)}</div>', unsafe_allow_html=True)

    # ── Reset + User footer ──────────────────────────────────────
    st.button("Limpar Filtros", use_container_width=True, on_click=_reset_filters)
    st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(f"**{st.session_state.get('username', '—')}**")
    if st.button("Terminar Sessao", use_container_width=True, type="primary"):
        logout()
    st.markdown("---")

# ─── Build filters dict ──────────────────────────────────────────
filters = _extract_filters(_locals)
filters["only_labs"] = is_lab_profile

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ─── Route to profile ────────────────────────────────────────────
if profile == "Visão Geral":
    render_profile_a_general(filters)
elif profile == "Laboratórios":
    render_profile_b_labs(filters)
elif profile == "Detalhe Sala":
    render_profile_c_spaces(filters)
elif profile == "Alertas":
    render_profile_e_alerts(filters)
elif profile == "Comparação":
    render_profile_f_comparison(filters)
elif profile == "Qualidade":
    render_profile_d_quality(filters)
elif profile == "Salas Vazias":
    render_profile_g_empty_rooms(filters)