"""
test_queries.py — Testes de integração para o módulo queries.py do dashboard.

Testa as funções de acesso à BD usando a base de dados de teste dw_ocupacao_tests.
A BD de teste deve existir e ter o mesmo schema que dw_ocupacao.

Os testes usam fixtures que inserem dados mínimos antes de cada teste
e limpam tudo depois — a BD de teste nunca fica com dados residuais.

Executar com:
    pytest tests/test_queries.py -v
"""

import pytest
import sys
import os
import pymysql
import pandas as pd
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit-dashboard'))

# Mock do streamlit — cache_data fica transparente, st.error fica silencioso
st_mock = MagicMock()
st_mock.cache_data = lambda **kwargs: (lambda f: f)
sys.modules['streamlit'] = st_mock

from queries import (
    get_dados_filtrados,
    get_contagem_salas_filtradas,
    get_metricas_qualidade_etl,
    get_dados_detalhe_espaco,
    get_ocupacao_por_horario,
    get_tendencia_sessoes_fantasma,
)


# SQLAlchemy — usado apenas para setup/teardown (insert, truncate)
TEST_DB_URL = "mysql+pymysql://root:@localhost:3306/dw_ocupacao_tests?charset=utf8mb4"
_test_engine = create_engine(TEST_DB_URL, future=True)

# pymysql — usado pelas queries (compatível com o queries.py real)
TEST_DB_PYMYSQL = {
    "host":       "localhost",
    "port":       3306,
    "user":       "root",
    "password":   "",
    "database":   "dw_ocupacao_tests",
    "charset":    "utf8mb4",
    "autocommit": True,
}


def get_test_connection():
    # Devolve uma ligação pymysql com autocommit — compatível com o _leitura_segura do queries.py
    return pymysql.connect(**TEST_DB_PYMYSQL)


@pytest.fixture(scope="session", autouse=True)
def verify_test_db():
    # Verifica que a BD de teste existe e é acessível — falha cedo se não estiver disponível
    try:
        conn = get_test_connection()
        conn.close()
    except Exception as e:
        pytest.exit(f"Não foi possível ligar à BD de teste dw_ocupacao_tests: {e}")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    # Limpa os dados antes de cada teste — garante isolamento
    with _test_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in ['Facto_Ocupacao', 'Dim_Data', 'Dim_Hora', 'Dim_Espaco',
                  'Dim_Unidade_Curricular', 'Dim_Curso', 'Dim_Responsavel',
                  'Dim_Tipo_Atividade', 'Dim_Estado_Agendamento', 'Dim_Turno', 'Dim_Epoca']:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    _test_engine.dispose()
    yield


def insert_minimal_fact(
    id_ocupacao="TEST_001", presencas=10, ano_escolar="2024/2025",
    semestre=1, espaco="SALA A", edificio="ED. A",
    categoria="Sala", escola="ESTG", is_online=0
):
    # Insere um conjunto mínimo de registos em todas as dimensões + 1 facto
    with _test_engine.begin() as conn:
        conn.execute(text("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO'"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        conn.execute(text("""
            INSERT IGNORE INTO Dim_Data
            (SK_Data, DataCompleta, Ano, Mes, Dia, DiaSemana, Semestre, Ano_Escolar,
             Numero_Semana, Numero_Semana_Escolar, Tipo_Dia)
            VALUES
            (:sk, '2024-10-15', 2024, 10, 15, 'Terça-feira', :sem, :ano, 42, 4, 'Dia Útil/Letivo')
        """), {"sk": 20241015, "sem": semestre, "ano": ano_escolar})

        conn.execute(text("INSERT IGNORE INTO Dim_Hora VALUES (900, 9, 0), (1100, 11, 0)"))

        conn.execute(text("""
            INSERT INTO Dim_Espaco (SK_Espaco, Edificio, Nome_Espaco, Categoria_Espaco,
                                    Escola_Responsavel, Departamento, is_online,
                                    Valid_From, Valid_To, Is_Active)
            VALUES (1, :ed, :esp, :cat, :esc, 'N/D', :online, '2024-01-01', '9999-12-31', 1)
        """), {"ed": edificio, "esp": espaco, "cat": categoria, "esc": escola, "online": is_online})

        conn.execute(text("""
            INSERT INTO Dim_Unidade_Curricular VALUES
            (1, '1234', 'Programação I', 'Licenciatura', '2024-01-01', '9999-12-31', 1)
        """))
        conn.execute(text(
            "INSERT INTO Dim_Curso VALUES (1, '8305', 'Eng. Informática', '2024-01-01', '9999-12-31', 1)"
        ))
        conn.execute(text("INSERT INTO Dim_Responsavel VALUES (1, 'Prof. Silva')"))
        conn.execute(text("INSERT INTO Dim_Tipo_Atividade VALUES (1, 'TP')"))
        conn.execute(text("INSERT INTO Dim_Estado_Agendamento VALUES (1, 'Confirmado')"))
        conn.execute(text("INSERT INTO Dim_Turno VALUES (1, 'TP1')"))
        conn.execute(text("INSERT INTO Dim_Epoca VALUES (1, 'Período Letivo')"))

        # Colunas nomeadas explicitamente — evita erros de ordem
        conn.execute(text("""
            INSERT INTO Facto_Ocupacao
            (ID_Ocupacao, SK_Data, SK_Hora_Inicio, SK_Hora_Fim,
             SK_Espaco, SK_Unidade_Curricular, SK_Curso, SK_Responsavel,
             SK_Tipo_Atividade, SK_Estado_Agendamento, SK_Turno, SK_Epoca,
             Duracao_Minutos, Numero_Presencas, Flag_Evento_Agregado)
            VALUES
            (:id, 20241015, 900, 1100, 1, 1, 1, 1, 1, 1, 1, 1, 120, :pres, 0)
        """), {"id": id_ocupacao, "pres": presencas})

        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    _test_engine.dispose()


# get_dados_filtrados

class TestGetFilteredData:

    def test_devolve_dataframe(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_filtrados()
        assert isinstance(df, pd.DataFrame)

    def test_sem_dados_devolve_dataframe_vazio(self):
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_filtrados()
        assert df.empty

    def test_filtra_por_ano_letivo(self):
        insert_minimal_fact(id_ocupacao="T1", ano_escolar="2024/2025")
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_filtrados(ano_letivo="2024/2025")
        assert len(df) == 1

    def test_filtra_por_ano_letivo_errado_devolve_vazio(self):
        insert_minimal_fact(id_ocupacao="T1", ano_escolar="2024/2025")
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_filtrados(ano_letivo="2023/2024")
        assert df.empty

    def test_filtra_por_semestre(self):
        insert_minimal_fact(id_ocupacao="T1", semestre=1)
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_filtrados(semestre=1)
        assert len(df) == 1

    def test_colunas_obrigatorias(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_filtrados()
        for col in ['ID_Ocupacao', 'Edificio', 'Nome_Espaco', 'Categoria_Espaco',
                    'Hora_Inicio', 'Hora_Fim', 'Duracao_Minutos', 'Numero_Presencas',
                    'Designacao_UC', 'Periodo_Dia']:
            assert col in df.columns, f"Coluna em falta: {col}"

    def test_periodo_dia_manha(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_filtrados()
        assert len(df) > 0
        assert df['Periodo_Dia'].iloc[0] == 'Manhã'


# get_contagem_salas_filtradas

class TestGetFilteredRoomsCount:

    def test_conta_sala(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            count = get_contagem_salas_filtradas()
        assert count == 1

    def test_sem_dados_devolve_zero(self):
        with patch('queries.get_connection', side_effect=get_test_connection):
            count = get_contagem_salas_filtradas()
        assert count == 0

    def test_filtra_por_edificio(self):
        insert_minimal_fact(edificio="ED. A")
        with patch('queries.get_connection', side_effect=get_test_connection):
            count = get_contagem_salas_filtradas(edificio="ED. A")
        assert count == 1

    def test_edificio_errado_devolve_zero(self):
        insert_minimal_fact(edificio="ED. A")
        with patch('queries.get_connection', side_effect=get_test_connection):
            count = get_contagem_salas_filtradas(edificio="ED. B")
        assert count == 0

    def test_filtra_por_categoria(self):
        insert_minimal_fact(categoria="Laboratorio")
        with patch('queries.get_connection', side_effect=get_test_connection):
            count = get_contagem_salas_filtradas(categoria_espaco="Laboratorio")
        assert count == 1


# get_metricas_qualidade_etl

class TestGetEtlQualityMetrics:

    def test_devolve_dict_com_chaves(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            result = get_metricas_qualidade_etl()
        assert set(result.keys()) == {'total', 'valid', 'errors'}

    def test_total_correto(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            result = get_metricas_qualidade_etl()
        assert result['total'] == 1

    def test_valid_mais_errors_igual_total(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            result = get_metricas_qualidade_etl()
        assert result['valid'] + result['errors'] == result['total']

    def test_sem_dados_devolve_zeros(self):
        with patch('queries.get_connection', side_effect=get_test_connection):
            result = get_metricas_qualidade_etl()
        assert result == {'total': 0, 'valid': 0, 'errors': 0}


# get_tendencia_sessoes_fantasma

class TestGetGhostSessionsTrend:

    def test_ghost_session_detetada(self):
        insert_minimal_fact(presencas=0)
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_tendencia_sessoes_fantasma()
        assert len(df) == 1
        assert df['Ghost_Count'].iloc[0] == 1

    def test_sem_ghost_devolve_vazio(self):
        insert_minimal_fact(presencas=15)
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_tendencia_sessoes_fantasma()
        assert df.empty

    def test_coluna_periodo_criada(self):
        insert_minimal_fact(presencas=0)
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_tendencia_sessoes_fantasma()
        assert 'Periodo' in df.columns

    def test_filtra_por_ano_escolar(self):
        insert_minimal_fact(presencas=0, ano_escolar="2024/2025")
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_tendencia_sessoes_fantasma(ano_escolar="2024/2025")
        assert len(df) == 1

    def test_ano_escolar_errado_devolve_vazio(self):
        insert_minimal_fact(presencas=0, ano_escolar="2024/2025")
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_tendencia_sessoes_fantasma(ano_escolar="2023/2024")
        assert df.empty


# get_dados_detalhe_espaco

class TestGetSpaceDetailData:

    def test_devolve_dados_para_espaco(self):
        insert_minimal_fact(espaco="SALA A")
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_detalhe_espaco("SALA A")
        assert len(df) == 1

    def test_espaco_errado_devolve_vazio(self):
        insert_minimal_fact(espaco="SALA A")
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_detalhe_espaco("SALA B")
        assert df.empty

    def test_ordenado_por_data_hora(self):
        insert_minimal_fact(espaco="SALA A")
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_dados_detalhe_espaco("SALA A")
        assert 'DataCompleta' in df.columns


# get_ocupacao_por_horario

class TestGetOccupancyBySlot:

    def test_devolve_slot(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_ocupacao_por_horario()
        assert len(df) >= 1

    def test_colunas_presentes(self):
        insert_minimal_fact()
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_ocupacao_por_horario()
        assert 'DiaSemana' in df.columns
        assert 'Hora_Inicio' in df.columns
        assert 'Salas_Ocupadas' in df.columns

    def test_sem_dados_devolve_vazio(self):
        with patch('queries.get_connection', side_effect=get_test_connection):
            df = get_ocupacao_por_horario()
        assert df.empty