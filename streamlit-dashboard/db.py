"""
db.py — Database connection pool via st.cache_resource.

Uses a single persistent connection per Streamlit worker process,
preventing the "one new connection per cached function call" anti-pattern.
Falls back to a plain connection if the pool package is unavailable.
"""
from __future__ import annotations
import logging
import pymysql
import streamlit as st
from config import DB_CONFIG

logger = logging.getLogger(__name__)


@st.cache_resource
def _get_pool():
    """
    Returns a thread-safe connection pool (PersistentDB via DBUtils).
    Created once per worker process; destroyed when the app restarts.
    """
    try:
        from dbutils.persistent_db import PersistentDB   # pip install dbutils
        pool = PersistentDB(
            creator=pymysql,
            maxusage=None,
            **DB_CONFIG,
        )
        logger.info("DBUtils PersistentDB pool created.")
        return pool
    except ImportError:
        logger.warning(
            "dbutils not installed — falling back to direct connections. "
            "Run: pip install dbutils"
        )
        return None


def get_connection() -> pymysql.connections.Connection:
    """
    Return an open pymysql connection.
    Callers are responsible for closing it (use inside try/finally).
    """
    pool = _get_pool()
    if pool is not None:
        return pool.connection()
    # Fallback: plain connection (still better than before thanks to
    # @st.cache_data TTLs reducing call frequency)
    return pymysql.connect(**DB_CONFIG)
