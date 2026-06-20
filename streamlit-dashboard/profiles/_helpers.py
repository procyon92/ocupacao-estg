"""
profiles/_helpers.py — Internal helpers shared by profile classes.
Not part of the public API.
"""
from __future__ import annotations
import pandas as pd
from models import Filters
from queries import get_filtered_data
from transforms import normalize_dataframe, apply_post_filters


def load_and_prepare(filters: Filters) -> pd.DataFrame:
    """
    Single call that:
      1. Pulls fact data using only the kwargs get_filtered_data accepts.
      2. Normalizes the DataFrame (dates, teacher names).
      3. Applies post-query row filters (online/ghost/concurrent).

    This is the only place that bridges Filters → get_filtered_data,
    so any future signature change only requires editing here.
    """
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
        only_labs=filters.get("only_labs", False),
    )
    df = normalize_dataframe(raw)
    df = apply_post_filters(
        df,
        hide_online=filters.get("hide_online", False),
        hide_concurrent=filters.get("hide_concurrent", False),
        hide_ghost=filters.get("hide_ghost", False),
    )
    return df
