"""
transforms.py — Post-query data cleaning and KPI computation.

All functions are pure (DataFrame in → DataFrame / dict out).
No DB access, no Streamlit calls, no side effects.
"""
from __future__ import annotations
import pandas as pd
from config import Sentinel
from utils import normalize_docente, clamp, pct


def apply_post_filters(
    df: pd.DataFrame,
    hide_online: bool = False,
    hide_concurrent: bool = False,
    hide_ghost: bool = False,
) -> pd.DataFrame:
    """Apply optional row-level exclusions after the main query."""
    if df.empty:
        return df
    if hide_online and "is_online" in df.columns:
        df = df[df["is_online"] != 1]
    if hide_concurrent and "Flag_Evento_Agregado" in df.columns:
        df = df[df["Flag_Evento_Agregado"] != 1]
    if hide_ghost and "Numero_Presencas" in df.columns:
        df = df[df["Numero_Presencas"] > 0]
    return df


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply consistent column transformations to any fact DataFrame.
    - Parse DataCompleta to datetime
    - Normalize blank teacher names

    Always works on a copy so the caller's DataFrame is never mutated.
    """
    if df.empty:
        return df

    df = df.copy()  # single copy — safe to mutate from here on

    if "DataCompleta" in df.columns:
        df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])

    if "Docente_Responsavel" in df.columns:
        df["Docente_Responsavel"] = df["Docente_Responsavel"].apply(normalize_docente)

    return df


def compute_general_kpis(df: pd.DataFrame) -> dict:
    """
    Compute the standard KPI set used by profiles A and E.
    Assumes df has already been normalized (DataCompleta is datetime).
    """
    total_ocup       = len(df)
    espacos_ocupados = df["Nome_Espaco"].nunique()
    total_min        = df["Duracao_Minutos"].sum()
    dias             = df["DataCompleta"].nunique()

    cap_disponivel = espacos_ocupados * dias * 480
    taxa_ocup      = clamp(pct(total_min, cap_disponivel)) if cap_disponivel > 0 else 0

    avg_min    = df["Duracao_Minutos"].mean() if total_ocup > 0 else 0
    total_pres = int(df["Numero_Presencas"].sum())
    ghost_pct  = round(pct((df["Numero_Presencas"] == 0).sum(), total_ocup), 1) if total_ocup else 0

    return {
        "total_ocup":        total_ocup,
        "espacos_ocupados":  espacos_ocupados,
        "total_min":         total_min,
        "dias":              dias,
        "taxa_ocup":         round(taxa_ocup),
        "avg_min":           avg_min,
        "total_pres":        total_pres,
        "ghost_pct":         ghost_pct,
    }


def build_heatmap_data(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["DiaSemana", "Hora_Inicio"])
        .size()
        .reset_index(name="Total_Ocupacoes")
    )


def combine_anomaly_flags(row: pd.Series) -> str:
    """Build a human-readable anomaly string from flag columns."""
    flags = []
    if row.get("Ghost_Flag"):  flags.append("👻 Ghost")
    if row.get("UC_Flag"):     flags.append("📚 UC N/D")
    if row.get("Curso_Flag"):  flags.append("🎓 Curso N/D")
    if row.get("Resp_Flag"):   flags.append("👤 Resp. N/D")
    return " | ".join(flags) if flags else "—"
