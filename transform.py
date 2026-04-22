import pandas as pd
import logging
import re
import numpy as np

class DataTransformer:
    """
    Camada de Transformação do Pipeline ETL.
    Aplica regras de negócio, limpeza e imputação inteligente conforme
    o Mapa Lógico de Dados e o Relatório Incremental.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # -----------------------------------------------------------------
    # 1. LIMPEZA DE STRINGS
    # -----------------------------------------------------------------
    def clean_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace e normaliza placeholders em todas as colunas texto."""
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
            # Upper case specifically on target columns according to Logical Map
            if col in ['edificio', 'desig_edf', 'espaco', 'nome_espaco', 'unidade_respon', 'unidade_responsavel']:
                df[col] = df[col].str.upper()
            df[col] = df[col].replace({'nan': pd.NA, '<NA>': pd.NA, '': pd.NA, 'None': pd.NA})
        return df

    # -----------------------------------------------------------------
    # 2. IMPUTAÇÃO DE RESPONSÁVEL
    # -----------------------------------------------------------------
    def impute_responsavel(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Substitui nulos no responsável por 'Indefinido/N.D.'
        Regra: 77% de nulls confirmados na EDA — imprescindível para FK.
        """
        for col in ['pessoa_resp', 'unidade_respon', 'unidade_responsavel']:
            if col in df.columns:
                df[col] = df[col].fillna('Indefinido/N.D.')
        return df

    # -----------------------------------------------------------------
    # 3. IMPUTAÇÃO ACADÉMICA (RESERVAS SEM UC)
    # -----------------------------------------------------------------
    def enforce_academic_dummy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Registos do tipo 'Reserva' não têm atributos académicos.
        Imputa com 'SEM_UNIDADE / RESERVA_ADMIN' para manter coerência dimensional.
        """
        academic_cols = [
            'cod_disc', 'codigo_unidade_curricular',
            'nome_disci', 'designacao_unidade_curricular',
            'ciclo', 'ciclo_estudo',
        ]
        for col in academic_cols:
            if col in df.columns:
                df[col] = df[col].fillna('SEM_UNIDADE / RESERVA_ADMIN')
        return df

    # -----------------------------------------------------------------
    # 4. NORMALIZAÇÃO DE EDIFÍCIOS
    # -----------------------------------------------------------------
    def normalize_edificios(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove parênteses redundantes dos edifícios.
        Ex: 'Edifício A (ESTG)' → 'Edifício A'
        """
        for col in ['edificio', 'desig_edf']:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(
                    lambda x: re.sub(r'\s*\(.*?\)', '', x).strip() if x != '<NA>' else x
                )
                df[col] = df[col].replace({'<NA>': pd.NA, 'nan': pd.NA})
        return df

    # -----------------------------------------------------------------
    # 5. FLAG ONLINE + TEMPORAL FILTERS + DURACAO
    # -----------------------------------------------------------------
    def add_online_flag_and_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        - is_online: True se edificio contém 'Ensino a Distância' ou 'Online'
        - Filtra datas inválidas e durações fora de [1, 360] minutos
        - Calcula flag_evento_agregado (overlaps no mesmo espaço)
        """
        df['is_online'] = False

        # Detetar online por estado
        if 'estado' in df.columns:
            mask = df['estado'].astype(str).str.contains(
                'Online|Ensino a Distância', case=False, na=False)
            df.loc[mask, 'is_online'] = True

        # Detetar online por edifício (ex: "Ensino a Distância / Zoom")
        for ecol in ['edificio', 'desig_edf']:
            if ecol in df.columns:
                mask = df[ecol].astype(str).str.contains(
                    'Ensino a Distância|Online|Virtual|Zoom', case=False, na=False)
                df.loc[mask, 'is_online'] = True

        # Encontrar colunas de data
        col_inicio = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        col_fim = next((c for c in ['data_fim', 'datafim'] if c in df.columns), None)

        if col_inicio and col_fim:
            df[col_inicio] = pd.to_datetime(df[col_inicio], errors='coerce')
            df[col_fim] = pd.to_datetime(df[col_fim], errors='coerce')

            before = len(df)
            df = df.dropna(subset=[col_inicio, col_fim]).copy()
            dropped = before - len(df)
            if dropped > 0:
                self.logger.info(f"  Removidas {dropped} linhas com datas invalidas.")

            df['duracao_minutos'] = (df[col_fim] - df[col_inicio]).dt.total_seconds() / 60

            before = len(df)
            validos = (df['duracao_minutos'] > 0) & (df['duracao_minutos'] <= 360)
            df = df[validos].copy()
            dropped = before - len(df)
            if dropped > 0:
                self.logger.info(f"  Removidas {dropped} linhas com duracao fora [1, 360] min.")

            # Flag_Evento_Agregado: overlaps no mesmo espaço e hora
            espaco_col = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
            if espaco_col:
                df = df.sort_values(by=[col_inicio, espaco_col])
                df['flag_evento_agregado'] = df.duplicated(
                    subset=[col_inicio, espaco_col], keep='first')
            else:
                df['flag_evento_agregado'] = False
        else:
            self.logger.warning("Campos de Data Inicio/Fim nao encontrados.")
            df['duracao_minutos'] = 0
            df['flag_evento_agregado'] = False

        return df

    # -----------------------------------------------------------------
    # 6. EXTRAÇÃO DE TURNO
    # -----------------------------------------------------------------
    def clean_turnos(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extrai designações de turno da coluna descricao_com_indicacao_turno.
        Padrões: TP1, T1, P1, PL1, S1, OT1, etc.
        """
        desc_col = next((c for c in ['descricao_com_indicacao_turno', 'descricao']
                         if c in df.columns), None)

        if desc_col:
            df['turno_extraido'] = df[desc_col].astype(str).str.extract(
                r'\b(TP\d*|T\d+|P\d+|PL\d+|S\d+|OT\d+)\b', expand=False
            ).fillna('N/D')
        else:
            df['turno_extraido'] = 'N/D'
        return df

    # -----------------------------------------------------------------
    # 7. RESOLUÇÃO DE PRESENÇAS
    # -----------------------------------------------------------------
    def resolve_attendance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Converte presenças para int, zeros onde nulo."""
        for col in ['presencas', 'numero_presencas']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df

    # -----------------------------------------------------------------
    # 8. EXTRAÇÃO DE CÓDIGO UC DO CAMPO COMPOSTO
    # -----------------------------------------------------------------
    def extract_uc_code(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        PorTurnoPresencas contém 'unidade_curricular' no formato:
        'Marketing Público e Social (20558)' — extrai o código entre parênteses.
        """
        if 'unidade_curricular' in df.columns:
            df['uc_code_extracted'] = df['unidade_curricular'].astype(str).str.extract(
                r'\(([^)]+)\)\s*$', expand=False
            ).fillna('N/D').str.strip()
        return df

    # -----------------------------------------------------------------
    # 9. IMPUTAÇÃO FINAL UNIVERSAL
    # -----------------------------------------------------------------
    def final_null_sweep(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Passagem final: garante zero nulos em colunas críticas para dimensões.
        Decisão técnica: imputa N/D em vez de eliminar registos,
        porque dados parciais ainda têm valor analítico para o BI.
        """
        impute_map = {
            'edificio': 'Edificio Desconhecido',
            'espaco': 'Espaco Desconhecido',
            'tipo': 'N/D',
            'estado': 'N/D',
            'turno_extraido': 'N/D',
            'ciclo_estudo': 'N/D',
            'codigo_unidade_curricular': 'SEM_UNIDADE / RESERVA_ADMIN',
            'designacao_unidade_curricular': 'SEM_UNIDADE / RESERVA_ADMIN',
            'unidade_responsavel': 'Indefinido/N.D.',
            'unidade_respon': 'Indefinido/N.D.',
            'pessoa_resp': 'Indefinido/N.D.',
        }
        for col, default in impute_map.items():
            if col in df.columns:
                df[col] = df[col].fillna(default)
                # Also catch string 'nan' / '<NA>' leftovers
                df[col] = df[col].replace({'nan': default, '<NA>': default, '': default})
        return df

    # -----------------------------------------------------------------
    # PIPELINE MASTER
    # -----------------------------------------------------------------
    def apply_pipeline(self, df: pd.DataFrame) -> pd.DataFrame:
        """Orquestra as limpezas sequenciais."""
        original_len = len(df)
        self.logger.info("A iniciar Transformacoes [STATUS: Em Processamento]")

        df = self.clean_strings(df)
        df = self.impute_responsavel(df)
        df = self.enforce_academic_dummy(df)
        df = self.normalize_edificios(df)
        df = self.clean_turnos(df)
        df = self.extract_uc_code(df)
        df = self.add_online_flag_and_filters(df)  # pode eliminar linhas
        df = self.resolve_attendance(df)
        df = self.final_null_sweep(df)

        final_len = len(df)
        removidos = original_len - final_len
        self.logger.info(f"Transformacao Completa: {removidos:,} outliers removidos.")
        self.logger.info(f"Dimensao Resultante: {final_len:,} registos.")

        # Report null residuals
        null_cols = df.isnull().sum()
        residual = null_cols[null_cols > 0]
        if len(residual) > 0:
            self.logger.warning(f"  Nulos residuais: {residual.to_dict()}")
        else:
            self.logger.info("  Zero nulos residuais em todo o DataFrame.")

        return df
