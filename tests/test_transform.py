"""
test_transform.py — Testes unitários para o módulo transform.py do pipeline ETL.

Cobre as seguintes classes e métodos do DataTransformer:
  - _inicio_semestre          : cálculo dinâmico do início de cada semestre
  - construir_dimensao_data   : geração da Dim_Data completa
  - construir_dimensao_hora   : geração da Dim_Hora completa
  - _limpar_strings           : normalização e limpeza de strings
  - _normalizar_edificios     : remoção de sufixos entre parênteses
  - _classificar_espaco       : classificação do tipo de espaço
  - _classificar_departamento : inferência do departamento pela sigla
  - _processar_cursos         : limpeza e normalização do ficheiro de cursos
  - _aplicar_filtros_negocio  : deteção de sessões online e remoção de outliers
  - _gerar_chaves_temporais   : geração de SK_Data, SK_Hora_Inicio, SK_Hora_Fim
  - _gerar_id_ocupacao        : geração do identificador único de ocupação
  - _classificar_epoca        : classificação da época letiva pelo mês
  - apply_pipeline            : pipeline completo de transformação dimensional

Cada classe de teste isola um método e cobre os casos normais,
casos limite (ex: anos bissextos, agosto, domingo) e casos de erro.

Executar com:
    pytest tests/test_transform.py -v
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'processo_etl'))

import pandas as pd
import numpy as np
from transform import DataTransformer


@pytest.fixture
def t():
    return DataTransformer()


# _inicio_semestre

class TestInicioSemestre:

    def test_sem1_e_segunda_feira(self, t):
        # Sem 1 deve começar numa segunda-feira
        result = t._inicio_semestre(2024, 1)
        assert result.dayofweek == 0

    def test_sem1_e_em_setembro(self, t):
        result = t._inicio_semestre(2024, 1)
        assert result.month == 9

    def test_sem1_e_terceira_semana(self, t):
        # A 3ª segunda-feira de setembro significa que há pelo menos 14 dias antes
        result = t._inicio_semestre(2024, 1)
        assert result.day >= 15

    def test_sem2_e_segunda_feira(self, t):
        result = t._inicio_semestre(2024, 2)
        assert result.dayofweek == 0

    def test_sem2_e_em_fevereiro(self, t):
        result = t._inicio_semestre(2024, 2)
        assert result.month == 2

    def test_sem2_ano_bissexto(self, t):
        # 2024 é bissexto — fevereiro tem 29 dias
        result = t._inicio_semestre(2024, 2)
        assert result.month == 2
        assert result.day <= 29

    def test_sem2_ano_nao_bissexto(self, t):
        # 2023 não é bissexto — fevereiro tem 28 dias
        result = t._inicio_semestre(2023, 2)
        assert result.month == 2
        assert result.day <= 28


# construir_dimensao_data

class TestConstruirDimensaoData:

    def test_colunas_obrigatorias(self, t):
        df = t.construir_dimensao_data('2024-01-01', '2024-01-31')
        for col in ['SK_Data', 'DataCompleta', 'Ano', 'Mes', 'Dia',
                    'Numero_Semana', 'DiaSemana', 'Semestre',
                    'Ano_Escolar', 'Numero_Semana_Escolar', 'Tipo_Dia']:
            assert col in df.columns, f"Coluna em falta: {col}"

    def test_sk_data_formato(self, t):
        df = t.construir_dimensao_data('2024-03-15', '2024-03-15')
        assert df['SK_Data'].iloc[0] == 20240315

    def test_agosto_e_semestre_0(self, t):
        df = t.construir_dimensao_data('2024-08-01', '2024-08-31')
        assert (df['Semestre'] == 0).all()

    def test_outubro_e_semestre_1(self, t):
        df = t.construir_dimensao_data('2024-10-01', '2024-10-31')
        assert (df['Semestre'] == 1).all()

    def test_marco_e_semestre_2(self, t):
        df = t.construir_dimensao_data('2024-03-01', '2024-05-31')
        assert (df['Semestre'] == 2).all()

    def test_ano_escolar_setembro(self, t):
        # Setembro de 2024 deve pertencer ao ano letivo 2024/2025
        df = t.construir_dimensao_data('2024-09-01', '2024-09-30')
        assert (df['Ano_Escolar'] == '2024/2025').all()

    def test_ano_escolar_janeiro(self, t):
        # Janeiro de 2025 deve pertencer ao ano letivo 2024/2025
        df = t.construir_dimensao_data('2025-01-01', '2025-01-31')
        assert (df['Ano_Escolar'] == '2024/2025').all()

    def test_sabado_fim_de_semana(self, t):
        # 2024-03-16 é sábado
        df = t.construir_dimensao_data('2024-03-16', '2024-03-16')
        assert df['Tipo_Dia'].iloc[0] == 'Fim de Semana'

    def test_dia_util(self, t):
        # 2024-03-18 é segunda-feira
        df = t.construir_dimensao_data('2024-03-18', '2024-03-18')
        assert df['Tipo_Dia'].iloc[0] == 'Dia Útil/Letivo'

    def test_agosto_ferias(self, t):
        df = t.construir_dimensao_data('2024-08-15', '2024-08-15')
        assert df['Tipo_Dia'].iloc[0] == 'Férias'

    def test_sem_registos_duplicados(self, t):
        df = t.construir_dimensao_data('2024-01-01', '2024-12-31')
        assert df['SK_Data'].nunique() == len(df)

    def test_janeiro_semana_escolar_sem1(self, t):
        # Janeiro de 2026 deve ter semana letiva > 1 no Sem 1 do ano letivo 2025/2026
        # Usa intervalo desde setembro para garantir contexto correto
        df = t.construir_dimensao_data('2025-09-01', '2026-01-31')
        df_jan = df[(df['Semestre'] == 1) & (pd.to_datetime(df['DataCompleta']).dt.month == 1)]
        assert not df_jan.empty
        assert df_jan['Numero_Semana_Escolar'].max() > 1

# construir_dimensao_hora

class TestConstruirDimensaoHora:

    def test_total_registos(self, t):
        df = t.construir_dimensao_hora()
        assert len(df) == 1440  # 24 * 60

    def test_sk_hora_meia_noite(self, t):
        df = t.construir_dimensao_hora()
        assert df['SK_Hora'].iloc[0] == 0

    def test_sk_hora_ultimo(self, t):
        df = t.construir_dimensao_hora()
        assert df['SK_Hora'].iloc[-1] == 2359

    def test_colunas(self, t):
        df = t.construir_dimensao_hora()
        assert set(df.columns) == {'SK_Hora', 'Hora', 'Minuto'}


# _limpar_strings

class TestLimparStrings:

    def test_strip_espacos(self, t):
        df = pd.DataFrame({'edificio': ['  Ed A  ']})
        result = t._limpar_strings(df)
        assert result['edificio'].iloc[0] == 'ED A'

    def test_edificio_maiusculas(self, t):
        df = pd.DataFrame({'edificio': ['ed. a']})
        result = t._limpar_strings(df)
        assert result['edificio'].iloc[0] == 'ED. A'

    def test_nan_string_para_na(self, t):
        df = pd.DataFrame({'outro_campo': ['nan']})
        result = t._limpar_strings(df)
        assert pd.isna(result['outro_campo'].iloc[0])

    def test_string_vazia_para_na(self, t):
        df = pd.DataFrame({'edificio': ['']})
        result = t._limpar_strings(df)
        assert pd.isna(result['edificio'].iloc[0])

    def test_coluna_normal_nao_maiuscula(self, t):
        df = pd.DataFrame({'nome': ['joão silva']})
        result = t._limpar_strings(df)
        assert result['nome'].iloc[0] == 'joão silva'


# _normalizar_edificios

class TestNormalizarEdificios:

    def test_remove_parenteses(self, t):
        df = pd.DataFrame({'edificio': ['Ed. A (ESTG)']})
        result = t._normalizar_edificios(df)
        assert result['edificio'].iloc[0] == 'Ed. A'

    def test_sem_parenteses_inalterado(self, t):
        df = pd.DataFrame({'edificio': ['Ed. B']})
        result = t._normalizar_edificios(df)
        assert result['edificio'].iloc[0] == 'Ed. B'

    def test_desig_edf_tambem_normalizado(self, t):
        df = pd.DataFrame({'desig_edf': ['Edifício C (IPL)']})
        result = t._normalizar_edificios(df)
        assert result['desig_edf'].iloc[0] == 'Edifício C'

    def test_nan_fica_na(self, t):
        df = pd.DataFrame({'edificio': [np.nan]})
        result = t._normalizar_edificios(df)
        assert pd.isna(result['edificio'].iloc[0])


# _classificar_espaco

class TestClassificarEspaco:

    def test_laboratorio_por_lab(self, t):
        df = pd.DataFrame({'espaco': ['LAB DEI'], 'is_online': [False]})
        result = t._classificar_espaco(df)
        assert result['categoria_espaco'].iloc[0] == 'Laboratorio'

    def test_laboratorio_por_prefixo_l(self, t):
        df = pd.DataFrame({'espaco': ['L001'], 'is_online': [False]})
        result = t._classificar_espaco(df)
        assert result['categoria_espaco'].iloc[0] == 'Laboratorio'

    def test_anfiteatro(self, t):
        df = pd.DataFrame({'espaco': ['ANFITEATRO A'], 'is_online': [False]})
        result = t._classificar_espaco(df)
        assert result['categoria_espaco'].iloc[0] == 'Anfiteatro'

    def test_gabinete(self, t):
        df = pd.DataFrame({'espaco': ['GAB 101'], 'is_online': [False]})
        result = t._classificar_espaco(df)
        assert result['categoria_espaco'].iloc[0] == 'Gabinete'

    def test_sala_por_defeito(self, t):
        df = pd.DataFrame({'espaco': ['SALA 205'], 'is_online': [False]})
        result = t._classificar_espaco(df)
        assert result['categoria_espaco'].iloc[0] == 'Sala'

    def test_online_substitui_espaco(self, t):
        df = pd.DataFrame({'espaco': ['SALA 205'], 'is_online': [True]})
        result = t._classificar_espaco(df)
        assert result['espaco'].iloc[0] == 'ONLINE'
        assert result['categoria_espaco'].iloc[0] == 'Online'


# _classificar_departamento

class TestClassificarDepartamento:

    def test_dei(self, t):
        df = pd.DataFrame({'espaco': ['LAB DEI 101']})
        result = t._classificar_departamento(df)
        assert result['departamento'].iloc[0] == 'Departamento de Engenharia Informática'

    def test_dec(self, t):
        df = pd.DataFrame({'espaco': ['SALA DEC 201']})
        result = t._classificar_departamento(df)
        assert result['departamento'].iloc[0] == 'Departamento de Engenharia Civil'

    def test_desconhecido(self, t):
        df = pd.DataFrame({'espaco': ['SALA XYZ']})
        result = t._classificar_departamento(df)
        assert result['departamento'].iloc[0] == 'N/D'

    def test_sem_coluna_espaco(self, t):
        df = pd.DataFrame({'outro': ['qualquer']})
        result = t._classificar_departamento(df)
        assert result['departamento'].iloc[0] == 'N/D'


# _processar_cursos

class TestProcessarCursos:

    def test_remove_prefixo_codigo(self, t):
        df = pd.DataFrame({
            'codigo_curso': ['8305'],
            'codigo_uc':    ['83051234'],
            'nome_curso':   ['Engenharia Informática'],
        })
        result = t._processar_cursos(df)
        assert result['codigo_uc_limpo'].iloc[0] == '1234'

    def test_sem_prefixo_inalterado(self, t):
        df = pd.DataFrame({
            'codigo_curso': ['8305'],
            'codigo_uc':    ['9999'],
            'nome_curso':   ['Outro Curso'],
        })
        result = t._processar_cursos(df)
        assert result['codigo_uc_limpo'].iloc[0] == '9999'

    def test_remove_zeros_a_esquerda(self, t):
        df = pd.DataFrame({
            'codigo_curso': ['8305'],
            'codigo_uc':    ['83050042'],
            'nome_curso':   ['Curso X'],
        })
        result = t._processar_cursos(df)
        assert result['codigo_uc_limpo'].iloc[0] == '42'

    def test_linhas_vazias_removidas(self, t):
        df = pd.DataFrame({
            'codigo_curso': ['8305', ''],
            'codigo_uc':    ['83051234', ''],
            'nome_curso':   ['Curso A', 'Curso B'],
        })
        result = t._processar_cursos(df)
        assert len(result) == 1

    def test_renomeia_designacao_curso(self, t):
        df = pd.DataFrame({
            'codigo_curso':     ['8305'],
            'codigo_uc':        ['83051234'],
            'designacao_curso': ['Eng. Informática'],
        })
        result = t._processar_cursos(df)
        assert 'nome_curso' in result.columns


# _aplicar_filtros_negocio

class TestAplicarFiltrosNegocio:

    def _make_df(self, inicio, fim, espaco='SALA A'):
        return pd.DataFrame({
            'datainicio': [pd.Timestamp(inicio)],
            'datafim':    [pd.Timestamp(fim)],
            'espaco':     [espaco],
        })

    def test_duracao_valida(self, t):
        df = self._make_df('2024-03-18 09:00', '2024-03-18 11:00')
        result = t._aplicar_filtros_negocio(df)
        assert len(result) == 1
        assert result['duracao_minutos'].iloc[0] == 120

    def test_duracao_zero_removida(self, t):
        df = self._make_df('2024-03-18 09:00', '2024-03-18 09:00')
        result = t._aplicar_filtros_negocio(df)
        assert len(result) == 0

    def test_duracao_acima_6h_removida(self, t):
        df = self._make_df('2024-03-18 08:00', '2024-03-18 15:00')
        result = t._aplicar_filtros_negocio(df)
        assert len(result) == 0

    def test_online_detetado_por_estado(self, t):
        df = pd.DataFrame({
            'datainicio': [pd.Timestamp('2024-03-18 09:00')],
            'datafim':    [pd.Timestamp('2024-03-18 11:00')],
            'espaco':     ['SALA A'],
            'estado':     ['Online'],
        })
        result = t._aplicar_filtros_negocio(df)
        assert result['is_online'].iloc[0] == True

    def test_duplicado_marcado_como_agregado(self, t):
        df = pd.DataFrame({
            'datainicio': [pd.Timestamp('2024-03-18 09:00')] * 2,
            'datafim':    [pd.Timestamp('2024-03-18 11:00')] * 2,
            'espaco':     ['SALA A', 'SALA A'],
        })
        result = t._aplicar_filtros_negocio(df)
        assert result['flag_evento_agregado'].sum() == 1


# _gerar_chaves_temporais

class TestGerarChavesTemporais:

    def test_sk_data(self, t):
        df = pd.DataFrame({
            'datainicio': [pd.Timestamp('2024-03-18 09:30')],
            'datafim':    [pd.Timestamp('2024-03-18 11:00')],
        })
        result = t._gerar_chaves_temporais(df)
        assert result['SK_Data'].iloc[0] == 20240318

    def test_sk_hora_inicio(self, t):
        df = pd.DataFrame({
            'datainicio': [pd.Timestamp('2024-03-18 09:30')],
            'datafim':    [pd.Timestamp('2024-03-18 11:00')],
        })
        result = t._gerar_chaves_temporais(df)
        assert result['SK_Hora_Inicio'].iloc[0] == 930

    def test_sk_hora_fim(self, t):
        df = pd.DataFrame({
            'datainicio': [pd.Timestamp('2024-03-18 09:30')],
            'datafim':    [pd.Timestamp('2024-03-18 11:00')],
        })
        result = t._gerar_chaves_temporais(df)
        assert result['SK_Hora_Fim'].iloc[0] == 1100


# _gerar_id_ocupacao

class TestGerarIdOcupacao:

    def test_usa_identificador_existente(self, t):
        df = pd.DataFrame({
            'identificador':  ['42'],
            'SK_Data':        [20240318],
            'SK_Hora_Inicio': [900],
            'espaco':         ['SALA A'],
        })
        result = t._gerar_id_ocupacao(df)
        assert result['ID_Ocupacao'].iloc[0] == '42'

    def test_gera_composto_sem_identificador(self, t):
        df = pd.DataFrame({
            'SK_Data':        [20240318],
            'SK_Hora_Inicio': [900],
            'espaco':         ['SALA A'],
        })
        result = t._gerar_id_ocupacao(df)
        assert result['ID_Ocupacao'].iloc[0] == '20240318_900_SALA '

    def test_identificador_zero_usa_composto(self, t):
        df = pd.DataFrame({
            'identificador':  [0],
            'SK_Data':        [20240318],
            'SK_Hora_Inicio': [900],
            'espaco':         ['SALA A'],
        })
        result = t._gerar_id_ocupacao(df)
        assert result['ID_Ocupacao'].iloc[0] == '20240318_900_SALA '


# _classificar_epoca

class TestClassificarEpoca:

    def test_janeiro_epoca_sem1(self, t):
        df = pd.DataFrame({'datainicio': [pd.Timestamp('2024-01-15')]})
        result = t._classificar_epoca(df)
        assert result['descricao_epoca'].iloc[0] == 'Época Normal/Recurso (Sem 1)'

    def test_junho_epoca_sem2(self, t):
        df = pd.DataFrame({'datainicio': [pd.Timestamp('2024-06-15')]})
        result = t._classificar_epoca(df)
        assert result['descricao_epoca'].iloc[0] == 'Época Normal/Recurso (Sem 2)'

    def test_agosto_ferias(self, t):
        df = pd.DataFrame({'datainicio': [pd.Timestamp('2024-08-15')]})
        result = t._classificar_epoca(df)
        assert result['descricao_epoca'].iloc[0] == 'Férias'

    def test_outubro_periodo_letivo(self, t):
        df = pd.DataFrame({'datainicio': [pd.Timestamp('2024-10-15')]})
        result = t._classificar_epoca(df)
        assert result['descricao_epoca'].iloc[0] == 'Período Letivo'


# apply_pipeline

class TestApplyPipeline:

    def _make_main_df(self):
        return pd.DataFrame({
            'identificador':  ['1'],
            'edificio':       ['Ed. A (ESTG)'],
            'espaco':         ['LAB DEI 101'],
            'datainicio':     [pd.Timestamp('2024-10-15 09:00')],
            'datafim':        [pd.Timestamp('2024-10-15 11:00')],
            'unidade_respon': ['ESTG'],
            'tipo':           ['TP'],
            'cod_disc':       ['1234'],
            'nome_disci':     ['Programação I'],
            'ciclo':          ['Licenciatura'],
            'descricao':      ['TP1'],
            'estado':         ['Confirmado'],
            'pessoa_resp':    ['Prof. Silva'],
        })

    def test_pipeline_corre_sem_erros(self, t):
        df = self._make_main_df()
        result = t.apply_pipeline(df)
        assert not result.empty

    def test_colunas_schema_presentes(self, t):
        df = self._make_main_df()
        result = t.apply_pipeline(df)
        for col in ['Edificio', 'Nome_Espaco', 'Categoria_Espaco',
                    'SK_Data', 'SK_Hora_Inicio', 'SK_Hora_Fim', 'ID_Ocupacao']:
            assert col in result.columns, f"Coluna em falta: {col}"

    def test_pipeline_sem_coluna_data_lanca_erro(self, t):
        df = pd.DataFrame({'espaco': ['SALA A']})
        with pytest.raises((ValueError, KeyError)):
            t.apply_pipeline(df)

    def test_outlier_removido(self, t):
        df = self._make_main_df()
        outlier = df.copy()
        outlier['datafim'] = pd.Timestamp('2024-10-15 17:00')
        df_combined = pd.concat([df, outlier], ignore_index=True)
        result = t.apply_pipeline(df_combined)
        assert len(result) == 1

    def test_edificio_normalizado(self, t):
        df = self._make_main_df()
        result = t.apply_pipeline(df)
        assert '(ESTG)' not in result['Edificio'].iloc[0]

    def test_categoria_espaco_laboratorio(self, t):
        df = self._make_main_df()
        result = t.apply_pipeline(df)
        assert result['Categoria_Espaco'].iloc[0] == 'Laboratorio'