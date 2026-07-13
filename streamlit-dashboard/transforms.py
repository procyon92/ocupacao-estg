from __future__ import annotations
import pandas as pd
from config import Omisso, DAILY_CAPACITY_MINUTES
from utils import normalizar_docente, clamp, pct


def apply_filtros_post(
    df: pd.DataFrame,
    hide_online: bool = False,
    hide_concurrent: bool = False,
    hide_ghost: bool = False,
) -> pd.DataFrame:
    # Aplica exclusões opcionais após a query principal — não toca na BD
    if df.empty:
        return df
    if hide_online and "is_online" in df.columns:
        df = df[df["is_online"] != 1]
    if hide_concurrent and "Flag_Evento_Agregado" in df.columns:
        df = df[df["Flag_Evento_Agregado"] != 1]
    if hide_ghost and "Numero_Presencas" in df.columns:
        df = df[df["Numero_Presencas"] > 0]
    return df


def normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # Normaliza colunas comuns a todos os DataFrames de factos:
    # converte DataCompleta para datetime e limpa nomes de docentes em branco.
    # Trabalha sempre numa cópia — o DataFrame original nunca é mutado.
    if df.empty:
        return df

    df = df.copy()

    if "DataCompleta" in df.columns:
        df["DataCompleta"] = pd.to_datetime(df["DataCompleta"])

    if "Docente_Responsavel" in df.columns:
        df["Docente_Responsavel"] = df["Docente_Responsavel"].apply(normalizar_docente)

    return df


def compute_kpis_gerais(df: pd.DataFrame) -> dict:
    # Calcula o conjunto padrão de KPIs usado pelos perfis gerais.
    # Assume que o DataFrame já foi normalizado (DataCompleta é datetime).
    total_ocup       = len(df)
    espacos_ocupados = df["Nome_Espaco"].nunique()
    total_min        = df["Duracao_Minutos"].sum()
    dias             = df["DataCompleta"].nunique()

    # Taxa de ocupação = minutos ocupados / capacidade total disponível
    cap_disponivel = espacos_ocupados * dias * DAILY_CAPACITY_MINUTES
    taxa_ocup      = clamp(pct(total_min, cap_disponivel)) if cap_disponivel > 0 else 0

    avg_min    = df["Duracao_Minutos"].mean() if total_ocup > 0 else 0
    total_pres = int(df["Numero_Presencas"].sum())
    # Ghost session = aula registada com 0 presenças
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


def build_dados_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    # Agrega o número de ocupações por (dia da semana, hora de início) — base para o mapa de calor
    return (
        df.groupby(["DiaSemana", "Hora_Inicio"])
        .size()
        .reset_index(name="Total_Ocupacoes")
    )


def combine_flags_anomalia(row: pd.Series) -> str:
    # Constrói uma string legível com as anomalias detetadas para uma linha de factos
    flags = []
    if row.get("Ghost_Flag"):  flags.append("👻 Ghost")
    if row.get("UC_Flag"):     flags.append("📚 UC N/D")
    if row.get("Curso_Flag"):  flags.append("🎓 Curso N/D")
    if row.get("Resp_Flag"):   flags.append("👤 Resp. N/D")
    if row.get("Hora_Flag"):   flags.append("🌙 Horário Invulgar")
    return " | ".join(flags) if flags else "—"