from __future__ import annotations
import pandas as pd
from models import Filters
from queries import get_filtered_data
from transforms import normalize_dataframe, apply_post_filters


def load_and_prepare(filters: Filters) -> pd.DataFrame:
    # Ponto único que liga os filtros da UI ao get_filtered_data.
    # Qualquer mudança na assinatura do get_filtered_data só precisa de ser feita aqui.

    # 1. vai à BD buscar os dados com os filtros ativos
    raw = get_filtered_data(
        ano_letivo=filters.get("ano_letivo"),
        semestre=filters.get("semestre"),
        escola=filters.get("escola"),
        departamento=filters.get("departamento"),
        edificio=filters.get("edificio"),
        categoria_espaco=filters.get("categoria_espaco"),
        espaco=filters.get("espaco"),
        ciclo_estudo=filters.get("ciclo_estudo"),
        curso=filters.get("curso"),
        uc=filters.get("uc"),
        epoca=filters.get("epoca"),
        semana_escolar=filters.get("semana_escolar"),
        only_labs=filters.get("only_labs", False),
    )
    # 2. normaliza datas e nomes de docentes
    df = normalize_dataframe(raw)
    # 3. aplica filtros de pós-query (online, ghost, sobrepostos)
    df = apply_post_filters(
        df,
        hide_online=filters.get("hide_online", False),
        hide_concurrent=filters.get("hide_concurrent", False),
        hide_ghost=filters.get("hide_ghost", False),
    )
    return df