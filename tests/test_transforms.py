"""
test_transforms.py — Testes unitários para o módulo transforms.py do dashboard.

Cobre:
  - apply_post_filters   : filtros de pós-query (online, ghost, sobrepostos)
  - normalize_dataframe  : normalização de datas e docentes
  - compute_general_kpis : cálculo dos KPIs gerais
  - build_heatmap_data   : agregação para mapa de calor
  - combine_anomaly_flags: construção de string de anomalias

Executar com:
    pytest tests/test_transforms.py -v
"""

import pytest
import sys
import os
import pandas as pd
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit-dashboard'))

# Mock do streamlit antes de importar módulos que o usam
st_mock = MagicMock()
st_mock.cache_data = lambda **kwargs: (lambda f: f)
sys.modules['streamlit'] = st_mock

from transforms import (
    apply_post_filters,
    normalize_dataframe,
    compute_general_kpis,
    build_heatmap_data,
    combine_anomaly_flags,
)


# Fixtures partilhadas

@pytest.fixture
def df_base():
    # DataFrame mínimo com todas as colunas usadas pelos filtros e KPIs
    return pd.DataFrame({
        'ID_Ocupacao':          ['001', '002', '003', '004'],
        'DataCompleta':         ['2024-10-15', '2024-10-16', '2024-10-17', '2024-10-18'],
        'Nome_Espaco':          ['SALA A', 'SALA A', 'SALA B', 'SALA B'],
        'Edificio':             ['ED. A', 'ED. A', 'ED. B', 'ED. B'],
        'DiaSemana':            ['Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira'],
        'Hora_Inicio':          [9, 10, 11, 14],
        'Duracao_Minutos':      [120, 90, 60, 120],
        'Numero_Presencas':     [10, 0, 5, 8],
        'is_online':            [0, 0, 1, 0],
        'Flag_Evento_Agregado': [0, 1, 0, 0],
        'Docente_Responsavel':  ['Prof. Silva', 'N/D', 'Prof. Costa', 'Indefinido/N.D.'],
    })


# apply_post_filters

class TestApplyPostFilters:

    def test_sem_filtros_devolve_tudo(self, df_base):
        result = apply_post_filters(df_base)
        assert len(result) == 4

    def test_hide_online_remove_online(self, df_base):
        result = apply_post_filters(df_base, hide_online=True)
        assert all(result['is_online'] != 1)
        assert len(result) == 3

    def test_hide_online_sem_coluna_nao_falha(self):
        df = pd.DataFrame({'ID_Ocupacao': ['001']})
        result = apply_post_filters(df, hide_online=True)
        assert len(result) == 1

    def test_hide_concurrent_remove_agregados(self, df_base):
        result = apply_post_filters(df_base, hide_concurrent=True)
        assert all(result['Flag_Evento_Agregado'] != 1)
        assert len(result) == 3

    def test_hide_ghost_remove_sem_presencas(self, df_base):
        result = apply_post_filters(df_base, hide_ghost=True)
        assert all(result['Numero_Presencas'] > 0)
        assert len(result) == 3

    def test_todos_filtros_combinados(self, df_base):
        result = apply_post_filters(df_base, hide_online=True, hide_concurrent=True, hide_ghost=True)
        assert all(result['is_online'] != 1)
        assert all(result['Flag_Evento_Agregado'] != 1)
        assert all(result['Numero_Presencas'] > 0)

    def test_dataframe_vazio_devolve_vazio(self):
        df = pd.DataFrame()
        result = apply_post_filters(df, hide_online=True, hide_ghost=True)
        assert result.empty

    def test_nao_muta_dataframe_original(self, df_base):
        original_len = len(df_base)
        apply_post_filters(df_base, hide_online=True)
        assert len(df_base) == original_len


# normalize_dataframe

class TestNormalizeDataframe:

    def test_converte_data_para_datetime(self, df_base):
        result = normalize_dataframe(df_base)
        assert pd.api.types.is_datetime64_any_dtype(result['DataCompleta'])

    def test_nao_muta_dataframe_original(self, df_base):
        original_tipo = type(df_base['DataCompleta'].iloc[0])
        normalize_dataframe(df_base)
        assert type(df_base['DataCompleta'].iloc[0]) == original_tipo

    def test_dataframe_vazio_devolve_vazio(self):
        result = normalize_dataframe(pd.DataFrame())
        assert result.empty

    def test_sem_coluna_data_nao_falha(self):
        df = pd.DataFrame({'Nome_Espaco': ['SALA A']})
        result = normalize_dataframe(df)
        assert 'Nome_Espaco' in result.columns

    def test_normaliza_docente_nd(self, df_base):
        result = normalize_dataframe(df_base)
        # N/D e Indefinido/N.D. devem ser normalizados
        assert 'Docente_Responsavel' in result.columns

    def test_sem_coluna_docente_nao_falha(self):
        df = pd.DataFrame({'DataCompleta': ['2024-10-15']})
        result = normalize_dataframe(df)
        assert 'DataCompleta' in result.columns


# compute_general_kpis

class TestComputeGeneralKpis:

    @pytest.fixture
    def df_norm(self, df_base):
        return normalize_dataframe(df_base)

    def test_devolve_todas_as_chaves(self, df_norm):
        result = compute_general_kpis(df_norm)
        for key in ['total_ocup', 'espacos_ocupados', 'total_min', 'dias',
                    'taxa_ocup', 'avg_min', 'total_pres', 'ghost_pct']:
            assert key in result, f"Chave em falta: {key}"

    def test_total_ocup_correto(self, df_norm):
        result = compute_general_kpis(df_norm)
        assert result['total_ocup'] == 4

    def test_espacos_ocupados_correto(self, df_norm):
        result = compute_general_kpis(df_norm)
        assert result['espacos_ocupados'] == 2

    def test_total_presencas_correto(self, df_norm):
        result = compute_general_kpis(df_norm)
        assert result['total_pres'] == 23  # 10+0+5+8

    def test_ghost_pct_correto(self, df_norm):
        # 1 de 4 tem 0 presenças = 25%
        result = compute_general_kpis(df_norm)
        assert result['ghost_pct'] == 25.0

    def test_taxa_ocup_entre_0_e_100(self, df_norm):
        result = compute_general_kpis(df_norm)
        assert 0 <= result['taxa_ocup'] <= 100

    def test_total_min_correto(self, df_norm):
        result = compute_general_kpis(df_norm)
        assert result['total_min'] == 390  # 120+90+60+120

    def test_dias_correto(self, df_norm):
        result = compute_general_kpis(df_norm)
        assert result['dias'] == 4

    def test_dataframe_vazio_devolve_zeros(self):
        df = normalize_dataframe(pd.DataFrame(columns=[
            'DataCompleta', 'Nome_Espaco', 'Duracao_Minutos', 'Numero_Presencas'
        ]))
        result = compute_general_kpis(df)
        assert result['total_ocup'] == 0
        assert result['ghost_pct'] == 0


# build_heatmap_data

class TestBuildHeatmapData:

    def test_devolve_colunas_corretas(self, df_base):
        result = build_heatmap_data(df_base)
        assert 'DiaSemana' in result.columns
        assert 'Hora_Inicio' in result.columns
        assert 'Total_Ocupacoes' in result.columns

    def test_agrupa_por_dia_e_hora(self, df_base):
        result = build_heatmap_data(df_base)
        assert len(result) == 4  # 4 combinações únicas de dia+hora

    def test_contagem_correta(self):
        df = pd.DataFrame({
            'DiaSemana':   ['Segunda-feira', 'Segunda-feira', 'Terça-feira'],
            'Hora_Inicio': [9, 9, 10],
        })
        result = build_heatmap_data(df)
        segunda_9 = result[(result['DiaSemana'] == 'Segunda-feira') & (result['Hora_Inicio'] == 9)]
        assert segunda_9['Total_Ocupacoes'].iloc[0] == 2

    def test_dataframe_vazio_devolve_vazio(self):
        df = pd.DataFrame(columns=['DiaSemana', 'Hora_Inicio'])
        result = build_heatmap_data(df)
        assert result.empty


# combine_anomaly_flags

class TestCombineAnomalyFlags:

    def test_sem_flags_devolve_traco(self):
        row = pd.Series({'Ghost_Flag': None, 'UC_Flag': None, 'Curso_Flag': None, 'Resp_Flag': None})
        assert combine_anomaly_flags(row) == '—'

    def test_ghost_flag(self):
        row = pd.Series({'Ghost_Flag': 'Ghost', 'UC_Flag': None, 'Curso_Flag': None, 'Resp_Flag': None})
        result = combine_anomaly_flags(row)
        assert '👻 Ghost' in result

    def test_uc_flag(self):
        row = pd.Series({'Ghost_Flag': None, 'UC_Flag': 'Unmapped_UC', 'Curso_Flag': None, 'Resp_Flag': None})
        result = combine_anomaly_flags(row)
        assert '📚 UC N/D' in result

    def test_curso_flag(self):
        row = pd.Series({'Ghost_Flag': None, 'UC_Flag': None, 'Curso_Flag': 'Unmapped_Curso', 'Resp_Flag': None})
        result = combine_anomaly_flags(row)
        assert '🎓 Curso N/D' in result

    def test_resp_flag(self):
        row = pd.Series({'Ghost_Flag': None, 'UC_Flag': None, 'Curso_Flag': None, 'Resp_Flag': 'Unmapped_Resp'})
        result = combine_anomaly_flags(row)
        assert '👤 Resp. N/D' in result

    def test_multiplas_flags(self):
        row = pd.Series({'Ghost_Flag': 'Ghost', 'UC_Flag': 'Unmapped_UC', 'Curso_Flag': None, 'Resp_Flag': None})
        result = combine_anomaly_flags(row)
        assert '👻 Ghost' in result
        assert '📚 UC N/D' in result
        assert '|' in result

    def test_todas_as_flags(self):
        row = pd.Series({
            'Ghost_Flag': 'Ghost',
            'UC_Flag':    'Unmapped_UC',
            'Curso_Flag': 'Unmapped_Curso',
            'Resp_Flag':  'Unmapped_Resp',
        })
        result = combine_anomaly_flags(row)
        assert '👻 Ghost' in result
        assert '📚 UC N/D' in result
        assert '🎓 Curso N/D' in result
        assert '👤 Resp. N/D' in result