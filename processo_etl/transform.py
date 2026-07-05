import pandas as pd
import logging
import re
import numpy as np


class DataTransformer:
    # Camada de Transformação do ETL — higienização, normalização e imputação.
    # Sem lógica de extração ou carregamento.

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # Geração de dimensões estáticas

    def _inicio_semestre(self, ano: int, semestre: int) -> pd.Timestamp:
        # Calcula dinamicamente o início de cada semestre sem hardcoding de datas.
        # Sem 1 → 3ª segunda-feira de setembro | Sem 2 → última segunda-feira de fevereiro
        if semestre == 1:
            set_1 = pd.Timestamp(f"{ano}-09-01")
            dias_ate_segunda = (7 - set_1.dayofweek) % 7
            primeira_segunda = set_1 + pd.DateOffset(days=dias_ate_segunda)
            return primeira_segunda + pd.DateOffset(weeks=2)
        else:
            ultimo_dia_fev = 29 if (ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)) else 28
            ultimo_fev = pd.Timestamp(f"{ano}-02-{ultimo_dia_fev}")
            dias_atras = ultimo_fev.dayofweek
            return ultimo_fev - pd.DateOffset(days=dias_atras)

    def construir_dimensao_data(self, start_date='2018-01-01', end_date='2035-12-31') -> pd.DataFrame:
        # Gera a Dim_Data completa — o início de cada semestre é calculado automaticamente
        self.logger.info(f"A gerar Dim_Data ({start_date} a {end_date})...")
        intervalo = pd.date_range(start=start_date, end=end_date)
        df = pd.DataFrame({'DataCompleta': intervalo})

        df['SK_Data']       = df['DataCompleta'].dt.strftime('%Y%m%d').astype(int)
        df['DataCompleta']  = df['DataCompleta'].dt.date
        df['Ano']           = pd.to_datetime(df['DataCompleta']).dt.year
        df['Mes']           = pd.to_datetime(df['DataCompleta']).dt.month
        df['Dia']           = pd.to_datetime(df['DataCompleta']).dt.day
        df['Numero_Semana'] = pd.to_datetime(df['DataCompleta']).dt.isocalendar().week.astype(int)

        # Pré-calcula os inícios de semestre para todos os anos — evita recalcular linha a linha
        anos = range(pd.Timestamp(start_date).year, pd.Timestamp(end_date).year + 2)
        inicios_semestre = {
            (ano, sem): self._inicio_semestre(ano, sem)
            for ano in anos
            for sem in (1, 2)
        }

        def _classificar_semestre(row):
            data = pd.Timestamp(row['DataCompleta'])
            ano  = row['Ano']
            mes  = row['Mes']

            if mes == 8:
                return 0

            # Sem 2 — verifica primeiro para fevereiro não cair no Sem 1
            ano_ref_s2  = ano
            inicio_sem2 = inicios_semestre.get((ano_ref_s2, 2))
            if inicio_sem2 and data >= inicio_sem2 and mes in [2, 3, 4, 5, 6, 7]:
                return 2

            # Sem 1 — setembro a fevereiro (antes do início do Sem 2)
            ano_ref_s1  = ano if mes >= 9 else ano - 1
            inicio_sem1 = inicios_semestre.get((ano_ref_s1, 1))
            if inicio_sem1 and data >= inicio_sem1 and mes in [9, 10, 11, 12, 1, 2]:
                return 1

            return 0

        df['Semestre'] = df.apply(_classificar_semestre, axis=1)

        df['Ano_Escolar'] = df.apply(
            lambda r: f"{r['Ano']}/{r['Ano']+1}" if r['Mes'] >= 9 else f"{r['Ano']-1}/{r['Ano']}",
            axis=1
        )

        def _semana_escolar(row):
            if row['Semestre'] == 0:
                return 0

            data = pd.Timestamp(row['DataCompleta'])
            mes  = row['Mes']
            ano  = row['Ano']

            if row['Semestre'] == 1:
                # Sem 1 começa em setembro — jan/fev pertencem ao ano letivo anterior
                ano_ref  = ano if mes >= 9 else ano - 1
                data_ref = inicios_semestre.get((ano_ref, 1))
            else:
                # Sem 2 começa sempre em fevereiro do ano corrente
                data_ref = inicios_semestre.get((ano, 2))

            if data_ref is None or data < data_ref:
                return 0

            delta = (data - data_ref).days
            return max(delta // 7 + 1, 1)

        df['Numero_Semana_Escolar'] = df.apply(_semana_escolar, axis=1)

        mapa_dias = {
            0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira',
            3: 'Quinta-feira',  4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'
        }
        df['DiaSemana'] = pd.to_datetime(df['DataCompleta']).dt.dayofweek.map(mapa_dias)

        def _tipo_dia(row):
            if row['DiaSemana'] in ['Sábado', 'Domingo']:
                return 'Fim de Semana'
            if row['Numero_Semana_Escolar'] > 0:
                return 'Dia Útil/Letivo'
            return 'Férias'

        df['Tipo_Dia'] = df.apply(_tipo_dia, axis=1)

        self.logger.info(f"Dim_Data gerada: {len(df):,} registos.")
        return df

    def construir_dimensao_hora(self) -> pd.DataFrame:
        # Gera todas as combinações hora/minuto do dia (24 × 60 = 1440 registos)
        self.logger.info("A fabricar a Dim_Hora (geração estática)...")
        linhas = [{'SK_Hora': h * 100 + m, 'Hora': h, 'Minuto': m} for h in range(24) for m in range(60)]
        return pd.DataFrame(linhas)

    # Limpeza de strings

    def _limpar_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        # Normaliza strings — edifícios e espaços ficam em maiúsculas para uniformidade
        for col in df.select_dtypes(include=['object', 'string']).columns:
            df[col] = df[col].astype(str).str.strip()
            if col in ['edificio', 'desig_edf', 'espaco', 'nome_espaco',
                       'unidade_respon', 'unidade_responsavel']:
                df[col] = df[col].str.upper()
            df[col] = df[col].replace({'nan': pd.NA, '<NA>': pd.NA, '': pd.NA, 'None': pd.NA})
        return df

    # Imputação de responsáveis

    def _imputar_responsavel(self, df: pd.DataFrame) -> pd.DataFrame:
        # Preenche responsáveis em falta com o valor omisso padrão
        for col in ['pessoa_resp', 'unidade_respon', 'unidade_responsavel']:
            if col in df.columns:
                df[col] = df[col].fillna('Indefinido/N.D.')
        return df

    # Registos sem UC (reservas administrativas)

    def _imputar_dummy_academico(self, df: pd.DataFrame) -> pd.DataFrame:
        # Reservas sem UC ficam com o placeholder SEM_UNIDADE em vez de nulo
        colunas_academicas = [
            'cod_disc', 'codigo_unidade_curricular',
            'nome_disci', 'designacao_unidade_curricular',
            'ciclo', 'ciclo_estudo',
        ]
        for col in colunas_academicas:
            if col in df.columns:
                df[col] = df[col].fillna('SEM_UNIDADE / RESERVA_ADMIN')
        return df

    def _flag_reserva_sem_uc (self, df: pd.DataFrame) -> pd.DataFrame:
        col_uc   = next((c for c in ['cod_disc', 'codigo_unidade_curricular'] if c in df.columns), None)
        col_tipo = 'tipo' if 'tipo' in df.columns else None
        if col_uc and col_tipo:
            mask = (
                df[col_tipo].astype(str).str.strip().str.upper() == 'RESERVA'
            ) & df[col_uc].isna()
            count = mask.sum()
            if count > 0:
                self.logger.warning(
                    f"[RESERVA_SEM_UC] {count:,} registos do tipo 'Reserva' sem código de UC imputados."
                )
                df.loc[mask, col_uc] = 'SEM_UNIDADE / RESERVA_ADMIN'
        return df

    # Normalização de edifícios

    def _normalizar_edificios(self, df: pd.DataFrame) -> pd.DataFrame:
        # Remove sufixos entre parênteses dos nomes de edifícios (ex: "Ed. A (ESTG)" → "Ed. A")
        for col in ['edificio', 'desig_edf']:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).apply(
                    lambda x: re.sub(r'\s*\(.*?\)', '', x).strip()
                    if x and x not in ('<NA>', 'nan', '') else x
                )
                df[col] = df[col].replace({'<NA>': pd.NA, 'nan': pd.NA, '': pd.NA})
        return df

    # Extração de turnos

    def _extrair_turno(self, df: pd.DataFrame) -> pd.DataFrame:
        # Extrai o código de turno da descrição (ex: "TP1", "PL2") via regex
        col_desc = next(
            (c for c in ['descricao_com_indicacao_turno', 'descricao'] if c in df.columns), None
        )
        if col_desc:
            df['turno_extraido'] = df[col_desc].astype(str).str.extract(
                r'\b(TP\d*|T\d+|P\d+|PL\d+|S\d+|OT\d+)\b', expand=False
            ).fillna('N/D')
        return df

    # Filtros de negócio e classificação

    def _aplicar_filtros_negocio(self, df: pd.DataFrame) -> pd.DataFrame:
        # Deteta sessões online e remove outliers de duração (>6h ou <=0 min)
        df['is_online'] = False
        online_re = 'Online|Ensino a Distância|Virtual|Zoom'

        if 'estado' in df.columns:
            df.loc[
                df['estado'].astype(str).str.contains(online_re, case=False, na=False),
                'is_online'
            ] = True
        for col_edf in ['edificio', 'desig_edf']:
            if col_edf in df.columns:
                df.loc[
                    df[col_edf].astype(str).str.contains(online_re, case=False, na=False),
                    'is_online'
                ] = True

        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        col_f = next((c for c in ['data_fim', 'datafim']       if c in df.columns), None)

        if col_i and col_f:
            df[col_i] = pd.to_datetime(df[col_i], errors='coerce')
            df[col_f] = pd.to_datetime(df[col_f], errors='coerce')
            df = df.dropna(subset=[col_i, col_f]).copy()
            df['duracao_minutos'] = (df[col_f] - df[col_i]).dt.total_seconds() / 60
            antes = len(df)
            df = df[(df['duracao_minutos'] > 0) & (df['duracao_minutos'] <= 360)].copy()
            removidos = antes - len(df)
            if removidos > 0:
                self.logger.info(f"[OUTLIERS] {removidos:,} registos com duração > 6h ou <= 0 removidos.")

            col_esp = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
            if col_esp:
                df = df.sort_values(by=[col_i, col_esp])
                df['flag_evento_agregado'] = df.duplicated(subset=[col_i, col_esp], keep='first')

        return df

    def _classificar_espaco(self, df: pd.DataFrame) -> pd.DataFrame:
        # Classifica o tipo de espaço pelo nome — laboratório, anfiteatro, auditório, etc.
        col_esp = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
        if col_esp:
            nome_upper = df[col_esp].astype(str).str.upper()
            condicoes = [
                nome_upper.str.contains('LAB', na=False) | nome_upper.str.match(r'^L', na=False),
                nome_upper.str.contains(r'\bANFITEATRO\b|\bAF\d*\b|\bANF\d*\b', na=False),
                nome_upper.str.contains('AUDITORIO|AUDITÓRIO', na=False),
                nome_upper.str.contains('GAB', na=False),
            ]
            categorias = ['Laboratorio', 'Anfiteatro', 'Auditorio', 'Gabinete']
            df['categoria_espaco'] = np.select(condicoes, categorias, default='Sala')
        else:
            df['categoria_espaco'] = 'Sala'

        # Sessões online têm edifício e espaço substituídos por valores padronizados
        if 'is_online' in df.columns:
            mask_online = df['is_online'] == True
            col_edf = next((c for c in ['edificio', 'desig_edf'] if c in df.columns), None)
            if col_edf:
                df.loc[mask_online, col_edf] = 'ENSINO A DISTANCIA'
            if col_esp:
                df.loc[mask_online, col_esp] = 'ONLINE'
            df.loc[mask_online, 'categoria_espaco'] = 'Online'

        return df

    def _classificar_epoca(self, df: pd.DataFrame) -> pd.DataFrame:
        # Classifica a época letiva pelo mês da sessão
        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        if col_i:
            mes = df[col_i].dt.month
            condicoes = [mes.isin([1, 2]), mes.isin([6, 7]), mes == 8]
            epocas    = ['Época Normal/Recurso (Sem 1)', 'Época Normal/Recurso (Sem 2)', 'Férias']
            df['descricao_epoca'] = np.select(condicoes, epocas, default='Período Letivo')
        else:
            df['descricao_epoca'] = 'N/D'
        return df

    def _classificar_departamento(self, df: pd.DataFrame) -> pd.DataFrame:
        # Infere o departamento pela sigla no nome do espaço (ex: "DEI" → Eng. Informática)
        col_esp = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
        if col_esp:
            nome_upper = df[col_esp].astype(str).str.upper()
            siglas = ['DCL', 'DCJ', 'DEC', 'DEE', 'DEI', 'DEM', 'DGE', 'DMAT']
            depts  = [
                'Departamento de Ciências da Linguagem',
                'Departamento de Ciências Jurídicas',
                'Departamento de Engenharia Civil',
                'Departamento de Engenharia Eletrotécnica',
                'Departamento de Engenharia Informática',
                'Departamento de Engenharia Mecânica',
                'Departamento de Gestão e Economia',
                'Departamento de Matemática',
            ]
            condicoes = [nome_upper.str.contains(rf'\b{s}\b', na=False) for s in siglas]
            df['departamento'] = np.select(condicoes, depts, default='N/D')
        else:
            df['departamento'] = 'N/D'
        return df

    # Chaves temporais e identificador único

    def _gerar_chaves_temporais(self, df: pd.DataFrame) -> pd.DataFrame:
        # Gera SK_Data e SK_Hora a partir dos campos de data/hora de início e fim
        col_i = next((c for c in ['data_inicio', 'datainicio'] if c in df.columns), None)
        col_f = next((c for c in ['data_fim', 'datafim']       if c in df.columns), None)
        if col_i and col_f:
            df['SK_Data']        = df[col_i].dt.strftime('%Y%m%d').astype(int)
            df['SK_Hora_Inicio'] = (df[col_i].dt.hour * 100 + df[col_i].dt.minute).astype(int)
            df['SK_Hora_Fim']    = (df[col_f].dt.hour * 100 + df[col_f].dt.minute).astype(int)
        return df

    def _gerar_id_ocupacao(self, df: pd.DataFrame) -> pd.DataFrame:
        # Usa o identificador original se existir; caso contrário gera um composto (data_hora_espaço)
        col_esp = next((c for c in ['espaco', 'nome_espaco'] if c in df.columns), None)
        if col_esp not in (df.columns.tolist() if col_esp else []):
            df['espaco_tmp'] = 'UNK'
            col_esp = 'espaco_tmp'

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
                    df[col_esp].astype(str).str[:5]
                )
        else:
            df['ID_Ocupacao'] = (
                df['SK_Data'].astype(str) + "_" +
                df['SK_Hora_Inicio'].astype(str) + "_" +
                df[col_esp].astype(str).str[:5]
            )

        if 'espaco_tmp' in df.columns:
            df = df.drop(columns=['espaco_tmp'])
        return df

    # Cruzamentos externos

    def _cruzar_staging_hibrido(self, df_main: pd.DataFrame, df_stg: pd.DataFrame) -> pd.DataFrame:
        # Enriquece o dataset principal com responsável e unidade vindos do dump SQL
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

    def _cruzar_presencas(self, df_main: pd.DataFrame, df_pres_raw: pd.DataFrame) -> pd.DataFrame:
        # Cruza presenças pelo triplo (data, UC, turno) — ghost session se ficar 0
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

        col_i     = next((c for c in ['data_inicio', 'datainicio'] if c in df_main.columns), None)
        col_uc    = next((c for c in ['designacao_unidade_curricular', 'nome_disci'] if c in df_main.columns), None)
        col_turno = 'turno_extraido' if 'turno_extraido' in df_main.columns else 'turno'

        df_main['_mk_date']  = pd.to_datetime(df_main[col_i], errors='coerce').dt.date if col_i else None
        df_main['_mk_uc']    = df_main[col_uc].astype(str).str.strip().str.upper() if col_uc else ''
        df_main['_mk_turno'] = (
            df_main.get(col_turno, pd.Series([''] * len(df_main))).astype(str).str.strip()
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

    def _processar_cursos(self, df_cursos: pd.DataFrame) -> pd.DataFrame:
        # Limpa e normaliza o ficheiro de cursos — remove prefixos de código duplicados
        df_c = df_cursos.copy()
        df_c = df_c.rename(columns={c: c.lower().strip() for c in df_c.columns})

        for col in ['codigo_curso', 'codigo_uc']:
            if col in df_c.columns:
                df_c[col] = df_c[col].fillna('').astype(str).str.strip()
                df_c[col] = df_c[col].replace({'nan': '', 'None': '', '<NA>': ''})

        df_c = df_c[df_c['codigo_curso'].str.len() > 0].copy()
        df_c = df_c[df_c['codigo_uc'].str.len() > 0].copy()

        # Remove o prefixo do código de curso do código de UC quando estão concatenados
        df_c['codigo_uc_limpo'] = df_c.apply(
            lambda x: x['codigo_uc'][len(x['codigo_curso']):]
            if x['codigo_uc'].startswith(x['codigo_curso']) else x['codigo_uc'],
            axis=1
        )
        df_c['codigo_uc_limpo'] = df_c['codigo_uc_limpo'].str.lstrip('0')

        col_nome = next((c for c in ['nome_curso', 'designacao_curso'] if c in df_c.columns), None)
        if col_nome and col_nome != 'nome_curso':
            df_c = df_c.rename(columns={col_nome: 'nome_curso'})

        return df_c

    def _cruzar_dados_cursos(self, df_main: pd.DataFrame, df_cursos: pd.DataFrame) -> pd.DataFrame:
        # Enriquece o dataset principal com o nome e código de curso
        df_cursos_limpo = self._processar_cursos(df_cursos)
        col_uc = 'cod_disc' if 'cod_disc' in df_main.columns else 'codigo_unidade_curricular'
        df_enriquecido = pd.merge(
            df_main,
            df_cursos_limpo[['codigo_uc_limpo', 'nome_curso', 'codigo_curso']].drop_duplicates('codigo_uc_limpo'),
            left_on=col_uc, right_on='codigo_uc_limpo',
            how='left'
        )
        return df_enriquecido

    # Alinhamento com o schema da base de dados

    def _alinhar_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        # Preenche nulos com os valores omissos padrão e renomeia colunas para o schema do DW
        mapa_imputacao = {
            'edificio':                        'Edifício Desconhecido',
            'espaco':                          'Espaço Desconhecido',
            'tipo':                            'N/D',
            'estado':                          'N/D',
            'turno_extraido':                  'N/D',
            'ciclo_estudo':                    'N/D',
            'codigo_unidade_curricular':       'SEM_UNIDADE / RESERVA_ADMIN',
            'designacao_unidade_curricular':   'SEM_UNIDADE / RESERVA_ADMIN',
            'unidade_respon':                  'Indefinido/N.D.',
            'unidade_responsavel':             'Indefinido/N.D.',
            'pessoa_resp':                     'Indefinido/N.D.',
            'nome_curso':                      'N/D',
            'codigo_curso':                    'N/D',
            'descricao_epoca':                 'N/D',
            'departamento':                    'N/D',
            'Departamento':                    'N/D',
        }
        for col, omisso in mapa_imputacao.items():
            if col in df.columns:
                df[col] = df[col].fillna(omisso).replace(
                    {'nan': omisso, '<NA>': omisso, '': omisso}
                )

        # Remove sufixos ".0" que o pandas adiciona a códigos numéricos lidos como float
        col_uc_codigo = next((c for c in ['codigo_unidade_curricular', 'cod_disc'] if c in df.columns), None)
        if col_uc_codigo:
            df[col_uc_codigo] = df[col_uc_codigo].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if 'flag_evento_agregado' in df.columns:
            df['flag_evento_agregado'] = df['flag_evento_agregado'].astype(bool)

        for col_num in ['presencas', 'duracao_minutos']:
            if col_num in df.columns:
                df[col_num] = pd.to_numeric(df[col_num], errors='coerce').fillna(0).astype(int)

        if 'is_online' in df.columns:
            df['is_online'] = df['is_online'].astype(int)

        mapa_rename = {
            'edificio':               'Edificio',
            'espaco':                 'Nome_Espaco',
            'tipo':                   'Designacao_Atividade',
            'estado':                 'Estado',
            'turno_extraido':         'Designacao_Turno',
            'ciclo_estudo':           'Ciclo_Estudo',
            'unidade_responsavel':    'Escola_Responsavel',
            'unidade_respon':         'Escola_Responsavel',
            'pessoa_resp':            'Docente_Responsavel',
            'duracao_minutos':        'Duracao_Minutos',
            'flag_evento_agregado':   'Flag_Evento_Agregado',
            'presencas':              'Numero_Presencas',
            'is_online':              'is_online',
            'categoria_espaco':       'Categoria_Espaco',
            'descricao_epoca':        'Descricao_Epoca',
            'departamento':           'Departamento',
        }

        if 'codigo_unidade_curricular' in df.columns:
            mapa_rename['codigo_unidade_curricular'] = 'Codigo_UC'
        elif 'cod_disc' in df.columns:
            mapa_rename['cod_disc'] = 'Codigo_UC'
        if 'designacao_unidade_curricular' in df.columns:
            mapa_rename['designacao_unidade_curricular'] = 'Designacao_UC'
        elif 'nome_disci' in df.columns:
            mapa_rename['nome_disci'] = 'Designacao_UC'
        if 'nome_curso'   in df.columns: mapa_rename['nome_curso']   = 'Nome_Curso'
        if 'codigo_curso' in df.columns: mapa_rename['codigo_curso'] = 'Codigo_Curso'

        df = df.rename(columns={k: v for k, v in mapa_rename.items() if k in df.columns})
        # Remove colunas duplicadas que possam ter surgido dos merges
        df = df.loc[:, ~df.columns.duplicated()]
        return df

    # Pipeline principal

    def apply_pipeline(
        self,
        df_main: pd.DataFrame,
        df_cursos: pd.DataFrame = None,
        df_presencas: pd.DataFrame = None,
        df_stg: pd.DataFrame = None,
    ) -> pd.DataFrame:
        # Executa todas as etapas de transformação pela ordem correta
        self.logger.info("═" * 60)
        self.logger.info("A iniciar Transformação Dimensional...")

        if df_stg is not None:
            df_main = self._cruzar_staging_hibrido(df_main, df_stg)

        df_main = self._limpar_strings(df_main)
        df_main = self._imputar_responsavel(df_main)
        df_main = self._imputar_dummy_academico(df_main)
        df_main = self._flag_reserva_sem_uc (df_main)
        df_main = self._normalizar_edificios(df_main)
        df_main = self._extrair_turno(df_main)
        df_main = self._aplicar_filtros_negocio(df_main)
        df_main = self._classificar_espaco(df_main)
        df_main = self._classificar_epoca(df_main)
        df_main = self._classificar_departamento(df_main)

        if df_cursos is not None:
            df_main = self._cruzar_dados_cursos(df_main, df_cursos)

        if df_presencas is not None:
            df_main = self._cruzar_presencas(df_main, df_presencas)

        df_main = self._gerar_chaves_temporais(df_main)
        df_main = self._gerar_id_ocupacao(df_main)
        df_main = self._alinhar_schema(df_main)

        self.logger.info(f"Transformação Completa. Volume final: {len(df_main):,} registos.")
        self.logger.info("═" * 60)
        return df_main