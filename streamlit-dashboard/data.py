"""
data.py — COMPATIBILITY SHIM.

All logic has moved to queries.py / transforms.py / utils.py.
This module re-exports every public symbol from the original data.py
so that plots.py, calendar_chart.py, and auth.py need zero changes.

TO MIGRATE: replace `from data import X` with the appropriate source module.
"""
# ── queries ───────────────────────────────────────────────────────────
from queries import (                           # noqa: F401
    get_cascade_options,
    get_anos_letivos,
    get_escolas,
    get_departamentos,
    get_edificios,
    get_categorias,
    get_espacos,
    get_ciclos_estudo,
    get_cursos,
    get_ucs,
    get_epocas,
    get_dias_semana,
    get_semanas,
    get_filtered_rooms_count,
    get_filtered_rooms_count as get_total_rooms_count,
    get_filtered_data,
    get_space_detail_data,
    get_occupancy_by_slot,
    get_free_rooms_by_interval,
    get_etl_quality_metrics,
    get_unmapped_records_count,
    get_ghost_sessions_trend,
    get_raw_anomalies,
)

# ── transforms ────────────────────────────────────────────────────────
from transforms import (                        # noqa: F401
    normalize_dataframe,
    apply_post_filters,
    compute_general_kpis,
    build_heatmap_data,
    combine_anomaly_flags,
)

# ── utils ─────────────────────────────────────────────────────────────
from utils import fmt_duration, fmt_duration_long, normalize_docente  # noqa: F401


def get_semestres() -> list:
    """Original API preserved."""
    return [1, 2]
