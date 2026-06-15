"""
main.py — Entry point.

What changed vs the original:
  - _locals is NO LONGER a module-level mutable dict mutated by a function.
    _render_filters() now returns a dict. Clean, refactor-safe.
  - All session_state keys use SessionKeys constants (no scattered string literals).
  - _reset_filters iterates SessionKeys.RESETTABLE — complete by construction.
  - Profile routing uses a dispatch dict instead of an if/elif chain.
  - CSS is loaded from assets/style.css (zero logic in this file).
  - Filters TypedDict provides a formal contract between main and profiles.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
import streamlit as st

from config import APP_TITLE, PAGE_TITLE, FAVICON, LAB_CATEGORY, Sentinel, CACHE_TTL_COLD
from auth import check_auth, login_page, logout
from models import Filters, SessionKeys
from queries import (
    get_anos_letivos, get_escolas, get_departamentos, get_edificios,
    get_categorias, get_espacos, get_ciclos_estudo, get_cursos, get_ucs,
    get_epocas, get_dias_semana, get_semanas,
)
from profiles.general    import GeneralProfile
from profiles.labs       import LabsProfile
from profiles.space_detail import SpaceDetailProfile
from profiles.quality    import QualityProfile
from profiles.alerts     import AlertsProfile
from profiles.comparison import ComparisonProfile
from profiles.empty_rooms import EmptyRoomsProfile

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────
_CSS_PATH = os.path.join(os.path.dirname(__file__), "assets", "style.css")
with open(_CSS_PATH) as _f:
    st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)

# ── Auth ──────────────────────────────────────────────────────────────
if not check_auth():
    login_page()
    st.stop()

# ── Navigation ────────────────────────────────────────────────────────
PROFILE_LABELS = [
    "Visão Geral", "Laboratórios", "Detalhe Sala",
    "Salas Vazias", "Alertas", "Comparação", "Qualidade",
]

nav_cols = st.columns([1, 5, 1])
with nav_cols[0]:
    st.markdown(f"**{APP_TITLE}**")
with nav_cols[1]:
    profile = st.segmented_control(
        "Navegação", options=PROFILE_LABELS, default=PROFILE_LABELS[0],
        label_visibility="collapsed", key=SessionKeys.NAV, selection_mode="single",
    )
with nav_cols[2]:
    st.markdown(f"👤 {st.session_state.get('username', '—')}")

st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

# ── Shared data ───────────────────────────────────────────────────────
_ANOS = get_anos_letivos()
_DEFAULT_ANO = _ANOS[0] if _ANOS else None
_MONTH = datetime.now().month
_DEFAULT_SEM = 1 if _MONTH in {9, 10, 11, 12, 1, 2} else 2 if _MONTH in {3, 4, 5, 6, 7} else None


def _ano_index(anos: list[str]) -> int:
    val = st.session_state.get(SessionKeys.ANO_LETIVO, _DEFAULT_ANO)
    return (anos.index(val) + 1) if val in anos else 0


def _sem_index() -> int:
    val = st.session_state.get(SessionKeys.SEMESTRE, _DEFAULT_SEM)
    return ([1, 2].index(val) + 1) if val in (1, 2) else 0


# ── Widget presence per profile ───────────────────────────────────────
_PROFILE_WIDGETS: dict[str, list[str]] = {
    "Visão Geral":    ["ano_letivo", "semestre", "semana", "dias",
                       "escola", "edificio", "categoria_espaco", "espaco",
                       "ciclo_estudo", "epoca", "curso", "uc",
                       "hide_online", "hide_ghost", "hide_concurrent"],
    "Laboratórios":   ["ano_letivo", "semestre", "semana", "dias",
                       "escola", "categoria_espaco", "edificio", "espaco",
                       "ciclo_estudo", "epoca", "curso", "uc",
                       "hide_online", "hide_ghost", "hide_concurrent"],
    "Alertas":        ["ano_letivo", "semestre", "semana", "dias",
                       "escola", "categoria_espaco", "edificio",
                       "epoca", "hide_online", "hide_ghost", "hide_concurrent"],
    "Comparação":     ["ano_letivo", "semestre", "semana", "dias",
                       "escola", "categoria_espaco", "edificio",
                       "epoca", "hide_online", "hide_ghost", "hide_concurrent"],
    "Detalhe Sala":   ["ano_letivo", "semestre",
                       "escola", "edificio", "departamento",
                       "hide_online", "hide_ghost"],
    "Qualidade":      ["ano_letivo", "semestre"],
    "Salas Vazias":   ["ano_letivo", "semestre",
                       "escola", "departamento", "edificio"],
}

# ── Reset callback ────────────────────────────────────────────────────
def _reset_filters() -> None:
    """Reset all filter session keys to their defaults.
    Uses SessionKeys.RESETTABLE so this list is always complete."""
    anos = get_anos_letivos()
    month = datetime.now().month
    defaults = {
        SessionKeys.ANO_LETIVO:      anos[0] if anos else Sentinel.NO_FILTER,
        SessionKeys.SEMESTRE:        (1 if month in {9,10,11,12,1,2}
                                      else 2 if month in {3,4,5,6,7}
                                      else Sentinel.NO_FILTER),
        SessionKeys.SEMANA:          Sentinel.NO_FILTER_F,
        SessionKeys.DIAS:            [],
        SessionKeys.ESCOLA:          Sentinel.NO_FILTER,
        SessionKeys.DEPARTAMENTO:    Sentinel.NO_FILTER,
        SessionKeys.EDIFICIO:        Sentinel.NO_FILTER,
        SessionKeys.CATEGORIA:       Sentinel.NO_FILTER,
        SessionKeys.ESPACO:          Sentinel.NO_FILTER,
        SessionKeys.CICLO:           Sentinel.NO_FILTER,
        SessionKeys.EPOCA:           Sentinel.NO_FILTER,
        SessionKeys.CURSO:           Sentinel.NO_FILTER,
        SessionKeys.UC:              Sentinel.NO_FILTER,
        SessionKeys.HIDE_ONLINE:     False,
        SessionKeys.HIDE_GHOST:      False,
        SessionKeys.HIDE_CONCURRENT: False,
    }
    for key in SessionKeys.RESETTABLE:
        st.session_state[key] = defaults.get(key, Sentinel.NO_FILTER)


# ── Active filters summary string ─────────────────────────────────────
def _build_active_string(vals: dict) -> str:
    parts = []
    if vals.get("ano_letivo"):         parts.append(f"📅 {vals['ano_letivo']}")
    if vals.get("semestre"):           parts.append(f"Sem {vals['semestre']}")
    if vals.get("semana"):             parts.append(f"S{vals['semana']}")
    if vals.get("dias"):               parts.append(f"Dias: {', '.join(vals['dias'][:2])}{'…' if len(vals['dias'])>2 else ''}")
    if vals.get("escola"):             parts.append(f"🏛 {vals['escola']}")
    if vals.get("departamento_label"): parts.append(f"🏢 {vals['departamento_label']}")
    if vals.get("edificio"):           parts.append(f"🏗 {vals['edificio']}")
    if vals.get("categoria_espaco"):   parts.append(f"📐 {vals['categoria_espaco']}")
    if vals.get("ciclo_estudo"):       parts.append(f"🎓 {vals['ciclo_estudo']}")
    if vals.get("epoca"):              parts.append(f"📆 {vals['epoca']}")
    return " | ".join(parts) if parts else "Sem filtros ativos"


# ── Filter renderer — returns a dict instead of mutating a global ──────
def _render_filters(profile: str) -> dict:
    """
    Render sidebar widgets for the current profile.
    Returns a plain dict of raw widget values (pre-extraction).
    No side effects on module-level state.
    """
    fw       = _PROFILE_WIDGETS[profile]
    is_lab   = profile == "Laboratórios"
    vals: dict = {}
    groups_seen: set[str] = set()

    _GROUP_LABELS = {
        "ano_letivo": "📅 Calendário", "semestre": "📅 Calendário",
        "semana": "📅 Calendário",     "dias": "📅 Calendário",
        "escola": "📍 Local",          "departamento": "📍 Local",
        "edificio": "📍 Local",        "categoria_espaco": "📍 Local",
        "espaco": "📍 Local",
        "ciclo_estudo": "🎯 Atividades", "epoca": "🎯 Atividades",
        "curso": "🎯 Atividades",      "uc": "🎯 Atividades",
    }

    for wname in fw:
        group = _GROUP_LABELS.get(wname)
        if group and group not in groups_seen:
            groups_seen.add(group)
            st.markdown(
                f'<div class="sidebar-group-header">{group}</div>',
                unsafe_allow_html=True,
            )

        if wname == "ano_letivo":
            vals["ano_letivo"] = st.selectbox(
                "Ano Letivo", [Sentinel.NO_FILTER] + _ANOS,
                index=_ano_index(_ANOS), key=SessionKeys.ANO_LETIVO,
            )
        elif wname == "semestre":
            vals["semestre"] = st.selectbox(
                "Semestre", [Sentinel.NO_FILTER, 1, 2],
                index=_sem_index(), key=SessionKeys.SEMESTRE,
            )
        elif wname == "semana":
            ano = vals.get("ano_letivo", Sentinel.NO_FILTER)
            sem = vals.get("semestre",   Sentinel.NO_FILTER)
            opts = [Sentinel.NO_FILTER_F] + [
                str(s) for s in get_semanas(
                    ano_letivo=ano if ano != Sentinel.NO_FILTER else None,
                    semestre=sem   if sem != Sentinel.NO_FILTER else None,
                )
            ]
            vals["semana"] = st.selectbox("Semana", opts, key=SessionKeys.SEMANA)
        elif wname == "dias":
            vals["dias"] = st.multiselect(
                "Dia da Semana", get_dias_semana(), default=[], key=SessionKeys.DIAS
            )
        elif wname == "escola":
            vals["escola"] = st.selectbox(
                "Escola", [Sentinel.NO_FILTER] + get_escolas(), key=SessionKeys.ESCOLA
            )
        elif wname == "departamento":
            dept_map    = get_departamentos()
            labels      = [Sentinel.NO_FILTER] + list(dept_map.keys())
            sel_label   = st.selectbox("Departamento", labels, key=SessionKeys.DEPARTAMENTO)
            vals["departamento_label"] = sel_label if sel_label != Sentinel.NO_FILTER else None
            vals["departamento"] = (
                dept_map.get(sel_label) if sel_label != Sentinel.NO_FILTER else None
            )
        elif wname == "edificio":
            esc  = vals.get("escola")
            esc  = esc if esc != Sentinel.NO_FILTER else None
            opts = [Sentinel.NO_FILTER] + get_edificios(escola=esc, only_labs=is_lab)
            vals["edificio"] = st.selectbox("Edifício", opts, key=SessionKeys.EDIFICIO)
        elif wname == "categoria_espaco":
            if is_lab:
                vals["categoria_espaco"] = st.selectbox(
                    "Categoria", [LAB_CATEGORY], disabled=True, key=SessionKeys.CATEGORIA
                )
            else:
                vals["categoria_espaco"] = st.selectbox(
                    "Categoria", [Sentinel.NO_FILTER] + get_categorias(),
                    key=SessionKeys.CATEGORIA,
                )
        elif wname == "espaco":
            edf = vals.get("edificio",        Sentinel.NO_FILTER)
            cat = vals.get("categoria_espaco", Sentinel.NO_FILTER)
            opts = [Sentinel.NO_FILTER] + get_espacos(
                edificio=edf if edf != Sentinel.NO_FILTER else None,
                categoria=cat if cat != Sentinel.NO_FILTER else None,
                only_labs=is_lab,
            )
            vals["espaco"] = st.selectbox("Sala", opts, key=SessionKeys.ESPACO)
        elif wname == "ciclo_estudo":
            vals["ciclo_estudo"] = st.selectbox(
                "Ciclo Estudo",
                [Sentinel.NO_FILTER] + get_ciclos_estudo(only_labs=is_lab),
                key=SessionKeys.CICLO,
            )
        elif wname == "epoca":
            vals["epoca"] = st.selectbox(
                "Período/Época", [Sentinel.NO_FILTER] + get_epocas(), key=SessionKeys.EPOCA
            )
        elif wname == "curso":
            ciclo = vals.get("ciclo_estudo", Sentinel.NO_FILTER)
            ciclo = ciclo if ciclo != Sentinel.NO_FILTER else None
            vals["curso"] = st.selectbox(
                "Curso",
                [Sentinel.NO_FILTER] + get_cursos(ciclo=ciclo, only_labs=is_lab),
                key=SessionKeys.CURSO,
            )
        elif wname == "uc":
            curso = vals.get("curso", Sentinel.NO_FILTER)
            curso = curso if curso != Sentinel.NO_FILTER else None
            vals["uc"] = st.selectbox(
                "UC",
                [Sentinel.NO_FILTER] + get_ucs(curso=curso, only_labs=is_lab),
                key=SessionKeys.UC,
            )
        elif wname == "hide_online":
            st.markdown('<div class="sidebar-group-divider"></div>', unsafe_allow_html=True)
            vals["hide_online"] = st.checkbox("Excluir Online", value=False, key=SessionKeys.HIDE_ONLINE)
        elif wname == "hide_ghost":
            vals["hide_ghost"] = st.checkbox("Ocultar Ghost", value=False, key=SessionKeys.HIDE_GHOST)
        elif wname == "hide_concurrent":
            vals["hide_concurrent"] = st.checkbox(
                "Deduplicar Concurrentes", value=False, key=SessionKeys.HIDE_CONCURRENT
            )

    return vals


def _extract_filters(vals: dict) -> Filters:
    """
    Convert raw widget values into a typed Filters dict.
    Only non-default values are included (None / False stay absent
    so downstream functions can use 'if filter.get(key)' safely).
    """
    NF = Sentinel.NO_FILTER

    def _v(key: str):
        val = vals.get(key)
        return val if val and val != NF else None

    f: Filters = {}
    if _v("ano_letivo"):        f["ano_letivo"]       = _v("ano_letivo")
    if _v("semestre"):          f["semestre"]         = int(_v("semestre"))
    if _v("escola"):            f["escola"]           = _v("escola")
    if _v("departamento"):      f["departamento"]     = _v("departamento")
    if _v("categoria_espaco"):  f["categoria_espaco"] = _v("categoria_espaco")
    if _v("edificio"):          f["edificio"]         = _v("edificio")
    if _v("espaco"):            f["espaco"]           = _v("espaco")
    if _v("ciclo_estudo"):      f["ciclo_estudo"]     = _v("ciclo_estudo")
    if _v("curso"):             f["curso"]            = _v("curso")
    if _v("uc"):                f["uc"]               = _v("uc")
    if _v("epoca"):             f["epoca"]            = _v("epoca")
    f["hide_online"]     = bool(vals.get("hide_online",     False))
    f["hide_concurrent"] = bool(vals.get("hide_concurrent", False))
    f["hide_ghost"]      = bool(vals.get("hide_ghost",      False))
    return f


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">🔍 Filtros</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    raw_vals = _render_filters(profile)

    st.markdown(
        f'<div class="active-filters">{_build_active_string(raw_vals)}</div>',
        unsafe_allow_html=True,
    )
    st.button("Limpar Filtros", use_container_width=True, on_click=_reset_filters)
    st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(f"**{st.session_state.get('username', '—')}**")
    if st.button("Terminar Sessão", use_container_width=True, type="primary"):
        logout()
    st.markdown("---")

# ── Build typed filters dict ──────────────────────────────────────────
filters: Filters = _extract_filters(raw_vals)
filters["only_labs"] = (profile == "Laboratórios")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ── Profile dispatch ──────────────────────────────────────────────────
_PROFILE_REGISTRY: dict[str, type] = {
    "Visão Geral":   GeneralProfile,
    "Laboratórios":  LabsProfile,
    "Detalhe Sala":  SpaceDetailProfile,
    "Alertas":       AlertsProfile,
    "Comparação":    ComparisonProfile,
    "Qualidade":     QualityProfile,
    "Salas Vazias":  EmptyRoomsProfile,
}

if profile in _PROFILE_REGISTRY:
    _PROFILE_REGISTRY[profile]().render(filters)
