"""
utils.py — Pure helper functions with no Streamlit or DB dependencies.
Everything here is stateless and unit-testable in isolation.
"""
from __future__ import annotations
from config import Omisso


def fmt_duracao(minutes: float) -> str:
    """
    Convert a minute count to a human-readable string.
    Examples: 90 → "1h30", 5 → "0h05", 0 → "0h00"
    """
    if minutes is None or minutes != minutes:   # NaN guard
        return "—"
    total = int(round(minutes))
    h, m = divmod(total, 60)
    return f"{h}h{m:02d}"


def fmt_duracao_long(minutes: float) -> str:
    """
    Verbose form used in the labs capacity table.
    Examples: 90 → "1h 30m", 5 → "0h 05m"
    """
    if minutes is None or minutes != minutes:
        return "—"
    total = int(round(minutes))
    h, m = divmod(total, 60)
    return f"{h}h {m:02d}m"


def normalizar_docente(value: object) -> str:
    """
    Replace a blank or single-char teacher name with the canonical Omisso.
    Applied post-query so the display layer never sees raw empty strings.
    """
    if isinstance(value, str) and len(value.strip()) <= 1:
        return Omisso.INDEFINIDO
    return value  # type: ignore[return-value]


def pct(numerator: float, denominator: float, decimals: int = 1) -> float:
    """Safe percentage: returns 0.0 when denominator is 0."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, decimals)


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))
