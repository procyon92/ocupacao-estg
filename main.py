import logging
import pandas as pd
import sys

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    setup_logger()
    logger = logging.getLogger("ETL_Orchestrator")

    logger.info("=" * 70)
    logger.info("  ETL PIPELINE v3.0 - Data Warehouse Ocupacao ESTG")
    logger.info("  Modo: Dados Higienizados para BI")
    logger.info("=" * 70)

    # =====================================================================
    # FASE E: EXTRACAO
    # =====================================================================
    logger.info("--- FASE 1: EXTRACAO ---")

    from extract import DataExtractor
    extractor = DataExtractor(base_path="Dados")

    df_agendamentos = extractor.extract_csv("PorSalaTurno.csv", sep=",", encoding="cp1252")
    df_presencas = extractor.extract_csv("PorTurnoPresencas.csv", sep=",", encoding="cp1252")
    df_stg = extractor.extract_sql_staging("script_espacos_salas_turnos.sql")

    if df_agendamentos is None:
        logger.critical("FALHA CRITICA: PorSalaTurno.csv nao carregou.")
        sys.exit(1)
        
    if df_stg is None:
        logger.critical("FALHA CRITICA: script_espacos_salas_turnos.sql nao carregou para staging.")
        sys.exit(1)

    logger.info(f"Agendamentos: {len(df_agendamentos):,} linhas")
    logger.info(f"  Colunas: {list(df_agendamentos.columns)}")
    if df_stg is not None:
        logger.info(f"Staging SQL: {len(df_stg):,} linhas")
        logger.info(f"  Colunas: {list(df_stg.columns)}")

        logger.info("  >> Efetuando MERGE HÍBRIDO com SQL <<")
        # Ensure we only pick what we need for enrichment to avoid duplication
        df_stg_enrich = df_stg[['id', 'unidade_respon', 'pessoa_resp']].copy()
        df_agendamentos['identificador'] = pd.to_numeric(df_agendamentos['identificador'], errors='coerce')
        df_stg_enrich['id'] = pd.to_numeric(df_stg_enrich['id'], errors='coerce')

        # Drop duplicates on SQL just in case to avoid expanding rows
        df_stg_enrich = df_stg_enrich.drop_duplicates(subset=['id'], keep='first')

        pre_len = len(df_agendamentos)
        df_agendamentos = pd.merge(
            df_agendamentos,
            df_stg_enrich,
            left_on='identificador',
            right_on='id',
            how='left',
            suffixes=('', '_sql')
        )
        
        # Resolving values (SQL overwrites CSV if not null, as SQL has rich metadata)
        if 'unidade_respon_sql' in df_agendamentos.columns:
            df_agendamentos['unidade_respon'] = df_agendamentos['unidade_respon_sql'].fillna(df_agendamentos.get('unidade_respon'))
        if 'pessoa_resp_sql' in df_agendamentos.columns:
            df_agendamentos['pessoa_resp'] = df_agendamentos['pessoa_resp_sql'].fillna(df_agendamentos.get('pessoa_resp'))

        df_agendamentos.drop(columns=['id', 'unidade_respon_sql', 'pessoa_resp_sql'], inplace=True, errors='ignore')

        if len(df_agendamentos) != pre_len:
            logger.warning(f"  ALERTA: Merge Híbrido expandiu linhas: {pre_len:,} -> {len(df_agendamentos):,}")

    # =====================================================================
    # FASE T: TRANSFORMACAO
    # =====================================================================
    logger.info("--- FASE 2: TRANSFORMACAO ---")

    from transform import DataTransformer
    transformer = DataTransformer()

    logger.info("Processando Agendamentos (PorSalaTurno.csv)...")
    df_main = transformer.apply_pipeline(df_agendamentos)

    # -----------------------------------------------------------------
    # CRUZAMENTO COM PRESENÇAS (Merge Semântico)
    # -----------------------------------------------------------------
    # PorSalaTurno: identificador(ID sala-turno), data_inicio, data_fim,
    #   codigo_unidade_curricular, descricao_com_indicacao_turno, ...
    # PorTurnoPresencas: identificador(ID sequencial diferente!), data_inicio,
    #   data_fim, unidade_curricular("Nome UC (codigo)"), turno("TP1"), presencas
    #
    # Os 'identificador' são DIFERENTES entre ficheiros!
    # Merge semântico: data_inicio + UC_code + turno
    # -----------------------------------------------------------------
    if df_presencas is not None and len(df_presencas) > 0:
        logger.info("Processando Presencas (PorTurnoPresencas.csv)...")
        df_pres = transformer.apply_pipeline(df_presencas)

        if 'presencas' in df_pres.columns and 'unidade_curricular' in df_pres.columns:
            import re
            logger.info("  Estrategia de merge: date(date-only) + UC_name(UPPER) + turno")

            # ---------------------------------------------------------------
            # CHAVE SEMÂNTICA: Os 'identificador' e 'codigo_unidade_curricular'
            # usam sistemas de numeração DIFERENTES entre os dois CSVs.
            # A unica chave fiável é: Data (date-part) + Nome da UC + Turno.
            # ---------------------------------------------------------------

            # 1. Extrair nome da UC do campo composto do PorTurnoPresencas
            #    Ex: "Marketing Público e Social (20558)" → "Marketing Público e Social"
            df_pres['_merge_uc'] = df_pres['unidade_curricular'].astype(str).apply(
                lambda x: re.sub(r'\s*\([^)]*\)\s*$', '', x).strip()
            ).str.upper()

            # 2. Construir data (date only) para merge
            df_pres['_merge_date'] = df_pres['data_inicio'].dt.date

            # 3. Turno já existe como coluna 'turno' (TP1, T1, etc.)
            df_pres['_merge_turno'] = df_pres['turno'].astype(str).str.strip()

            # 4. Agregar presenças por (date, UC_name, turno)
            pres_agg = df_pres.groupby(
                ['_merge_date', '_merge_uc', '_merge_turno'], dropna=False
            ).agg({'presencas': 'sum'}).reset_index()

            logger.info(f"  Presencas agregadas: {len(pres_agg):,} combinacoes unicas")
            logger.info(f"  Presencas > 0: {(pres_agg['presencas'] > 0).sum():,}")

            # 5. Preparar chaves no ficheiro principal (PorSalaTurno)
            df_main['_merge_date'] = df_main['data_inicio'].dt.date
            df_main['_merge_uc'] = df_main['designacao_unidade_curricular'].astype(str).str.strip().str.upper()
            df_main['_merge_turno'] = df_main['turno_extraido'].astype(str).str.strip()

            # 6. Merge
            pre_len = len(df_main)
            df_main = pd.merge(
                df_main, pres_agg,
                on=['_merge_date', '_merge_uc', '_merge_turno'],
                how='left',
                suffixes=('', '_from_pres')
            )

            # 7. Resolver coluna presencas
            if 'presencas_from_pres' in df_main.columns:
                df_main['presencas'] = df_main['presencas_from_pres'].fillna(
                    df_main.get('presencas', 0)
                ).fillna(0).astype(int)
                df_main.drop(columns=['presencas_from_pres'], inplace=True, errors='ignore')
            elif 'presencas' not in df_main.columns:
                df_main['presencas'] = 0

            df_main['presencas'] = pd.to_numeric(df_main['presencas'], errors='coerce').fillna(0).astype(int)

            # 8. Cleanup temp merge columns
            df_main.drop(columns=['_merge_date', '_merge_uc', '_merge_turno'], inplace=True, errors='ignore')

            matched = (df_main['presencas'] > 0).sum()
            logger.info(f"  Presencas cruzadas: {matched:,}/{len(df_main):,} ({matched/len(df_main)*100:.1f}%)")

            # 9. Verificar e corrigir expansão (merge não deve multiplicar linhas)
            if len(df_main) != pre_len:
                logger.warning(f"  ATENCAO: Merge expandiu de {pre_len:,} para {len(df_main):,}")
                df_main = df_main.sort_values('presencas', ascending=False)
                df_main = df_main.drop_duplicates(
                    subset=['data_inicio', 'espaco', 'codigo_unidade_curricular', 'turno_extraido'],
                    keep='first'
                )
                logger.info(f"  Apos dedup: {len(df_main):,} linhas")
        else:
            logger.warning("  Presencas sem colunas necessarias para merge semantico.")
            if 'presencas' not in df_main.columns:
                df_main['presencas'] = 0

    logger.info(f"  Colunas pos-transform: {list(df_main.columns)}")

    # =====================================================================
    # FASE C: COMPLIANCE - RENOMEACAO PARA SCHEMA DW
    # =====================================================================
    logger.info("--- FASE 3: COMPLIANCE (Mapeamento para Schema DW) ---")

    db_mapping = {
        # Espaco
        'edificio': 'Edificio',
        'espaco': 'Nome_Espaco',
        'unidade_respon': 'Unidade_Responsavel',
        # Unidade Curricular
        'codigo_unidade_curricular': 'Codigo_UC',
        'designacao_unidade_curricular': 'Designacao_UC',
        'ciclo_estudo': 'Ciclo_Estudo',
        # Responsavel
        'pessoa_resp': 'Nome_Responsavel',
        # Turno
        'turno_extraido': 'Designacao_Turno',
        # Tipo de Atividade
        'tipo': 'Designacao_Atividade',
        # Estado
        'estado': 'Estado',
        # Metricas
        'duracao_minutos': 'Duracao_Minutos',
        'presencas': 'Numero_Presencas',
        'flag_evento_agregado': 'Flag_Evento_Agregado',
        # Datas
        'data_inicio': 'DataInicio',
        'data_fim': 'DataFim',
        # ID
        'identificador': 'SourceID',
        # Descricao
        'descricao_com_indicacao_turno': 'Descricao_Turno_Raw',
    }

    rename_map = {k: v for k, v in db_mapping.items() if k in df_main.columns}
    df_main.rename(columns=rename_map, inplace=True)

    logger.info(f"  Colunas pos-rename: {list(df_main.columns)}")
    logger.info(f"  Total registos: {len(df_main):,}")

    # =====================================================================
    # FASE SANITÁRIA: AUDITORIA PRE-LOAD DE NULOS
    # =====================================================================
    logger.info("--- FASE 3.5: AUDITORIA PRE-LOAD ---")

    # Fix Float-Poisoning in IDs
    if 'Codigo_UC' in df_main.columns:
        # User explicitly requested this strict casting
        df_main['Codigo_UC'] = pd.to_numeric(df_main['Codigo_UC'], errors='coerce').fillna(0).astype(int).astype(str)
        # Re-apply placeholder for 0s
        df_main['Codigo_UC'] = df_main['Codigo_UC'].replace({'0': 'SEM_UNIDADE / RESERVA_ADMIN'})

    # Garantir imputacao de todos os campos dimensionais
    dim_defaults = {
        'Edificio': 'Edificio Desconhecido',
        'Nome_Espaco': 'Espaco Desconhecido',
        'Unidade_Responsavel': 'Indefinido/N.D.',
        'Designacao_UC': 'SEM_UNIDADE / RESERVA_ADMIN',
        'Ciclo_Estudo': 'N/D',
        'Nome_Responsavel': 'Indefinido/N.D.',
        'Designacao_Turno': 'N/D',
        'Designacao_Atividade': 'N/D',
        'Estado': 'N/D',
    }
    for col, default in dim_defaults.items():
        if col in df_main.columns:
            df_main[col] = df_main[col].fillna(default)
            df_main[col] = df_main[col].replace({'nan': default, '<NA>': default, '': default, 'None': default})

    # Garantir metricas numericas
    if 'Numero_Presencas' not in df_main.columns:
        df_main['Numero_Presencas'] = 0
    df_main['Numero_Presencas'] = pd.to_numeric(df_main['Numero_Presencas'], errors='coerce').fillna(0).astype(int)

    if 'Duracao_Minutos' not in df_main.columns:
        df_main['Duracao_Minutos'] = 0
    df_main['Duracao_Minutos'] = pd.to_numeric(df_main['Duracao_Minutos'], errors='coerce').fillna(0).astype(int)

    # Reportar nulos residuais
    null_report = df_main.isnull().sum()
    residual = null_report[null_report > 0]
    if len(residual) > 0:
        logger.warning(f"  Nulos residuais pos-sanitizacao: {residual.to_dict()}")
    else:
        logger.info("  ZERO nulos residuais! DataFrame imaculado.")

    # =====================================================================
    # FASE L: LOAD (MYSQL)
    # =====================================================================
    logger.info("--- FASE 4: LOAD (MySQL) ---")

    from load import DataLoader
    loader = DataLoader(host="localhost", user="root", password="dbsecret", db_name="dw_ocupacao")

    # ----- 0. DIMENSOES AUTONOMAS -----
    logger.info("[STEP 0] Populando Dimensoes Autonomas...")
    loader.generate_date_dimension()
    loader.generate_hour_dimension()
    loader.ensure_dummy_dimension_records()

    # ----- 1. SK_Data (YYYYMMDD) -----
    logger.info("[STEP 1] Calculando SK_Data...")
    if 'DataInicio' in df_main.columns:
        data_dt = pd.to_datetime(df_main['DataInicio'], errors='coerce')
        df_main['SK_Data'] = data_dt.dt.strftime('%Y%m%d').fillna('0').astype(int)
    else:
        logger.warning("  DataInicio NAO ENCONTRADA!")
        df_main['SK_Data'] = 0

    filled = (df_main['SK_Data'] > 0).sum()
    logger.info(f"  SK_Data: {filled:,}/{len(df_main):,}")

    # ----- 2. SK_Hora_Inicio e SK_Hora_Fim (HHMM) -----
    logger.info("[STEP 2] Calculando SK_Hora...")
    if 'DataInicio' in df_main.columns:
        inicio_dt = pd.to_datetime(df_main['DataInicio'], errors='coerce')
        df_main['SK_Hora_Inicio'] = (inicio_dt.dt.hour * 100 + inicio_dt.dt.minute).fillna(0).astype(int)
    else:
        df_main['SK_Hora_Inicio'] = 0

    if 'DataFim' in df_main.columns:
        fim_dt = pd.to_datetime(df_main['DataFim'], errors='coerce')
        df_main['SK_Hora_Fim'] = (fim_dt.dt.hour * 100 + fim_dt.dt.minute).fillna(0).astype(int)
    else:
        df_main['SK_Hora_Fim'] = 0

    # Nota: SK_Hora_Fim=0 para sessoes que terminam a meia-noite (00:00)
    # e perfeitamente legitimo — 1,264 sessoes (~2.2%) terminam as 00:00
    midnight_count = (df_main['SK_Hora_Fim'] == 0).sum()
    logger.info(f"  SK_Hora_Fim=0 (meia-noite): {midnight_count:,} ({midnight_count/len(df_main)*100:.1f}%)")

    # ----- 3. ID_Ocupacao -----
    logger.info("[STEP 3] Gerando ID_Ocupacao...")
    if 'SourceID' in df_main.columns:
        # Avoid float-poisoning if SourceID was read as float
        df_main['ID_Ocupacao'] = pd.to_numeric(df_main['SourceID'], errors='coerce').fillna(0).astype(int).astype(str)
        # Exclude dummy value back to generic 
        df_main['ID_Ocupacao'] = df_main['ID_Ocupacao'].replace({'0': 'DEFAULT_ID'}).str[:100]
    else:
        c1 = df_main['SK_Data'].astype(str)
        c2 = df_main.get('Nome_Espaco', pd.Series('ND', index=df_main.index)).astype(str).str[:20]
        df_main['ID_Ocupacao'] = (c1 + "_" + c2).str[:100]

    # ----- 4. DIMENSOES COM LOOKUP -----
    logger.info("[STEP 4] Carregando Dimensoes...")

    if 'Edificio' in df_main.columns and 'Nome_Espaco' in df_main.columns:
        logger.info("  -> Dim_Espaco")
        df_main = loader.load_dimension(df_main, "Dim_Espaco", ['Edificio', 'Nome_Espaco', 'Unidade_Responsavel', 'is_online'], 'SK_Espaco')

    if 'Codigo_UC' in df_main.columns:
        logger.info("  -> Dim_Unidade_Curricular")
        nk_uc = ['Codigo_UC']
        if 'Designacao_UC' in df_main.columns:
            nk_uc.append('Designacao_UC')
        if 'Ciclo_Estudo' in df_main.columns:
            nk_uc.append('Ciclo_Estudo')
        df_main = loader.load_dimension(df_main, "Dim_Unidade_Curricular", nk_uc, 'SK_Unidade_Curricular')

    if 'Nome_Responsavel' in df_main.columns:
        logger.info("  -> Dim_Responsavel")
        df_main = loader.load_dimension(df_main, "Dim_Responsavel", ['Nome_Responsavel'], 'SK_Responsavel')

    if 'Designacao_Turno' in df_main.columns:
        logger.info("  -> Dim_Turno")
        df_main = loader.load_dimension(df_main, "Dim_Turno", ['Designacao_Turno'], 'SK_Turno')

    if 'Designacao_Atividade' in df_main.columns:
        logger.info("  -> Dim_Tipo_Atividade")
        df_main = loader.load_dimension(df_main, "Dim_Tipo_Atividade", ['Designacao_Atividade'], 'SK_Tipo_Atividade')

    if 'Estado' in df_main.columns:
        logger.info("  -> Dim_Estado_Agendamento")
        df_main = loader.load_dimension(df_main, "Dim_Estado_Agendamento", ['Estado'], 'SK_Estado_Agendamento')

    if 'Ciclo_Estudo' in df_main.columns:
        logger.info("  -> Dim_Curso (Removido lookup dinâmico para garantir placeholder)")
        # Dim_Curso mantida estritamente vazia segundo regras de fine-tuning
        df_main['SK_Curso'] = 0

    # ----- 5. AUDITORIA -----
    logger.info("[STEP 5] Auditoria de Qualidade...")
    loader.print_quality_metrics(df_main)

    # ----- 6. FACTO_OCUPACAO -----
    logger.info("[STEP 6] Carregando Facto_Ocupacao...")

    df_payload = loader.prepare_fact_payload(df_main)
    logger.info(f"  Payload: {len(df_payload):,} registos, {len(df_payload.columns)} colunas.")

    # Relatório final de nulos no payload
    payload_nulls = df_payload.isnull().sum()
    payload_residual = payload_nulls[payload_nulls > 0]
    if len(payload_residual) > 0:
        logger.warning(f"  NULOS NO PAYLOAD: {payload_residual.to_dict()}")
    else:
        logger.info("  Payload sem nulos. Integridade confirmada.")

    # Relatório de presenças
    pres_filled = (df_payload['Numero_Presencas'] > 0).sum()
    logger.info(f"  Numero_Presencas > 0: {pres_filled:,}/{len(df_payload):,} ({pres_filled/len(df_payload)*100:.1f}%)")

    loader.load_fact(df_payload)

    logger.info("=" * 70)
    logger.info("  >> TAREFA 3 COMPLETADA — DADOS HIGIENIZADOS PARA BI <<")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
