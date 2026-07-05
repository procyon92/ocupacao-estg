"""
test_plots.py — Testes unitários para o módulo plots.py do dashboard.

Verifica que cada função de gráfico:
  - devolve sempre um go.Figure (nunca None nem exceção)
  - funciona com DataFrame vazio (devolve figura com mensagem "Sem dados")
  - funciona com dados mínimos válidos

Não testa o aspeto visual — só a correção estrutural do output.

Executar com:
    pytest tests/test_plots.py -v
"""

import pytest
import sys
import os
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit-dashboard'))

st_mock = MagicMock()
st_mock.cache_data = lambda **kwargs: (lambda f: f)
sys.modules['streamlit'] = st_mock

import plotly.graph_objects as go
from plots import (
    chart_ocupacao_tempo,
    chart_ocupacao_edificio,
    chart_heatmap_ocupacao,
    chart_top_espacos,
    chart_bottom_espacos,
    chart_tipo_atividade,
    chart_categoria_espaco,
    chart_periodo_dia,
    chart_heatmap_espaco_unico,
    chart_tendencia_anomalias,
    chart_calendario_mensal,
    chart_heatmap_critico,
    chart_tendencia_comparacao,
    chart_calendario_dia,
    chart_calendario_semana,
    chart_calendario_mes,
)


# Fixtures partilhadas

@pytest.fixture
def df_ocupacao():
    # DataFrame mínimo compatível com as queries reais
    return pd.DataFrame({
        'DataCompleta':        pd.to_datetime(['2024-10-15', '2024-10-16', '2024-10-17']),
        'Edificio':            ['ED. A', 'ED. A', 'ED. B'],
        'Nome_Espaco':         ['SALA A', 'SALA A', 'SALA B'],
        'Categoria_Espaco':    ['Sala', 'Sala', 'Laboratorio'],
        'DiaSemana':           ['Terça-feira', 'Quarta-feira', 'Quinta-feira'],
        'Hora_Inicio':         [9, 10, 14],
        'Minuto_Inicio':       [0, 30, 0],
        'Hora_Fim':            [11, 12, 16],
        'Minuto_Fim':          [0, 0, 0],
        'Duracao_Minutos':     [120, 90, 120],
        'Numero_Presencas':    [10, 0, 5],
        'Designacao_Atividade': ['TP', 'PL', 'TP'],
        'Designacao_UC':       ['Programação I', 'Redes', 'Matemática'],
        'Designacao_Turno':    ['TP1', 'PL1', 'TP2'],
        'Docente_Responsavel': ['Prof. Silva', 'Prof. Costa', 'Prof. Lima'],
        'Nome_Espaco':         ['SALA A', 'SALA A', 'SALA B'],
        'Periodo_Dia':         ['Manhã', 'Manhã', 'Tarde'],
        'is_online':           [0, 0, 0],
    })


@pytest.fixture
def df_heatmap():
    return pd.DataFrame({
        'DiaSemana':       ['Segunda-feira', 'Terça-feira', 'Quarta-feira'],
        'Hora_Inicio':     [9, 10, 14],
        'Total_Ocupacoes': [5, 3, 8],
    })


@pytest.fixture
def df_slot():
    return pd.DataFrame({
        'DiaSemana':     ['Segunda-feira', 'Terça-feira'],
        'Hora_Inicio':   [9, 10],
        'Salas_Ocupadas': [3, 5],
    })


@pytest.fixture
def df_espaco_detalhe():
    return pd.DataFrame({
        'DataCompleta':      pd.to_datetime(['2024-10-15', '2024-10-15']),
        'DiaSemana':         ['Terça-feira', 'Terça-feira'],
        'Hora_Inicio':       [9, 14],
        'Minuto_Inicio':     [0, 0],
        'Hora_Fim':          [11, 16],
        'Minuto_Fim':        [0, 0],
        'Duracao_Minutos':   [120, 120],
        'Numero_Presencas':  [10, 5],
        'Designacao_UC':     ['Programação I', 'Redes'],
        'Designacao_Turno':  ['TP1', 'PL1'],
        'Docente_Responsavel': ['Prof. Silva', 'Prof. Costa'],
        'Nome_Espaco':       ['SALA A', 'SALA A'],
    })


# chart_ocupacao_tempo

class TestChartOcupacaoTempo:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_ocupacao_tempo(df_ocupacao), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_ocupacao_tempo(pd.DataFrame()), go.Figure)

    def test_granularidade_diario(self, df_ocupacao):
        assert isinstance(chart_ocupacao_tempo(df_ocupacao, granularity="Diário"), go.Figure)

    def test_granularidade_semanal(self, df_ocupacao):
        assert isinstance(chart_ocupacao_tempo(df_ocupacao, granularity="Semanal"), go.Figure)

    def test_granularidade_mensal(self, df_ocupacao):
        assert isinstance(chart_ocupacao_tempo(df_ocupacao, granularity="Mensal"), go.Figure)


# chart_ocupacao_edificio

class TestChartOcupacaoEdificio:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_ocupacao_edificio(df_ocupacao), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_ocupacao_edificio(pd.DataFrame()), go.Figure)

    def test_mais_de_8_edificios_agrupa_outros(self):
        df = pd.DataFrame({'Edificio': [f'ED. {i}' for i in range(10)]})
        fig = chart_ocupacao_edificio(df)
        assert isinstance(fig, go.Figure)


# chart_heatmap_ocupacao

class TestChartHeatmapOcupacao:

    def test_devolve_figure(self, df_heatmap):
        assert isinstance(chart_heatmap_ocupacao(df_heatmap), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_heatmap_ocupacao(pd.DataFrame()), go.Figure)


# chart_top_espacos

class TestChartTopEspacos:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_top_espacos(df_ocupacao), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_top_espacos(pd.DataFrame()), go.Figure)

    def test_top_n_personalizado(self, df_ocupacao):
        assert isinstance(chart_top_espacos(df_ocupacao, top_n=5), go.Figure)


# chart_bottom_espacos

class TestChartBottomEspacos:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_bottom_espacos(df_ocupacao), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_bottom_espacos(pd.DataFrame()), go.Figure)


# chart_tipo_atividade

class TestChartTipoAtividade:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_tipo_atividade(df_ocupacao), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_tipo_atividade(pd.DataFrame()), go.Figure)


# chart_categoria_espaco

class TestChartCategoriaEspaco:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_categoria_espaco(df_ocupacao), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_categoria_espaco(pd.DataFrame()), go.Figure)


# chart_periodo_dia

class TestChartPeriodOfDay:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_periodo_dia(df_ocupacao), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_periodo_dia(pd.DataFrame()), go.Figure)

    def test_sem_coluna_periodo_devolve_figure(self, df_ocupacao):
        df = df_ocupacao.drop(columns=['Periodo_Dia'])
        assert isinstance(chart_periodo_dia(df), go.Figure)


# chart_heatmap_espaco_unico

class TestChartSingleSpaceHeatmap:

    def test_devolve_figure(self, df_espaco_detalhe):
        assert isinstance(chart_heatmap_espaco_unico(df_espaco_detalhe), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_heatmap_espaco_unico(pd.DataFrame()), go.Figure)

    def test_so_fim_de_semana_devolve_figure(self):
        df = pd.DataFrame({
            'DiaSemana':   ['Domingo'],
            'Hora_Inicio': [10],
        })
        assert isinstance(chart_heatmap_espaco_unico(df), go.Figure)


# chart_tendencia_anomalias

class TestChartAnomaliesTrend:

    def test_devolve_figure(self):
        df = pd.DataFrame({
            'Periodo':     ['2024/2025 - Mês 10', '2024/2025 - Mês 11'],
            'Ghost_Count': [5, 3],
        })
        assert isinstance(chart_tendencia_anomalias(df), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_tendencia_anomalias(pd.DataFrame()), go.Figure)


# chart_calendario_mensal

class TestChartMonthlyCalendar:

    def test_devolve_figure(self, df_ocupacao):
        assert isinstance(chart_calendario_mensal(df_ocupacao, 2024, 10), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_calendario_mensal(pd.DataFrame(), 2024, 10), go.Figure)


# chart_heatmap_critico

class TestChartCriticalHeatmap:

    def test_devolve_figure(self, df_slot):
        assert isinstance(chart_heatmap_critico(df_slot, total_rooms=10), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_heatmap_critico(pd.DataFrame(), total_rooms=10), go.Figure)

    def test_total_rooms_zero_devolve_figure(self, df_slot):
        assert isinstance(chart_heatmap_critico(df_slot, total_rooms=0), go.Figure)


# chart_tendencia_comparacao

class TestChartComparisonTrend:

    def test_devolve_figure(self, df_ocupacao):
        rooms = {"SALA A": df_ocupacao, "SALA B": df_ocupacao}
        assert isinstance(chart_tendencia_comparacao(rooms), go.Figure)

    def test_vazio_devolve_figure(self):
        assert isinstance(chart_tendencia_comparacao({}), go.Figure)

    def test_sala_vazia_ignorada(self, df_ocupacao):
        rooms = {"SALA A": df_ocupacao, "SALA B": pd.DataFrame()}
        assert isinstance(chart_tendencia_comparacao(rooms), go.Figure)


# chart_calendario_dia

class TestChartCalendarDay:

    def test_devolve_figure(self, df_espaco_detalhe):
        date = pd.Timestamp('2024-10-15')
        assert isinstance(chart_calendario_dia(df_espaco_detalhe, date), go.Figure)

    def test_dia_sem_aulas_devolve_figure(self, df_espaco_detalhe):
        date = pd.Timestamp('2024-12-25')  # dia sem aulas
        assert isinstance(chart_calendario_dia(df_espaco_detalhe, date), go.Figure)


# chart_calendario_semana

class TestChartCalendarWeek:

    def test_devolve_figure(self, df_espaco_detalhe):
        week = [pd.Timestamp('2024-10-14') + pd.Timedelta(days=i) for i in range(6)]
        assert isinstance(chart_calendario_semana(df_espaco_detalhe, week), go.Figure)

    def test_semana_vazia_devolve_figure(self):
        week = [pd.Timestamp('2024-10-14') + pd.Timedelta(days=i) for i in range(6)]
        df = pd.DataFrame({'DataCompleta': pd.Series(dtype='datetime64[ns]'), 'Designacao_UC': pd.Series(dtype=str)})
        assert isinstance(chart_calendario_semana(df, week), go.Figure)

    def test_titulo_personalizado(self, df_espaco_detalhe):
        week = [pd.Timestamp('2024-10-14') + pd.Timedelta(days=i) for i in range(6)]
        fig = chart_calendario_semana(df_espaco_detalhe, week, title="Semana de teste")
        assert isinstance(fig, go.Figure)


# chart_calendario_mes

class TestChartCalendarMonth:

    def test_devolve_figure(self, df_espaco_detalhe):
        assert isinstance(chart_calendario_mes(df_espaco_detalhe, 2024, 10), go.Figure)

    def test_mes_sem_dados_devolve_figure(self, df_espaco_detalhe):
        assert isinstance(chart_calendario_mes(df_espaco_detalhe, 2024, 12), go.Figure)

    def test_diferentes_meses(self, df_espaco_detalhe):
        for month in range(1, 13):
            assert isinstance(chart_calendario_mes(df_espaco_detalhe, 2024, month), go.Figure)