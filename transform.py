import pandas as pd
import logging
import re
import numpy as np


class DataTransformer:
    """
    Camada de Transformação do Pipeline ETL.
    Implementa as regras de higienização, normalização e imputação
    definidas no mapa_logico_dados.xlsx e no relatorio_projeto_ESTG.pdf.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # =================================================================
    # 1. DIMENSÃO DATA (Geração Autónoma)
    # =================================================================
    def build_date_dimension(self, start_date='2018-01-01', end_date='2035-12-31') -> pd.DataFrame:
        """Gera o DataFrame completo para a Dim_Data com todos os atributos do schema."""
        self.logger.info(f"A gerar Dim_Data ({start_date} a {end_date})...")
        date_range = pd.date_range(start=start_date, end=end_date)
        df = pd.DataFrame({'DataCompleta': date_range})

        df['SK_Data'] = df['DataCompleta'].dt.strftime('%Y%m%d').astype(int)
        df['DataCompleta'] = df['DataCompleta'].dt.date
        df['Ano'] = pd.to_datetime(df['DataCompleta']).dt.year
        df['Mes'] = pd.to_datetime(df['DataCompleta']).dt.month
        df['Dia'] = pd.to_datetime(df['DataCompleta']).dt.day
        df['Numero_Semana'] = pd.to_datetime(df['DataCompleta']).dt.isocalendar().week.astype(int)

        # Ano letivo: começa em setembro
        df['Ano_Letivo'] = df.apply(
            lambda r: f"{r['Ano']}/{r['Ano']+1}" if r['Mes'] >= 9 else f"{r['Ano']-1}/{r['Ano']}", axis=1
        )

        # Semestre: 1 (Set-Fev), 2 (Mar-Jul), 0 (Ago)
        df['Semestre'] = df['Mes'].apply(
            lambda m: 1 if m in [9,10,11,12,1,2] else (2 if m in [3,4,5,6,7] else 0)
        )

        # Dia da Semana em Português
        day_map = {0:'Segunda-feira',1:'Terça-feira',2:'Quarta-feira',
                   3:'Quinta-feira',4:'Sexta-feira',5:'Sábado',6:'Domingo'}
        df['DiaSemana'] = pd.to_datetime(df['DataCompleta']).dt.dayofweek.map(day_map)

        # Época de Exame
        def get_epoca(m):
            if m in [1,2]: return 'Época Normal/Recurso (Sem 1)'
            if m in [6,7]: return 'Época Normal/Recurso (Sem 2)'
            if m == 8: return 'Férias'
            return 'Período Letivo'
        df['Epoca_Exame'] = df['Mes'].apply(get_epoca)

        # Tipo de Dia
        def get_tipo_dia(row):
            if row['DiaSemana'] in ['Sábado','Domingo']: return 'Fim de Semana'
            if row['Mes'] == 8: return 'Férias'
            return 'Dia Útil/Letivo'
        df['Tipo_Dia'] = df.apply(get_tipo_dia, axis=1)

        self.logger.info(f"Dim_Data gerada: {len(df):,} registos.")
        return df

    # =================================================================
    # 2. LIMPEZA DE STRINGS E PLACEHOLDERS
    # =================================================================
    def _clean_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza casing e remove espaços redundantes em colunas texto."""
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
            # Uppercase para campos de localização conforme Mapa Lógico
            if col in ['edificio','desig_edf','espaco','nome_espaco','unidade_respon','unidade_responsavel']:
                df[col] = df[col].str.upper()
            df[col] = df[col].replace({'nan': pd.NA, '<NA>': pd.NA, '': pd.NA, 'None': pd.NA})
        return df

    # =================================================================
    # 3. IMPUTAÇÃO DE RESPONSÁVEIS
    # =================================================================
    def _impute_responsavel(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preenche colunas de responsabilidade com valor padrão."""
        for col in ['pessoa_resp','unidade_respon','unidade_responsavel']:
            if col in df.columns:
                df[col] = df[col].fillna('Indefinido/N.D.')
        return df

    # =================================================================
    # 4. TRATAMENTO DE REGISTOS SEM UC (Reservas Administrativas)
    # =================================================================
    def _enforce_academic_dummy(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preenche campos académicos vazios com placeholder para Dim_UC."""
        academic_cols = [
            'cod_disc','codigo_unidade_curricular',
            'nome_disci','designacao_unidade_curricular',
            'ciclo','ciclo_estudo',
        ]
        for col in academic_cols:
            if col in df.columns:
                df[col] = df[col].fillna('SEM_UNIDADE / RESERVA_ADMIN')
        return df

    # =================================================================
    # 5. NORMALIZAÇÃO DE EDIFÍCIOS (Remoção de sufixos redundantes)
    # =================================================================
    def _normalize_edificios(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove sufixos em parênteses de nomes de edifícios (e.g. 'EDIFÍCIO A (ESTG)' → 'EDIFÍCIO A')."""
        for col in ['edificio','desig_edf']:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).apply(
                    lambda x: re.sub(r'\s*\(.*?\)', '', x).strip() if x and x not in ('<NA>','nan','') else x
                )
                df[col] = df[col].replace({'<NA>': pd.NA, 'nan': pd.NA, '': pd.NA})
        return df

    # =================================================================
    # 6. EXTRAÇÃO DE TURNOS (Regex)
    # =================================================================
    def _extract_turno(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extrai código de turno do campo de descrição."""
        desc_col = next((c for c in ['descricao_com_indicacao_turno','descricao'] if c in df.columns), None)
        if desc_col:
            df['turno_extraido'] = df[desc_col].astype(str).str.extract(
                r'\b(TP\d*|T\d+|P\d+|PL\d+|S\d+|OT\d+)\b', expand=False
            ).fillna('N/D')
        return df

    # =================================================================
    # 7. FLAG ONLINE, DURAÇÃO, FILTROS DE OUTLIERS
    # =================================================================
    def _apply_business_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula is_online, duracao_minutos, filtra outliers (0 < dur ≤ 360)."""
        df['is_online'] = False
        online_re = 'Online|Ensino a Distância|Virtual|Zoom'

        if 'estado' in df.columns:
            df.loc[df['estado'].astype(str).str.contains(online_re, case=False, na=False), 'is_online'] = True
        for ecol in ['edificio','desig_edf']:
            if ecol in df.columns:
                df.loc[df[ecol].astype(str).str.contains(online_re, case=False, na=False), 'is_online'] = True

        col_i = next((c for c in ['data_inicio','datainicio'] if c in df.columns), None)
        col_f = next((c for c in ['data_fim','datafim'] if c in df.columns), None)

        if col_i and col_f:
            df[col_i] = pd.to_datetime(df[col_i], errors='coerce')
            df[col_f] = pd.to_datetime(df[col_f], errors='coerce')
            df = df.dropna(subset=[col_i, col_f]).copy()
            df['duracao_minutos'] = (df[col_f] - df[col_i]).dt.total_seconds() / 60
            # Filtro de outliers: duração > 0 e ≤ 360 minutos (6h)
            df = df[(df['duracao_minutos'] > 0) & (df['duracao_minutos'] <= 360)].copy()
            # Flag de sobreposição
            esp_c = next((c for c in ['espaco','nome_espaco'] if c in df.columns), None)
            if esp_c:
                df = df.sort_values(by=[col_i, esp_c])
                df['flag_evento_agregado'] = df.duplicated(subset=[col_i, esp_c], keep='first')

        return df

    # =================================================================
    # 8. CHAVES TEMPORAIS (SK_Data, SK_Hora_Inicio, SK_Hora_Fim)
    # =================================================================
    def _generate_temporal_keys(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gera as Surrogate Keys temporais para ligação a Dim_Data e Dim_Hora."""
        col_i = next((c for c in ['data_inicio','datainicio'] if c in df.columns), None)
        col_f = next((c for c in ['data_fim','datafim'] if c in df.columns), None)
        if col_i and col_f:
            df['SK_Data'] = df[col_i].dt.strftime('%Y%m%d').astype(int)
            df['SK_Hora_Inicio'] = (df[col_i].dt.hour * 100 + df[col_i].dt.minute).astype(int)
            df['SK_Hora_Fim'] = (df[col_f].dt.hour * 100 + df[col_f].dt.minute).astype(int)
        return df

    # =================================================================
    # 9. GERAÇÃO DE ID_OCUPACAO (PK da Facto)
    # =================================================================
    def _generate_ocupacao_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gera a chave primária da tabela de factos a partir do identificador fonte."""
        if 'identificador' in df.columns:
            df['ID_Ocupacao'] = pd.to_numeric(df['identificador'], errors='coerce').fillna(0).astype(int).astype(str)
            mask_zero = df['ID_Ocupacao'] == '0'
            if mask_zero.any():
                df.loc[mask_zero, 'ID_Ocupacao'] = (
                    df['SK_Data'].astype(str) + "_" +
                    df['SK_Hora_Inicio'].astype(str) + "_" +
                    df['espaco'].astype(str).str[:5]
                )
        else:
            df['ID_Ocupacao'] = (
                df['SK_Data'].astype(str) + "_" +
                df['SK_Hora_Inicio'].astype(str) + "_" +
                df.get('espaco', pd.Series(['UNK']*len(df))).astype(str).str[:5]
            )
        return df

    # =================================================================
    # 10. MERGE COM SQL STAGING (Enriquecimento de Responsáveis)
    # =================================================================
    def _merge_hybrid_stg(self, df_main: pd.DataFrame, df_stg: pd.DataFrame) -> pd.DataFrame:
        """Cruza CSV transacional com dump SQL para preencher pessoa_resp e unidade_respon."""
        self.logger.info("A iniciar Merge Híbrido com Metadados SQL...")
        df_stg_e = df_stg[['id','unidade_respon','pessoa_resp']].copy()
        df_main['identificador'] = pd.to_numeric(df_main['identificador'], errors='coerce')
        df_stg_e['id'] = pd.to_numeric(df_stg_e['id'], errors='coerce')
        df_stg_e = df_stg_e.drop_duplicates(subset=['id'], keep='first')

        pre_len = len(df_main)
        df_m = pd.merge(df_main, df_stg_e, left_on='identificador', right_on='id', how='left', suffixes=('','_sql'))

        if 'unidade_respon_sql' in df_m.columns:
            df_m['unidade_respon'] = df_m['unidade_respon_sql'].fillna(df_m.get('unidade_respon'))
        if 'pessoa_resp_sql' in df_m.columns:
            df_m['pessoa_resp'] = df_m['pessoa_resp_sql'].fillna(df_m.get('pessoa_resp'))
        df_m.drop(columns=['id','unidade_respon_sql','pessoa_resp_sql'], inplace=True, errors='ignore')

        if len(df_m) != pre_len:
            self.logger.warning(f"ALERTA: Merge STG alterou volumetria: {pre_len:,} -> {len(df_m):,}")
        return df_m

    # =================================================================
    # 11. MERGE DE PRESENÇAS (Chave Semântica)
    # =================================================================
    def _merge_attendance(self, df_main: pd.DataFrame, df_pres_raw: pd.DataFrame) -> pd.DataFrame:
        """Cruza agendamentos com presenças via chave semântica: Data + UC (UPPER) + Turno."""
        self.logger.info("A processar Presenças via Chave Semântica...")
        df_p = df_pres_raw.copy()

        # Preparar fonte de presenças
        if 'unidade_curricular' in df_p.columns:
            df_p['_mk_uc'] = df_p['unidade_curricular'].astype(str).apply(
                lambda x: re.sub(r'\s*\([^)]*\)\s*$', '', x).strip()
            ).str.upper()
        if 'data_inicio' in df_p.columns:
            df_p['_mk_date'] = pd.to_datetime(df_p['data_inicio'], errors='coerce').dt.date
        if 'turno' in df_p.columns:
            df_p['_mk_turno'] = df_p['turno'].astype(str).str.strip()

        # Garantir tipo numérico
        df_p['presencas'] = pd.to_numeric(df_p.get('presencas', 0), errors='coerce').fillna(0).astype(int)

        pres_agg = df_p.groupby(['_mk_date','_mk_uc','_mk_turno'], dropna=False).agg(
            {'presencas': 'sum'}
        ).reset_index()

        # Preparar target
        col_i = next((c for c in ['data_inicio','datainicio'] if c in df_main.columns), None)
        uc_col = next((c for c in ['designacao_unidade_curricular','nome_disci'] if c in df_main.columns), None)
        turno_col = 'turno_extraido' if 'turno_extraido' in df_main.columns else 'turno'

        df_main['_mk_date'] = pd.to_datetime(df_main[col_i], errors='coerce').dt.date if col_i else None
        df_main['_mk_uc'] = df_main[uc_col].astype(str).str.strip().str.upper() if uc_col else ''
        df_main['_mk_turno'] = df_main.get(turno_col, pd.Series([''] * len(df_main))).astype(str).str.strip()

        pre_len = len(df_main)
        df_merged = pd.merge(df_main, pres_agg, on=['_mk_date','_mk_uc','_mk_turno'], how='left', suffixes=('','_fp'))

        if 'presencas_fp' in df_merged.columns:
            df_merged['presencas'] = df_merged['presencas_fp'].fillna(df_merged.get('presencas', 0)).fillna(0).astype(int)
            df_merged.drop(columns=['presencas_fp'], inplace=True, errors='ignore')
        elif 'presencas' not in df_merged.columns:
            df_merged['presencas'] = 0

        df_merged.drop(columns=['_mk_date','_mk_uc','_mk_turno'], inplace=True, errors='ignore')

        matched = (df_merged['presencas'] > 0).sum()
        self.logger.info(f"Presenças cruzadas: {matched:,}/{len(df_merged):,}")

        # Proteção contra produto cartesiano
        if len(df_merged) != pre_len:
            self.logger.warning(f"CORREÇÃO: Removendo duplicados do merge ({len(df_merged):,} linhas).")
            dup_cols = [c for c in [col_i,'espaco','codigo_unidade_curricular','turno_extraido'] if c in df_merged.columns]
            if dup_cols:
                df_merged = df_merged.sort_values('presencas', ascending=False).drop_duplicates(subset=dup_cols, keep='first')

        return df_merged

    # =================================================================
    # 12. PROCESSAMENTO DE CURSOS (Reference Data)
    # =================================================================
    def _process_courses(self, df_cursos: pd.DataFrame) -> pd.DataFrame:
        """Limpa o dicionário de cursos, extraindo codigo_uc limpo."""
        df_c = df_cursos.copy()
        # Normalizar colunas que podem ter nomes com acentos estranhos
        col_map = {c: c.lower().strip() for c in df_c.columns}
        df_c = df_c.rename(columns=col_map)

        # Garantir que todas as colunas-chave são strings limpas
        for col in ['codigo_curso', 'codigo_uc']:
            if col in df_c.columns:
                df_c[col] = df_c[col].fillna('').astype(str).str.strip()
                df_c[col] = df_c[col].replace({'nan': '', 'None': '', '<NA>': ''})

        # Filtrar linhas com códigos vazios
        df_c = df_c[df_c['codigo_curso'].str.len() > 0].copy()
        df_c = df_c[df_c['codigo_uc'].str.len() > 0].copy()

        # Extrair código da UC sem o prefixo do curso
        df_c['codigo_uc_limpo'] = df_c.apply(
            lambda x: x['codigo_uc'][len(x['codigo_curso']):]
            if x['codigo_uc'].startswith(x['codigo_curso']) else x['codigo_uc'], axis=1
        )
        df_c['codigo_uc_limpo'] = df_c['codigo_uc_limpo'].str.lstrip('0')

        # Normalizar nome_curso / designacao_curso
        nome_col = next((c for c in ['nome_curso','designacao_curso'] if c in df_c.columns), None)
        if nome_col and nome_col != 'nome_curso':
            df_c = df_c.rename(columns={nome_col: 'nome_curso'})

        return df_c

    def _merge_course_data(self, df_main: pd.DataFrame, df_cursos: pd.DataFrame) -> pd.DataFrame:
        """Enriquece dados com nomes de cursos via merge no código da UC."""
        df_cursos_clean = self._process_courses(df_cursos)
        uc_col = 'cod_disc' if 'cod_disc' in df_main.columns else 'codigo_unidade_curricular'
        df_enriched = pd.merge(
            df_main,
            df_cursos_clean[['codigo_uc_limpo','nome_curso','codigo_curso']].drop_duplicates('codigo_uc_limpo'),
            left_on=uc_col, right_on='codigo_uc_limpo', how='left'
        )
        return df_enriched

    # =================================================================
    # 13. MAPEAMENTO FINAL PARA SCHEMA DW (PascalCase)
    # =================================================================
    def _align_to_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Renomeia colunas do DataFrame para os nomes exactos do schema_dw.sql.
        Realiza a auditoria final de nulos.
        """
        # Imputação final
        impute_map = {
            'edificio': 'Edifício Desconhecido', 'espaco': 'Espaço Desconhecido',
            'tipo': 'N/D', 'estado': 'N/D', 'turno_extraido': 'N/D',
            'ciclo_estudo': 'N/D', 'codigo_unidade_curricular': 'SEM_UNIDADE / RESERVA_ADMIN',
            'designacao_unidade_curricular': 'SEM_UNIDADE / RESERVA_ADMIN',
            'unidade_responsavel': 'Indefinido/N.D.', 'pessoa_resp': 'Indefinido/N.D.',
            'nome_curso': 'N/D', 'codigo_curso': 'N/D',
        }
        for col, default in impute_map.items():
            if col in df.columns:
                df[col] = df[col].fillna(default).replace({'nan': default, '<NA>': default, '': default})

        # Garantir que Codigo_UC é string limpa (anti float-poisoning)
        uc_code_col = next((c for c in ['codigo_unidade_curricular','cod_disc'] if c in df.columns), None)
        if uc_code_col:
            df[uc_code_col] = (
                df[uc_code_col].astype(str)
                .str.replace(r'\.0$', '', regex=True)
                .str.strip()
            )

        # Conversão de booleanos para int (MySQL compatível) — Bug 2: evita mismatch True/False vs 0/1
        if 'is_online' in df.columns:
            df['is_online'] = df['is_online'].astype(int)
        if 'flag_evento_agregado' in df.columns:
            df['flag_evento_agregado'] = df['flag_evento_agregado'].astype(int)

        # Imputação de métricas numéricas (garantir zero nulos)
        for num_col in ['presencas', 'duracao_minutos']:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors='coerce').fillna(0).astype(int)

        # Renomeação final para PascalCase (schema_dw.sql)
        rename_map = {
            'edificio': 'Edificio',
            'espaco': 'Nome_Espaco',
            'tipo': 'Designacao_Atividade',
            'estado': 'Estado',
            'turno_extraido': 'Designacao_Turno',
            'ciclo_estudo': 'Ciclo_Estudo',
            'unidade_responsavel': 'Unidade_Responsavel',
            'pessoa_resp': 'Nome_Responsavel',
            'duracao_minutos': 'Duracao_Minutos',
            'flag_evento_agregado': 'Flag_Evento_Agregado',
            'presencas': 'Numero_Presencas',
            'is_online': 'is_online',
        }
        # Codigo_UC e Designacao_UC
        if 'codigo_unidade_curricular' in df.columns:
            rename_map['codigo_unidade_curricular'] = 'Codigo_UC'
        elif 'cod_disc' in df.columns:
            rename_map['cod_disc'] = 'Codigo_UC'
        if 'designacao_unidade_curricular' in df.columns:
            rename_map['designacao_unidade_curricular'] = 'Designacao_UC'
        elif 'nome_disci' in df.columns:
            rename_map['nome_disci'] = 'Designacao_UC'
        # Curso
        if 'nome_curso' in df.columns:
            rename_map['nome_curso'] = 'Nome_Curso'
        if 'codigo_curso' in df.columns:
            rename_map['codigo_curso'] = 'Codigo_Curso'

        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        return df

    # =================================================================
    # ORQUESTRAÇÃO PRINCIPAL
    # =================================================================
    def apply_pipeline(self, df_main: pd.DataFrame, df_cursos: pd.DataFrame = None,
                       df_presencas: pd.DataFrame = None, df_stg: pd.DataFrame = None) -> pd.DataFrame:
        """Orquestração sequencial de todas as transformações da Fact Table."""
        self.logger.info("═" * 60)
        self.logger.info("A iniciar Transformação Dimensional...")

        # 1. Enriquecimento via SQL Staging
        if df_stg is not None:
            df_main = self._merge_hybrid_stg(df_main, df_stg)

        # 2. Limpezas Estruturais
        df_main = self._clean_strings(df_main)
        df_main = self._impute_responsavel(df_main)
        df_main = self._enforce_academic_dummy(df_main)
        df_main = self._normalize_edificios(df_main)
        df_main = self._extract_turno(df_main)

        # 3. Regras de Negócio (Online, Duração, Outliers)
        df_main = self._apply_business_filters(df_main)

        # 4. Integração do Dicionário de Cursos
        if df_cursos is not None:
            df_main = self._merge_course_data(df_main, df_cursos)

        # 5. Integração de Presenças (Chave Semântica)
        if df_presencas is not None:
            df_main = self._merge_attendance(df_main, df_presencas)

        # 6. Chaves Temporais e ID_Ocupacao
        df_main = self._generate_temporal_keys(df_main)
        df_main = self._generate_ocupacao_id(df_main)

        # 7. Alinhamento Final com Schema DW
        df_main = self._align_to_schema(df_main)

        self.logger.info(f"Transformação Completa. Volume final: {len(df_main):,} registos.")
        self.logger.info("═" * 60)
        return df_main