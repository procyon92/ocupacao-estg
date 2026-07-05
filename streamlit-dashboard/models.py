from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict


class Filters(TypedDict, total=False):
    # Todos os filtros possíveis passados entre módulos.
    # total=False significa que nenhum campo é obrigatório — campo ausente = sem filtro aplicado
    ano_letivo:       Optional[str]
    semestre:         Optional[int]
    escola:           Optional[str]
    departamento:     Optional[str]
    edificio:         Optional[str]
    categoria_espaco: Optional[str]
    espaco:           Optional[str]
    ciclo_estudo:     Optional[str]
    curso:            Optional[str]
    uc:               Optional[str]
    epoca:            Optional[str]
    hide_online:      bool
    hide_concurrent:  bool
    hide_ghost:       bool
    only_labs:        bool


class SessionKeys:
    # Registo central de todas as chaves do st.session_state usadas na app.
    # Usar estas constantes em vez de strings diretas evita erros de digitação
    # e garante que _repor_filtros() limpa sempre tudo o que devia limpar.

    # Valores dos filtros
    ANO_LETIVO      = "filter_ano_letivo"
    SEMESTRE        = "filter_semestre"
    SEMANA          = "filter_semana"
    DIAS            = "filter_dias"
    ESCOLA          = "filter_escola"
    DEPARTAMENTO    = "filter_departamento"
    EDIFICIO        = "filter_edificio"
    CATEGORIA       = "filter_categoria_espaco"
    ESPACO          = "filter_espaco"
    CICLO           = "filter_ciclo_estudo"
    EPOCA           = "filter_epoca"
    CURSO           = "filter_curso"
    UC              = "filter_uc"

    # Toggles
    HIDE_ONLINE     = "toggle_online"
    HIDE_GHOST      = "toggle_ghost"
    HIDE_CONCURRENT = "toggle_concurrent"

    # Navegação
    NAV             = "nav"

    # Sub-widgets do detalhe de espaço
    PROFILE_C_ROOM  = "profile_room"
    CAL_YEAR        = "cal_year"
    CAL_MONTH       = "cal_month"

    # Todas as chaves que o _repor_filtros() deve limpar
    RESETTABLE: tuple = (
        ANO_LETIVO, SEMESTRE, SEMANA, DIAS,
        ESCOLA, DEPARTAMENTO, EDIFICIO, CATEGORIA, ESPACO,
        CICLO, EPOCA, CURSO, UC,
        HIDE_ONLINE, HIDE_GHOST, HIDE_CONCURRENT,
    )