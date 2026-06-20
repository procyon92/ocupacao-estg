import pandas as pd
import logging
import re
import numpy as np


class DataTransformer:
    """
    Camada de Transformação do Pipeline ETL.
    Implementa as regras de higienização, normalização e imputação.
    Refatorado para alinhamento estrito com schema_dw.sql e separação de responsabilidades.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # =================================================================
    # 1. GERAÇÃO AUTÓNOMA DE DIMENSÕES ESTÁTICAS
    # =================================================================

    def _get_semester_start(self, year: int, semester: int) -> pd.Timestamp:
        """
        Calcula dinamicamente o início de cada semestre sem hardcoding de datas.

        Semestre 1 → 3ª segunda-feira de setembro do ano indicado.
        Semestre 2 → última segunda-feira de fevereiro do ano indicado.

        Esta heurística cobre o calendário académico do IPL e da generalidade
        das instituições portuguesas (ex: 2025 → 15-09-2025 / 23-02-2026).
        """
        if semester == 1:
            # 3ª segunda-feira de setembro
            sep_1 = pd.Timestamp(f"{year}-09-01")
            # dayofweek: 0=Segunda ... 6=Domingo
            days_until_monday = (7 - sep_1.dayofweek) % 7  # dias até à 1ª segunda
            first_monday = sep_1 + pd.DateOffset(days=days_until_monday)
            # Se sep_1 já for segunda-feira, days_until_monday = 0 → first_monday = sep_1
            return first_monday + pd.DateOffset(weeks=2)  # +2 semanas → 3ª segunda
        else:
            # Última segunda-feira de fevereiro
            # Verifica se o ano é bissexto para usar o dia 29 ou 28
            feb_last_day = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
            feb_last = pd.Timestamp(f"{year}-02-{feb_last_day}")
            days_back = feb_last.dayofweek  # 0=Segunda → recua 0 dias; 1=Terça → recua 1, etc.
            return feb_last - pd.DateOffset(days=days_back)

    def build_date_dimension(self, start_date='2018-01-01', end_date='2035-12-31') -> pd.DataFrame:
        """
        Gera a Dim_Data completa.

        O início de cada semestre é calculado automaticamente por ano letivo:
          - Sem 1: 3ª segunda-feira de setembro
          - Sem 2: última segunda-feira de fevereiro
        Não são necessários parâmetros de datas de semestre.
        """
        self.logger.info(f"A gerar Dim_Data ({start_date} a {end_date})...")
        date_range = pd.date_range(start=start_date, end=end_date)
        df = pd.DataFrame({'DataCompleta': date_range})

        df['SK_Data'] = df['DataCompleta'].dt.strftime('%Y%m%d').astype(int)
        df['DataCompleta'] = df['DataCompleta'].dt.date
        df['Ano'] = pd.to_datetime(df['DataCompleta']).dt.year
        df['Mes'] = pd.to_datetime(df['DataCompleta']).dt.month
        df['Dia'] = pd.to_datetime(df['DataCompleta']).dt.day
        df['Numero_Semana'] = pd.to_datetime(df['DataCompleta']).dt.isocalendar().week.astype(int)

        # Pré-calcula os inícios de semestre para todos os anos no intervalo
        # (evita recalcular dentro do apply linha a linha)
        anos = range(
            pd.Timestamp(start_date).year,
            pd.Timestamp(end_date).year + 2
        )
        sem_starts = {
            (year, sem): self._get_semester_start(year, sem)
            for year in anos
            for sem in (1, 2)
        }

        def _classify_semestre(row):
            """
            Classifica o semestre com base nas datas reais de início,
            não apenas pelo mês — necessário porque o Sem 2 começa ainda em fevereiro.

            Lógica:
              - Agosto → 0 (férias de verão)
              - Se a data >= início do Sem 2 do ano civil → Semestre 2
              - Se a data >= início do Sem 1 do ano académico → Semestre 1
              - Caso contrário → 0 (entre semestres / férias)
            """
            data = pd.Timestamp(row['DataCompleta'])
            ano = row['Ano']
            mes = row['Mes']

            if mes == 8:
                return 0

            # Sem 2 começa em fevereiro: compara com a data real
            sem2_start = sem_starts.get((ano, 2))
            if sem2_start and data >= sem2_start and mes not in [8, 9, 10, 11, 12]:
                return 2

            # Sem 1 começa em setembro: o ano de referência é o ano anterior para jan-jul
            ano_ref_s1 = ano if mes >= 9 else ano - 1
            sem1_start = sem_starts.get((ano_ref_s1, 1))
            if sem1_start and data >= sem1_start and mes in [9, 10, 11, 12, 1, 2]:
                return 1

            return 0  # entre semestres

        df['Semestre'] = df.apply(_classify_semestre, axis=1)

        # Ano letivo: setembro marca a transição
        df['Ano_Escolar'] = df.apply(
            lambda r: f"{r['Ano']}/{r['Ano']+1}" if r['Mes'] >= 9 else f"{r['Ano']-1}/{r['Ano']}",
            axis=1
        )

        def _escolar_week(row):
            if row['Semestre'] == 0:
                return 0

            data = pd.Timestamp(row['DataCompleta'])
            mes = row['Mes']
            ano = row['Ano']

            if row['Semestre'] == 1:
                ano_ref = ano if mes >= 9 else ano - 1
            else:
                ano_ref = ano

            ref_date = sem_starts.get((ano_ref, row['Semestre']))
            if ref_date is None:
                return 0

            delta = (data - ref_date).days
            week = delta // 7 + 1
            return max(week, 1)  # dentro do semestre começa em 1

        df['Numero_Semana_Escolar'] = df.apply(_escolar_week, axis=1)

        day_map = {
            0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira',
            3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'
        }
        df['DiaSemana'] = pd.to_datetime(df['DataCompleta']).dt.dayofweek.map(day_map)

        def get_tipo_dia(row):
            if row['DiaSemana'] in ['Sábado', 'Domingo']:
                return 'Fim de Semana'
            if row['Mes'] == 8:
                return 'Férias'
            return 'Dia Útil/Letivo'

        df['Tipo_Dia'] = df.apply(get_tipo_dia, axis=1)

        self.logger.info(f"Dim_Data gerada: {len(df):,} registos.")
        return df

    def build_hour_dimension(self) -> pd.DataFrame:
        self.logger.info("A fabricar a Dim_Hora (geração estática)...")
        rows = [{'SK_Hora': h * 100 + m, 'Hora': h, 'Minuto': m} for h in range(24) for m in range(60)]
        return pd.DataFrame(rows)

    # =================================================================
    # 2. LIMPEZA DE STRINGS E PLACEHOLDERS
    # =================================================================

    def _clean_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.select_dtypes(include=['object', 'string']).columns:
            df[col] = df[col].astype(str).str.strip()
            if col in ['edificio', 'desig_edf', 'espaco', 'nome_espaco',
                       'unidade_respon', 'unidade_responsavel']:
                df[col] = df[col].str.upper()
            df[col] = df[col].replace({'nan': pd.NA, '<NA>': pd.NA, '': pd.NA, 'None': pd.NA})
        return df

    # =================================================================
    # 3. IMPUTAÇÃO DE RESPONSÁVEIS
    # =================================================================

    def _impute_responsavel(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in ['pessoa_resp', 'unidade_respon', 'unidade_responsavel']:
            if col in df.columns:
                df[col] = df[col].fillna('Indefinido/N.D.')
        return df

    # =================================================================
    # 4. TRATAMENTO DE REGISTOS SEM UC (Reservas Administrativas)
    # =================================================================

    def _enforce_academic_dummy(self, df: pd.DataFrame) -> pd.DataFrame:
        academic_cols = [
            'cod_disc', 'codigo_unidade_curricular',
            'nome_disci', 'designacao_unidade_curricular',
            'ciclo', 'ciclo_estudo',
        ]
        for col in academic_cols:
            if col in df.columns:
                df[col] = df[col].fillna('SEM_UNIDADE / RESERVA_ADMIN')
        return df

    def _flag_reserva_sem_uc(self, df: pd.DataFrame) -> pd.DataFrame:
        uc_col = next((c for c in ['cod_disc', 'codigo_unidade_curricular'] if c in df.columns), None)
        tipo_col = 'tipo' if 'tipo' in df.columns else None
        if uc_col and tipo_col:
            mask = (
                df[tipo_col].astype(str).str.strip().str.upper() == 'RESERVA'
            ) & df[uc_col].isna()
            count = mask.sum()
            if count > 0:
                self.logger.warning(
                    f"[RESERVA_SEM_UC] {count:,} registos do tipo 'Reserva' "
                    f"sem codigo de UC imputados."
                )
                df.loc[mask, uc_col] = 'SEM_UNIDADE / RESERVA_ADMIN'
        return df

    # =================================================================
    # 5. NORMALIZAÇÃO DE EDIFÍCIOS
    # =================================================================

    def _normalize_edificios(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in ['edificio', 'desig_edf']:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).apply(
                    lambda x: re.sub(r'\s*\(.*?\)', '', x).strip()
                    if x and x not in ('<NA>', 'nan', '') else x
                )
                df[col] = df[col].replace({'<NA>': pd.NA, 'nan': pd.NA, '': pd.NA})
        return df

    # =================================================================
    # 6. EXTRAÇÃO DE TURNOS
    # =================================================================

    def _extract_turno(self, df: pd.DataFrame) -> pd.DataFrame:
        desc_col = next(
            (c for c in ['descricao_com_indicacao_turno', 'descricao'] if c in df.columns), None
        )
        if desc_col:
            df['turno_extraido'] = df[desc_col].astype(str).str.extract(
                r'\b(TP\d*|T\d+|P\d+|PL\d+|S\d+|OT\d+)\b', expand=False
            ).fillna('N/D')
        return df

    # =================================================================
    # 7. FILTROS DE NEGÓCIO E CLASSIFICAÇÃO
    # =================================================================

    def _apply_business_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        df['is_online'] = False
        online_re = 'Online|Ensino a Distância|Virtual|Zoom'

        if 'estado' in df.columns:
            df.loc[
                df['estado'].astype(str).str.contains(online_re, case=False, na=False),
                'is_online'
            ] = True
        for ecol in ['edificio', 'desig_edf']:
            if ecol in df.columns:
                df.loc[
                    df[ecol].astype(str).str.contains(online_re, case=False, na=False),
                    'is_online'
                ] = True

        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        col_f = next((c for c in ['data_fim', 'datafim'] if c in df.columns), None)

        if col_i and col_f:
            df[col_i] = pd.to_datetime(df[col_i], errors='coerce')
            df[col_f] = pd.to_datetime(df[col_f], errors='coerce')
            df = df.dropna(subset=[col_i, col_f]).copy()
            df['duracao_minutos'] = (df[col_f] - df[col_i]).dt.total_seconds() / 60
            pre = len(df)
            df = df[(df['duracao_minutos'] > 0) & (df['duracao_minutos'] <= 360)].copy()
            dropped = pre - len(df)
            if dropped > 0:
                self.logger.info(
                    f"[OUTLIERS] {dropped:,} registos com duração > 6h ou <= 0 foram removidos."
                )

            esp_c = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
            if esp_c:
                df = df.sort_values(by=[col_i, esp_c])
                df['flag_evento_agregado'] = df.duplicated(subset=[col_i, esp_c], keep='first')

        return df

    def _classify_espaco(self, df: pd.DataFrame) -> pd.DataFrame:
        esp_col = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
        if esp_col:
            nome_upper = df[esp_col].astype(str).str.upper()
            conditions = [
                nome_upper.str.contains('LAB', na=False) | nome_upper.str.match(r'^L', na=False),
                nome_upper.str.contains(r'\bANFITEATRO\b|\bAF\d*\b|\bANF\d*\b', na=False),
                nome_upper.str.contains('AUDITORIO|AUDITÓRIO', na=False),
                nome_upper.str.contains('GAB', na=False),
            ]
            choices = ['Laboratorio', 'Anfiteatro', 'Auditorio', 'Gabinete']
            df['categoria_espaco'] = np.select(conditions, choices, default='Sala')
        else:
            df['categoria_espaco'] = 'Sala'

        if 'is_online' in df.columns:
            mask_online = df['is_online'] == True
            edf_col = next((c for c in ['edificio', 'desig_edf'] if c in df.columns), None)
            if edf_col:
                df.loc[mask_online, edf_col] = 'ENSINO A DISTANCIA'
            if esp_col:
                df.loc[mask_online, esp_col] = 'ONLINE'
            df.loc[mask_online, 'categoria_espaco'] = 'Online'

        return df

    def _classify_epoca(self, df: pd.DataFrame) -> pd.DataFrame:
        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        if col_i:
            mes = df[col_i].dt.month
            conditions = [
                mes.isin([1, 2]),
                mes.isin([6, 7]),
                mes == 8
            ]
            choices = ['Época Normal/Recurso (Sem 1)', 'Época Normal/Recurso (Sem 2)', 'Férias']
            df['descricao_epoca'] = np.select(conditions, choices, default='Período Letivo')
        else:
            df['descricao_epoca'] = 'N/D'
        return df

    def _classify_departamento(self, df: pd.DataFrame) -> pd.DataFrame:
        esp_col = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
        if esp_col:
            nome_upper = df[esp_col].astype(str).str.upper()
            siglas = ['DCL', 'DCJ', 'DEC', 'DEE', 'DEI', 'DEM', 'DGE', 'DMAT']
            depts = [
                'Departamento de Ciências da Linguagem',
                'Departamento de Ciências Jurídicas',
                'Departamento de Engenharia Civil',
                'Departamento de Engenharia Eletrotécnica',
                'Departamento de Engenharia Informática',
                'Departamento de Engenharia Mecânica',
                'Departamento de Gestão e Economia',
                'Departamento de Matemática',
            ]
            conditions = [nome_upper.str.contains(rf'\b{s}\b', na=False) for s in siglas]
            df['departamento'] = np.select(conditions, depts, default='N/D')
        else:
            df['departamento'] = 'N/D'
        return df

    # =================================================================
    # 8. CHAVES TEMPORAIS E IDENTIFICADOR ÚNICO
    # =================================================================

    def _generate_temporal_keys(self, df: pd.DataFrame) -> pd.DataFrame:
        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        col_f = next((c for c in ['data_fim', 'datafim'] if c in df.columns), None)
        if col_i and col_f:
            df['SK_Data'] = df[col_i].dt.strftime('%Y%m%d').astype(int)
            df['SK_Hora_Inicio'] = (df[col_i].dt.hour * 100 + df[col_i].dt.minute).astype(int)
            df['SK_Hora_Fim'] = (df[col_f].dt.hour * 100 + df[col_f].dt.minute).astype(int)
        return df

    def _generate_ocupacao_id(self, df: pd.DataFrame) -> pd.DataFrame:
        esp_col = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
        if esp_col not in (df.columns.tolist() if esp_col else []):
            df['espaco_tmp'] = 'UNK'
            esp_col = 'espaco_tmp'

        if 'identificador' in df.columns:
            df['ID_Ocupacao'] = (
                pd.to_numeric(df['identificador'], errors='coerce')
                .fillna(0).astype(int).astype(str)
            )
            mask_zero = df['ID_Ocupacao'] == '0'
            if mask_zero.any():
                df.loc[mask_zero, 'ID_Ocupacao'] = (
                    df['SK_Data'].astype(str) + "_" +
                    df['SK_Hora_Inicio'].astype(str) + "_" +
                    df[esp_col].astype(str).str[:5]
                )
        else:
            df['ID_Ocupacao'] = (
                df['SK_Data'].astype(str) + "_" +
                df['SK_Hora_Inicio'].astype(str) + "_" +
                df[esp_col].astype(str).str[:5]
            )

        if 'espaco_tmp' in df.columns:
            df = df.drop(columns=['espaco_tmp'])
        return df

    # =================================================================
    # 9. CRUZAMENTOS EXTERNOS (Staging SQL, Presenças, Cursos)
    # =================================================================

    def _merge_hybrid_stg(self, df_main: pd.DataFrame, df_stg: pd.DataFrame) -> pd.DataFrame:
        df_stg_e = df_stg[['id', 'unidade_respon', 'pessoa_resp']].copy()
        df_main['identificador'] = pd.to_numeric(df_main['identificador'], errors='coerce')
        df_stg_e['id'] = pd.to_numeric(df_stg_e['id'], errors='coerce')
        df_stg_e = df_stg_e.drop_duplicates(subset=['id'], keep='first')

        df_m = pd.merge(
            df_main, df_stg_e,
            left_on='identificador', right_on='id',
            how='left', suffixes=('', '_sql')
        )

        if 'unidade_respon_sql' in df_m.columns:
            df_m['unidade_respon'] = df_m['unidade_respon_sql'].fillna(df_m.get('unidade_respon'))
        if 'pessoa_resp_sql' in df_m.columns:
            df_m['pessoa_resp'] = df_m['pessoa_resp_sql'].fillna(df_m.get('pessoa_resp'))
        df_m.drop(columns=['id', 'unidade_respon_sql', 'pessoa_resp_sql'], inplace=True, errors='ignore')

        return df_m

    def _merge_attendance(self, df_main: pd.DataFrame, df_pres_raw: pd.DataFrame) -> pd.DataFrame:
        df_p = df_pres_raw.copy()

        if 'unidade_curricular' in df_p.columns:
            df_p['_mk_uc'] = df_p['unidade_curricular'].astype(str).apply(
                lambda x: re.sub(r'\s*\([^)]*\)\s*$', '', x).strip()
            ).str.upper()
        if 'data_inicio' in df_p.columns:
            df_p['_mk_date'] = pd.to_datetime(df_p['data_inicio'], errors='coerce').dt.date
        if 'turno' in df_p.columns:
            df_p['_mk_turno'] = df_p['turno'].astype(str).str.strip()

        df_p['presencas'] = pd.to_numeric(df_p.get('presencas', 0), errors='coerce').fillna(0).astype(int)
        pres_agg = df_p.groupby(
            ['_mk_date', '_mk_uc', '_mk_turno'], dropna=False
        ).agg({'presencas': 'sum'}).reset_index()

        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df_main.columns), None)
        uc_col = next(
            (c for c in ['designacao_unidade_curricular', 'nome_disci'] if c in df_main.columns), None
        )
        turno_col = 'turno_extraido' if 'turno_extraido' in df_main.columns else 'turno'

        df_main['_mk_date'] = pd.to_datetime(df_main[col_i], errors='coerce').dt.date if col_i else None
        df_main['_mk_uc'] = df_main[uc_col].astype(str).str.strip().str.upper() if uc_col else ''
        df_main['_mk_turno'] = (
            df_main.get(turno_col, pd.Series([''] * len(df_main))).astype(str).str.strip()
        )

        df_merged = pd.merge(
            df_main, pres_agg,
            on=['_mk_date', '_mk_uc', '_mk_turno'],
            how='left', suffixes=('', '_fp')
        )

        if 'presencas_fp' in df_merged.columns:
            df_merged['presencas'] = (
                df_merged['presencas_fp'].fillna(df_merged.get('presencas', 0)).fillna(0).astype(int)
            )
            df_merged.drop(columns=['presencas_fp'], inplace=True, errors='ignore')
        elif 'presencas' not in df_merged.columns:
            df_merged['presencas'] = 0

        ghost_count = (df_merged['presencas'] == 0).sum()
        if ghost_count > 0:
            self.logger.info(f"[GHOST_SESSIONS] {ghost_count:,} registos com presencas = 0.")

        df_merged.drop(columns=['_mk_date', '_mk_uc', '_mk_turno'], inplace=True, errors='ignore')
        return df_merged

    def _process_courses(self, df_cursos: pd.DataFrame) -> pd.DataFrame:
        df_c = df_cursos.copy()
        col_map = {c: c.lower().strip() for c in df_c.columns}
        df_c = df_c.rename(columns=col_map)

        for col in ['codigo_curso', 'codigo_uc']:
            if col in df_c.columns:
                df_c[col] = df_c[col].fillna('').astype(str).str.strip()
                df_c[col] = df_c[col].replace({'nan': '', 'None': '', '<NA>': ''})

        df_c = df_c[df_c['codigo_curso'].str.len() > 0].copy()
        df_c = df_c[df_c['codigo_uc'].str.len() > 0].copy()

        df_c['codigo_uc_limpo'] = df_c.apply(
            lambda x: x['codigo_uc'][len(x['codigo_curso']):]
            if x['codigo_uc'].startswith(x['codigo_curso']) else x['codigo_uc'],
            axis=1
        )
        df_c['codigo_uc_limpo'] = df_c['codigo_uc_limpo'].str.lstrip('0')

        nome_col = next((c for c in ['nome_curso', 'designacao_curso'] if c in df_c.columns), None)
        if nome_col and nome_col != 'nome_curso':
            df_c = df_c.rename(columns={nome_col: 'nome_curso'})

        return df_c

    def _merge_course_data(self, df_main: pd.DataFrame, df_cursos: pd.DataFrame) -> pd.DataFrame:
        df_cursos_clean = self._process_courses(df_cursos)
        uc_col = 'cod_disc' if 'cod_disc' in df_main.columns else 'codigo_unidade_curricular'
        df_enriched = pd.merge(
            df_main,
            df_cursos_clean[['codigo_uc_limpo', 'nome_curso', 'codigo_curso']].drop_duplicates(
                'codigo_uc_limpo'
            ),
            left_on=uc_col, right_on='codigo_uc_limpo',
            how='left'
        )
        return df_enriched

    # =================================================================
    # 10. ALINHAMENTO COM DDL DW
    # =================================================================

    def _align_to_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        impute_map = {
            'edificio': 'Edifício Desconhecido',
            'espaco': 'Espaço Desconhecido',
            'tipo': 'N/D',
            'estado': 'N/D',
            'turno_extraido': 'N/D',
            'ciclo_estudo': 'N/D',
            'codigo_unidade_curricular': 'SEM_UNIDADE / RESERVA_ADMIN',
            'designacao_unidade_curricular': 'SEM_UNIDADE / RESERVA_ADMIN',
            'unidade_respon': 'Indefinido/N.D.',
            'unidade_responsavel': 'Indefinido/N.D.',
            'pessoa_resp': 'Indefinido/N.D.',
            'nome_curso': 'N/D',
            'codigo_curso': 'N/D',
            'descricao_epoca': 'N/D',
            'departamento': 'N/D',
            'Departamento': 'N/D',
        }
        for col, default in impute_map.items():
            if col in df.columns:
                df[col] = df[col].fillna(default).replace(
                    {'nan': default, '<NA>': default, '': default}
                )

        uc_code_col = next(
            (c for c in ['codigo_unidade_curricular', 'cod_disc'] if c in df.columns), None
        )
        if uc_code_col:
            df[uc_code_col] = (
                df[uc_code_col].astype(str)
                .str.replace(r'\.0$', '', regex=True)
                .str.strip()
            )

        if 'flag_evento_agregado' in df.columns:
            df['flag_evento_agregado'] = df['flag_evento_agregado'].astype(bool)

        for num_col in ['presencas', 'duracao_minutos']:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors='coerce').fillna(0).astype(int)

        if 'is_online' in df.columns:
            df['is_online'] = df['is_online'].astype(int)

        rename_map = {
            'edificio': 'Edificio',
            'espaco': 'Nome_Espaco',
            'tipo': 'Designacao_Atividade',
            'estado': 'Estado',
            'turno_extraido': 'Designacao_Turno',
            'ciclo_estudo': 'Ciclo_Estudo',
            'unidade_responsavel': 'Escola_Responsavel',
            'unidade_respon': 'Escola_Responsavel',
            'pessoa_resp': 'Docente_Responsavel',
            'duracao_minutos': 'Duracao_Minutos',
            'flag_evento_agregado': 'Flag_Evento_Agregado',
            'presencas': 'Numero_Presencas',
            'is_online': 'is_online',
            'categoria_espaco': 'Categoria_Espaco',
            'descricao_epoca': 'Descricao_Epoca',
            'departamento': 'Departamento',
        }

        if 'codigo_unidade_curricular' in df.columns:
            rename_map['codigo_unidade_curricular'] = 'Codigo_UC'
        elif 'cod_disc' in df.columns:
            rename_map['cod_disc'] = 'Codigo_UC'
        if 'designacao_unidade_curricular' in df.columns:
            rename_map['designacao_unidade_curricular'] = 'Designacao_UC'
        elif 'nome_disci' in df.columns:
            rename_map['nome_disci'] = 'Designacao_UC'
        if 'nome_curso' in df.columns:
            rename_map['nome_curso'] = 'Nome_Curso'
        if 'codigo_curso' in df.columns:
            rename_map['codigo_curso'] = 'Codigo_Curso'

        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        df = df.loc[:, ~df.columns.duplicated()]
        return df

    # =================================================================
    # ORQUESTRAÇÃO PRINCIPAL
    # =================================================================

    def apply_pipeline(
        self,
        df_main: pd.DataFrame,
        df_cursos: pd.DataFrame = None,
        df_presencas: pd.DataFrame = None,
        df_stg: pd.DataFrame = None,
    ) -> pd.DataFrame:
        self.logger.info("═" * 60)
        self.logger.info("A iniciar Transformação Dimensional...")

        if df_stg is not None:
            df_main = self._merge_hybrid_stg(df_main, df_stg)

        df_main = self._clean_strings(df_main)
        df_main = self._impute_responsavel(df_main)
        df_main = self._enforce_academic_dummy(df_main)
        df_main = self._flag_reserva_sem_uc(df_main)
        df_main = self._normalize_edificios(df_main)
        df_main = self._extract_turno(df_main)

        df_main = self._apply_business_filters(df_main)
        df_main = self._classify_espaco(df_main)
        df_main = self._classify_epoca(df_main)
        df_main = self._classify_departamento(df_main)

        if df_cursos is not None:
            df_main = self._merge_course_data(df_main, df_cursos)

        if df_presencas is not None:
            df_main = self._merge_attendance(df_main, df_presencas)

        df_main = self._generate_temporal_keys(df_main)
        df_main = self._generate_ocupacao_id(df_main)
        df_main = self._align_to_schema(df_main)

        self.logger.info(f"Transformação Completa. Volume final: {len(df_main):,} registos.")
        self.logger.info("═" * 60)
        return df_main