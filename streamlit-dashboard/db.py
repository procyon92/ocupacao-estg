from __future__ import annotations
import logging
import pymysql
import streamlit as st
from config import DB_CONFIG

logger = logging.getLogger(__name__)

# Pool = conjunto de ligações à BD que ficam abertas e prontas a reutilizar
@st.cache_resource
def _get_pool():
    # Cria uma pool uma vez por processo e o Streamlit trata de a reutilizar
    try:
        from dbutils.persistent_db import PersistentDB
        pool = PersistentDB(
            creator=pymysql,
            maxusage=None,
            **DB_CONFIG,
        )
        logger.info("DBUtils PersistentDB pool created.")
        return pool
    except ImportError:
        # Se o dbutils não estiver instalado, avisa e usa ligações diretas
        logger.warning(
            "dbutils not installed — falling back to direct connections. "
            "Run: pip install dbutils"
        )
        return None


def get_connection() -> pymysql.connections.Connection:
    # Tenta usar o pool; se não houver, abre uma ligação normal
    pool = _get_pool()
    if pool is not None:
        return pool.connection()
    return pymysql.connect(**DB_CONFIG)
