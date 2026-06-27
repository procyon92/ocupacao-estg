from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict


class Filters(TypedDict, total=False):
    # Todos os filtros possíveis passados entre módulos.
    # total=False significa que nenhum campo é obrigatório — campo ausente = sem filtro aplicado
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
    # Registo central de todas as chaves do st.session_state usadas na app.
    # Usar estas constantes em vez de strings diretas evita erros de digitação
    # e garante que _reset_filters() limpa sempre tudo o que devia limpar.

    # Valores dos filtros
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

    # Toggles
    HIDE_ONLINE     = "v4_toggle_online"
    HIDE_GHOST      = "v4_toggle_ghost"
    HIDE_CONCURRENT = "v4_toggle_concurrent"

    # Navegação
    NAV             = "v4_nav"

    # Sub-widgets do detalhe de espaço
    PROFILE_C_ROOM  = "v2_profile_c_room"
    CAL_YEAR        = "v2_cal_year"
    CAL_MONTH       = "v2_cal_month"

    # Todas as chaves que o _reset_filters() deve limpar
    RESETTABLE: tuple = (
        ANO_LETIVO, SEMESTRE, SEMANA, DIAS,
        ESCOLA, DEPARTAMENTO, EDIFICIO, CATEGORIA, ESPACO,
        CICLO, EPOCA, CURSO, UC,
        HIDE_ONLINE, HIDE_GHOST, HIDE_CONCURRENT,
    )