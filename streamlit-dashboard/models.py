"""
models.py — Typed contracts: Filters TypedDict, SessionKeys enum.
Eliminates silent key-typo bugs when passing filters between modules.
"""
from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict


class Filters(TypedDict, total=False):
    """
    All possible filter values passed from main.py to page renderers.
    All fields are optional (total=False); absent key == no filter applied.
    """
    ano_letivo:      Optional[str]
    semestre:        Optional[int]
    escola:          Optional[str]
    departamento:    Optional[str]
    edificio:        Optional[str]
    categoria_espaco: Optional[str]
    espaco:          Optional[str]
    ciclo_estudo:    Optional[str]
    curso:           Optional[str]
    uc:              Optional[str]
    epoca:           Optional[str]
    hide_online:     bool
    hide_concurrent: bool
    hide_ghost:      bool
    only_labs:       bool


class SessionKeys:
    """
    Central registry of every st.session_state key used in the app.
    Use these constants instead of raw strings to prevent typos and
    make _reset_filters() complete by construction.
    """
    # ── Filter values ─────────────────────────────────────────────────
    ANO_LETIVO      = "v4_filter_ano_letivo"
    SEMESTRE        = "v4_filter_semestre"
    SEMANA          = "v4_filter_semana"
    DIAS            = "v4_filter_dias"
    ESCOLA          = "v4_filter_escola"
    DEPARTAMENTO    = "v4_filter_departamento"
    EDIFICIO        = "v4_filter_edificio"
    CATEGORIA       = "v4_filter_categoria_espaco"
    ESPACO          = "v4_filter_espaco"
    CICLO           = "v4_filter_ciclo_estudo"
    EPOCA           = "v4_filter_epoca"
    CURSO           = "v4_filter_curso"
    UC              = "v4_filter_uc"

    # ── Toggles ───────────────────────────────────────────────────────
    HIDE_ONLINE     = "v4_toggle_online"
    HIDE_GHOST      = "v4_toggle_ghost"
    HIDE_CONCURRENT = "v4_toggle_concurrent"

    # ── Navigation ────────────────────────────────────────────────────
    NAV             = "v4_nav"

    # ── Space detail sub-widgets ──────────────────────────────────────
    PROFILE_C_ROOM  = "v2_profile_c_room"
    CAL_YEAR        = "v2_cal_year"
    CAL_MONTH       = "v2_cal_month"

    # ── All resettable filter keys (used by _reset_filters) ───────────
    RESETTABLE: tuple = (
        ANO_LETIVO, SEMESTRE, SEMANA, DIAS,
        ESCOLA, DEPARTAMENTO, EDIFICIO, CATEGORIA, ESPACO,
        CICLO, EPOCA, CURSO, UC,
        HIDE_ONLINE, HIDE_GHOST, HIDE_CONCURRENT,
    )
