"""
profiles/base.py — Abstract base class for all dashboard profiles.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import streamlit as st
import pandas as pd
from models import Filters


class BaseProfile(ABC):
    """
    Each profile subclass implements render() and nothing else.
    Shared rendering helpers live here so profiles stay thin.
    """

    @abstractmethod
    def render(self, filters: Filters) -> None:
        """Render this profile into the active Streamlit container."""
        ...

    # ── Shared helpers ────────────────────────────────────────────────

    @staticmethod
    def _empty(msg: str = "Sem dados para os filtros selecionados.") -> None:
        st.info(msg)

    @staticmethod
    def _h2(title: str) -> None:
        st.markdown(f"<h2 style='color:#1B2139;font-weight:700;'>{title}</h2>",
                    unsafe_allow_html=True)

    @staticmethod
    def _subtitle(text: str) -> None:
        st.markdown(f"<p style='color:#64748B;font-size:0.85rem;'>{text}</p>",
                    unsafe_allow_html=True)
