"""
test_load.py — Testes de integração para o módulo load.py do pipeline ETL.

Testa o DataLoader usando a base de dados de teste dw_ocupacao_tests.
A BD de teste deve existir e ter o mesmo schema que dw_ocupacao.

Cobre:
  - prepare_fact_payload    : preparação e validação do payload de factos
  - load_fixed_pk_dimension : inserção de dimensões com PK fixa
  - load_dimension_scd1     : inserção e lookup SCD tipo 1
  - load_dimension_scd2     : inserção, expiração e lookup SCD tipo 2
  - load_fact               : inserção de factos repetidos
  - ensure_dummy_dimension_records : inserção dos registos SK=0

Executar com:
    pytest tests/test_load.py -v
"""

import pytest
import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'processo_etl'))

from load import DataLoader


TEST_DB_URL = "mysql+pymysql://root:@localhost:3306/dw_ocupacao_tests?charset=utf8mb4"
_test_engine = create_engine(TEST_DB_URL, future=True)


@pytest.fixture(scope="session")
def loader():
    # DataLoader apontado para a BD de teste
    return DataLoader(
        host="localhost",
        user="root",
        password="",
        db_name="dw_ocupacao_tests",
        port="3306",
    )


@pytest.fixture(scope="session", autouse=True)
def verify_test_db():
    try:
        with _test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
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


def count_rows(table: str) -> int:
    with _test_engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        return result.scalar()


# prepare_fact_payload

class TestPrepareFactPayload:

    def test_adiciona_sks_em_falta(self, loader):
        df = pd.DataFrame({'ID_Ocupacao': ['001']})
        result = loader.prepare_fact_payload(df)
        for sk in ['SK_Data', 'SK_Hora_Inicio', 'SK_Hora_Fim', 'SK_Espaco',
                   'SK_Unidade_Curricular', 'SK_Curso', 'SK_Responsavel',
                   'SK_Tipo_Atividade', 'SK_Estado_Agendamento', 'SK_Turno', 'SK_Epoca']:
            assert sk in result.columns
            assert result[sk].iloc[0] == 0

    def test_adiciona_id_ocupacao_por_defeito(self, loader):
        df = pd.DataFrame({'SK_Data': [1]})
        result = loader.prepare_fact_payload(df)
        assert 'ID_Ocupacao' in result.columns
        assert result['ID_Ocupacao'].iloc[0] == 'DEFAULT_ID'

    def test_adiciona_metricas_em_falta(self, loader):
        df = pd.DataFrame({'ID_Ocupacao': ['001']})
        result = loader.prepare_fact_payload(df)
        assert result['Duracao_Minutos'].iloc[0] == 0
        assert result['Numero_Presencas'].iloc[0] == 0
        assert result['Flag_Evento_Agregado'].iloc[0] == 0

    def test_converte_sks_para_int(self, loader):
        df = pd.DataFrame({
            'ID_Ocupacao': ['001'],
            'SK_Data': ['20241015'],
        })
        result = loader.prepare_fact_payload(df)
        assert result['SK_Data'].dtype in [int, 'int64', 'int32']

    def test_nan_sk_fica_zero(self, loader):
        df = pd.DataFrame({
            'ID_Ocupacao': ['001'],
            'SK_Data': [float('nan')],
        })
        result = loader.prepare_fact_payload(df)
        assert result['SK_Data'].iloc[0] == 0

    def test_so_colunas_validas_no_output(self, loader):
        df = pd.DataFrame({
            'ID_Ocupacao': ['001'],
            'coluna_extra': ['ignorada'],
        })
        result = loader.prepare_fact_payload(df)
        assert 'coluna_extra' not in result.columns

    def test_multiplas_linhas(self, loader):
        df = pd.DataFrame({'ID_Ocupacao': ['001', '002', '003']})
        result = loader.prepare_fact_payload(df)
        assert len(result) == 3


# load_fixed_pk_dimension

class TestLoadFixedPkDimension:

    def test_insere_registos_novos(self, loader):
        df = pd.DataFrame({
            'SK_Hora': [100, 200],
            'Hora':    [1, 2],
            'Minuto':  [0, 0],
        })
        loader.load_fixed_pk_dimension(df, 'Dim_Hora', 'SK_Hora')
        assert count_rows('Dim_Hora') == 2

    def test_nao_duplica_registos_existentes(self, loader):
        df = pd.DataFrame({
            'SK_Hora': [100],
            'Hora':    [1],
            'Minuto':  [0],
        })
        loader.load_fixed_pk_dimension(df, 'Dim_Hora', 'SK_Hora')
        loader.load_fixed_pk_dimension(df, 'Dim_Hora', 'SK_Hora')
        assert count_rows('Dim_Hora') == 1

    def test_insere_apenas_novos(self, loader):
        df1 = pd.DataFrame({'SK_Hora': [100], 'Hora': [1], 'Minuto': [0]})
        df2 = pd.DataFrame({'SK_Hora': [100, 200], 'Hora': [1, 2], 'Minuto': [0, 0]})
        loader.load_fixed_pk_dimension(df1, 'Dim_Hora', 'SK_Hora')
        loader.load_fixed_pk_dimension(df2, 'Dim_Hora', 'SK_Hora')
        assert count_rows('Dim_Hora') == 2


# load_dimension_scd1

class TestLoadDimensionScd1:

    def test_insere_registo_novo(self, loader):
        df = pd.DataFrame({'Designacao_Turno': ['TP1'], 'outro': ['x']})
        loader.load_dimension_scd1(df, 'Dim_Turno', ['Designacao_Turno'], 'SK_Turno')
        assert count_rows('Dim_Turno') == 1

    def test_nao_duplica_registo_existente(self, loader):
        df = pd.DataFrame({'Designacao_Turno': ['TP1']})
        loader.load_dimension_scd1(df, 'Dim_Turno', ['Designacao_Turno'], 'SK_Turno')
        loader.load_dimension_scd1(df, 'Dim_Turno', ['Designacao_Turno'], 'SK_Turno')
        assert count_rows('Dim_Turno') == 1

    def test_devolve_sk_preenchida(self, loader):
        df = pd.DataFrame({'Designacao_Turno': ['TP1'], 'valor': [42]})
        result = loader.load_dimension_scd1(df, 'Dim_Turno', ['Designacao_Turno'], 'SK_Turno')
        assert 'SK_Turno' in result.columns
        assert result['SK_Turno'].iloc[0] > 0

    def test_natural_key_inexistente_devolve_sk_zero(self, loader):
        df = pd.DataFrame({'coluna_inexistente': ['x']})
        result = loader.load_dimension_scd1(df, 'Dim_Turno', ['Designacao_Turno'], 'SK_Turno')
        assert result['SK_Turno'].iloc[0] == 0

    def test_insere_multiplos_registos(self, loader):
        df = pd.DataFrame({'Designacao_Turno': ['TP1', 'TP2', 'PL1']})
        loader.load_dimension_scd1(df, 'Dim_Turno', ['Designacao_Turno'], 'SK_Turno')
        assert count_rows('Dim_Turno') == 3

    def test_sk_diferente_por_registo(self, loader):
        df = pd.DataFrame({'Designacao_Turno': ['TP1', 'TP2']})
        result = loader.load_dimension_scd1(df, 'Dim_Turno', ['Designacao_Turno'], 'SK_Turno')
        assert result['SK_Turno'].iloc[0] != result['SK_Turno'].iloc[1]


# load_dimension_scd2

class TestLoadDimensionScd2:

    def _make_espaco_df(self, edificio="ED. A", espaco="SALA A", categoria="Sala",
                        escola="ESTG", is_online=0):
        return pd.DataFrame({
            'Edificio':          [edificio],
            'Nome_Espaco':       [espaco],
            'Categoria_Espaco':  [categoria],
            'Escola_Responsavel': [escola],
            'is_online':         [is_online],
        })

    def test_insere_registo_novo(self, loader):
        df = self._make_espaco_df()
        loader.load_dimension_scd2(
            df, 'Dim_Espaco',
            ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Escola_Responsavel', 'is_online'],
            'SK_Espaco'
        )
        assert count_rows('Dim_Espaco') == 1

    def test_registo_inserido_fica_ativo(self, loader):
        df = self._make_espaco_df()
        loader.load_dimension_scd2(
            df, 'Dim_Espaco',
            ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Escola_Responsavel', 'is_online'],
            'SK_Espaco'
        )
        with _test_engine.connect() as conn:
            result = conn.execute(text("SELECT Is_Active FROM Dim_Espaco")).fetchone()
        assert result[0] == 1

    def test_nao_duplica_registo_sem_alteracao(self, loader):
        df = self._make_espaco_df()
        nks = ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Escola_Responsavel', 'is_online']
        loader.load_dimension_scd2(df, 'Dim_Espaco', nks, 'SK_Espaco')
        loader.load_dimension_scd2(df, 'Dim_Espaco', nks, 'SK_Espaco')
        assert count_rows('Dim_Espaco') == 1

    def test_devolve_sk_preenchida(self, loader):
        df = self._make_espaco_df()
        result = loader.load_dimension_scd2(
            df, 'Dim_Espaco',
            ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Escola_Responsavel', 'is_online'],
            'SK_Espaco'
        )
        assert 'SK_Espaco' in result.columns
        assert result['SK_Espaco'].iloc[0] > 0

    def test_natural_key_inexistente_devolve_sk_zero(self, loader):
        df = pd.DataFrame({'coluna_inexistente': ['x']})
        result = loader.load_dimension_scd2(df, 'Dim_Espaco', ['Edificio'], 'SK_Espaco')
        assert result['SK_Espaco'].iloc[0] == 0

    def test_valid_from_e_valid_to_preenchidos(self, loader):
        df = self._make_espaco_df()
        loader.load_dimension_scd2(
            df, 'Dim_Espaco',
            ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Escola_Responsavel', 'is_online'],
            'SK_Espaco'
        )
        with _test_engine.connect() as conn:
            result = conn.execute(
                text("SELECT Valid_From, Valid_To FROM Dim_Espaco")
            ).fetchone()
        assert result[0] is not None
        assert str(result[1]) == '9999-12-31'


# load_fact

class TestLoadFact:

    def _make_fact_df(self, id_ocupacao="F001"):
        return pd.DataFrame({
            'ID_Ocupacao':          [id_ocupacao],
            'SK_Data':              [0],
            'SK_Hora_Inicio':       [0],
            'SK_Hora_Fim':          [0],
            'SK_Espaco':            [0],
            'SK_Unidade_Curricular': [0],
            'SK_Curso':             [0],
            'SK_Responsavel':       [0],
            'SK_Tipo_Atividade':    [0],
            'SK_Estado_Agendamento': [0],
            'SK_Turno':             [0],
            'SK_Epoca':             [0],
            'Duracao_Minutos':      [120],
            'Numero_Presencas':     [10],
            'Flag_Evento_Agregado': [0],
        })

    def test_insere_facto_novo(self, loader):
        # Garante que os dummies SK=0 existem antes de inserir factos
        loader.ensure_dummy_dimension_records()
        df = self._make_fact_df()
        loader.load_fact(df)
        assert count_rows('Facto_Ocupacao') == 1

    def test_nao_duplica_facto_existente(self, loader):
        loader.ensure_dummy_dimension_records()
        df = self._make_fact_df()
        loader.load_fact(df)
        loader.load_fact(df)
        assert count_rows('Facto_Ocupacao') == 1

    def test_insere_apenas_factos_novos(self, loader):
        loader.ensure_dummy_dimension_records()
        df1 = self._make_fact_df("F001")
        df2 = self._make_fact_df("F002")
        loader.load_fact(df1)
        loader.load_fact(pd.concat([df1, df2], ignore_index=True))
        assert count_rows('Facto_Ocupacao') == 2

    def test_insere_em_chunks(self, loader):
        loader.ensure_dummy_dimension_records()
        rows = [{'ID_Ocupacao': f'F{i:04d}', 'SK_Data': 0, 'SK_Hora_Inicio': 0,
                 'SK_Hora_Fim': 0, 'SK_Espaco': 0, 'SK_Unidade_Curricular': 0,
                 'SK_Curso': 0, 'SK_Responsavel': 0, 'SK_Tipo_Atividade': 0,
                 'SK_Estado_Agendamento': 0, 'SK_Turno': 0, 'SK_Epoca': 0,
                 'Duracao_Minutos': 60, 'Numero_Presencas': 5, 'Flag_Evento_Agregado': 0}
                for i in range(15)]
        df = pd.DataFrame(rows)
        loader.load_fact(df, chunk_size=5)
        assert count_rows('Facto_Ocupacao') == 15


# ensure_dummy_dimension_records

class TestEnsureDummyDimensionRecords:

    def test_cria_dummies_sk_zero(self, loader):
        loader.ensure_dummy_dimension_records()
        tabelas = [
            ('Dim_Hora',                 'SK_Hora'),
            ('Dim_Epoca',                'SK_Epoca'),
            ('Dim_Espaco',               'SK_Espaco'),
            ('Dim_Unidade_Curricular',   'SK_Unidade_Curricular'),
            ('Dim_Curso',                'SK_Curso'),
            ('Dim_Responsavel',          'SK_Responsavel'),
            ('Dim_Tipo_Atividade',       'SK_Tipo_Atividade'),
            ('Dim_Estado_Agendamento',   'SK_Estado_Agendamento'),
            ('Dim_Turno',                'SK_Turno'),
        ]
        with _test_engine.connect() as conn:
            for tabela, sk in tabelas:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {tabela} WHERE {sk} = 0")
                ).scalar()
                assert result == 1, f"Dummy SK=0 em falta em {tabela}"

    def test_idempotente(self, loader):
        # Correr duas vezes não duplica os dummies
        loader.ensure_dummy_dimension_records()
        loader.ensure_dummy_dimension_records()
        with _test_engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM Dim_Turno WHERE SK_Turno = 0")
            ).scalar()
        assert result == 1