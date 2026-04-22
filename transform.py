import pandas as pd
import logging
import re
import numpy as np

class DataTransformer:
    """
    Camada de Transformação do Pipeline ETL.
    Implementa as regras de higienização, normalização e imputação inteligente 
    necessárias para a integridade do Modelo Dimensional.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # -----------------------------------------------------------------
    # 1. NORMALIZAÇÃO DE STRINGS E PLACEHOLDERS
    # -----------------------------------------------------------------
    def clean_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza o casing e remove espaços redundantes em colunas descritivas."""
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
            
            # Normalização para UPPERCASE em dimensões de localização (requisito do Mapa Lógico)
            target_loc = ['edificio', 'desig_edf', 'espaco', 'nome_espaco', 'unidade_respon', 'unidade_responsavel']
            if col in target_loc:
                df[col] = df[col].str.upper()
            
            # Padronização de nulos semânticos
            df[col] = df[col].replace({'nan': pd.NA, '<NA>': pd.NA, '': pd.NA, 'None': pd.NA})
        return df

    # -----------------------------------------------------------------
    # 2. TRATAMENTO DE RESPONSÁVEIS E UNIDADES
    # -----------------------------------------------------------------
    def impute_responsavel(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Garante que colunas de responsabilidade possuam valores válidos para FKs.
        Nota: A EDA revelou ~77% de nulidade nestes campos na fonte original.
        """
        cols = ['pessoa_resp', 'unidade_respon', 'unidade_responsavel']
        for col in cols:
            if col in df.columns:
                df[col] = df[col].fillna('Indefinido/N.D.')
        return df

    # -----------------------------------------------------------------
    # 3. GESTÃO DE DADOS ACADÉMICOS (RESERVAS ADMIN)
    # -----------------------------------------------------------------
    def enforce_academic_dummy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Trata registos que não possuem vínculo direto a uma Unidade Curricular.
        Imputa placeholders para evitar 'Unknowns' genéricos no dashboard de BI.
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
    # 4. LIMPEZA DE NOMENCLATURA DE EDIFÍCIOS
    # -----------------------------------------------------------------
    def normalize_edificios(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remoção de sufixos redundantes via Regex.
        Ex: 'EDIFÍCIO A (ESTG)' -> 'EDIFÍCIO A'
        """
        for col in ['edificio', 'desig_edf']:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(
                    lambda x: re.sub(r'\s*\(.*?\)', '', x).strip() if x != '<NA>' else x
                )
                df[col] = df[col].replace({'<NA>': pd.NA, 'nan': pd.NA})
        return df

    # -----------------------------------------------------------------
    # 5. LÓGICA DE NEGÓCIO: ONLINE, FILTROS E SOBREPOSIÇÕES
    # -----------------------------------------------------------------
    def add_online_flag_and_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        - RF05: Isola ocupação virtual através da flag 'is_online'.
        - Limpeza Temporal: Remove durações absurdas (outliers > 6h ou <= 0).
        - Audit: Calcula 'flag_evento_agregado' para identificar partilha de espaços.
        """
        df['is_online'] = False

        # Deteção de sessões virtuais por estado ou localização
        online_terms = 'Online|Ensino a Distância|Virtual|Zoom|Colibri'
        
        if 'estado' in df.columns:
            df.loc[df['estado'].astype(str).str.contains(online_terms, case=False, na=False), 'is_online'] = True

        for ecol in ['edificio', 'desig_edf']:
            if ecol in df.columns:
                df.loc[df[ecol].astype(str).str.contains(online_terms, case=False, na=False), 'is_online'] = True

        # Conversão Temporal e Cálculo de Duração
        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        col_f = next((c for c in ['data_fim', 'datafim'] if c in df.columns), None)

        if col_i and col_f:
            df[col_i] = pd.to_datetime(df[col_i], errors='coerce')
            df[col_f] = pd.to_datetime(df[col_f], errors='coerce')
            
            # Remoção de datas corrompidas (Essential for Time Dimension FK)
            df = df.dropna(subset=[col_i, col_f]).copy()

            df['duracao_minutos'] = (df[col_f] - df[col_i]).dt.total_seconds() / 60

            # Filtro de sanidade (Business Rule: Aulas entre 1 e 360 minutos)
            df = df[(df['duracao_minutos'] > 0) & (df['duracao_minutos'] <= 360)].copy()

            # Identificação de Eventos Agregados (Mesmo Espaço/Hora, UCs diferentes)
            esp_c = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
            if esp_c:
                df = df.sort_values(by=[col_i, esp_c])
                df['flag_evento_agregado'] = df.duplicated(subset=[col_i, esp_c], keep='first')
        
        return df

    # -----------------------------------------------------------------
    # 6. PARSING DE TURNOS E UCs
    # -----------------------------------------------------------------
    def clean_turnos(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extração de códigos de turno (T1, TP2, etc.) de campos de descrição."""
        desc_col = next((c for c in ['descricao_com_indicacao_turno', 'descricao'] if c in df.columns), None)
        if desc_col:
            df['turno_extraido'] = df[desc_col].astype(str).str.extract(
                r'\b(TP\d*|T\d+|P\d+|PL\d+|S\d+|OT\d+)\b', expand=False
            ).fillna('N/D')
        return df

    def extract_uc_code(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extrai o código numérico da UC quando embutido no nome: 'Nome (Código)'."""
        if 'unidade_curricular' in df.columns:
            df['uc_code_extracted'] = df['unidade_curricular'].astype(str).str.extract(
                r'\(([^)]+)\)\s*$', expand=False
            ).fillna('N/D').str.strip()
        return df

    # -----------------------------------------------------------------
    # 7. MAPEAMENTO FINAL E AUDITORIA DE NULOS
    # -----------------------------------------------------------------
    def final_null_sweep(self, df: pd.DataFrame) -> pd.DataFrame:
        """Última barreira de sanitização para garantir zero nulos antes do carregamento."""
        impute_map = {
            'edificio': 'Edifício Desconhecido', 'espaco': 'Espaço Desconhecido',
            'tipo': 'N/D', 'estado': 'N/D', 'turno_extraido': 'N/D',
            'ciclo_estudo': 'N/D', 'codigo_unidade_curricular': 'SEM_UNIDADE / RESERVA_ADMIN',
            'unidade_responsavel': 'Indefinido/N.D.', 'pessoa_resp': 'Indefinido/N.D.'
        }
        for col, default in impute_map.items():
            if col in df.columns:
                df[col] = df[col].fillna(default).replace({'nan': default, '<NA>': default, '': default})
        return df

    def apply_pipeline(self, df: pd.DataFrame) -> pd.DataFrame:
        """Orquestração sequencial de todas as transformações."""
        self.logger.info("A iniciar Transformação Dimensional...")
        
        df = self.clean_strings(df)
        df = self.impute_responsavel(df)
        df = self.enforce_academic_dummy(df)
        df = self.normalize_edificios(df)
        df = self.clean_turnos(df)
        df = self.extract_uc_code(df)
        df = self.add_online_flag_and_filters(df)
        df = self.final_null_sweep(df)

        self.logger.info(f"Transformação Completa. Volume final: {len(df):,} registos.")
        return df