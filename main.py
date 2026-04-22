import logging
import pandas as pd
import sys
import re
import os
from dotenv import load_dotenv

# Carregamento das variáveis de ambiente no início da execução
load_dotenv()

def setup_logger():
    """Configuração do sistema de logging para auditoria do processo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    setup_logger()
    logger = logging.getLogger("ETL_Orchestrator")

    logger.info("=" * 70)
    logger.info("  ETL PIPELINE v3.0 - Data Warehouse Ocupação ESTG")
    logger.info("  Fase: Implementação do Modelo Dimensional (Tarefa 3)")
    logger.info("=" * 70)

    # =====================================================================
    # FASE E: EXTRAÇÃO (Extraction)
    # =====================================================================
    logger.info("--- FASE 1: EXTRAÇÃO ---")

    from extract import DataExtractor
    extractor = DataExtractor(base_path="Dados")

    # Extração das fontes de dados (CSVs e SQL Staging)
    df_agendamentos = extractor.extract_csv("PorSalaTurno.csv", sep=",", encoding="cp1252")
    df_presencas = extractor.extract_csv("PorTurnoPresencas.csv", sep=",", encoding="cp1252")
    df_stg = extractor.extract_sql_staging("script_espacos_salas_turnos.sql")

    # Validação de integridade das fontes críticas
    if df_agendamentos is None:
        logger.critical("FALHA CRÍTICA: PorSalaTurno.csv não carregou.")
        sys.exit(1)
        
    if df_stg is None:
        logger.critical("FALHA CRÍTICA: script_espacos_salas_turnos.sql não carregou para staging.")
        sys.exit(1)

    logger.info(f"Agendamentos: {len(df_agendamentos):,} linhas")
    
    # Enriquecimento de dados via MERGE HÍBRIDO (CSV + SQL Staging)
    if df_stg is not None:
        logger.info("  >> Efetuando MERGE HÍBRIDO com Metadados SQL <<")
        
        # Seleção de atributos para enriquecimento (Responsáveis e Unidades)
        df_stg_enrich = df_stg[['id', 'unidade_respon', 'pessoa_resp']].copy()
        
        # Normalização de chaves para o merge
        df_agendamentos['identificador'] = pd.to_numeric(df_agendamentos['identificador'], errors='coerce')
        df_stg_enrich['id'] = pd.to_numeric(df_stg_enrich['id'], errors='coerce')

        # Garantia de unicidade na fonte SQL para evitar duplicação de registos no facto
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
        
        # Priorização dos dados provenientes do SQL (metadados mais ricos)
        if 'unidade_respon_sql' in df_agendamentos.columns:
            df_agendamentos['unidade_respon'] = df_agendamentos['unidade_respon_sql'].fillna(df_agendamentos.get('unidade_respon'))
        if 'pessoa_resp_sql' in df_agendamentos.columns:
            df_agendamentos['pessoa_resp'] = df_agendamentos['pessoa_resp_sql'].fillna(df_agendamentos.get('pessoa_resp'))

        df_agendamentos.drop(columns=['id', 'unidade_respon_sql', 'pessoa_resp_sql'], inplace=True, errors='ignore')

        if len(df_agendamentos) != pre_len:
            logger.warning(f"  ALERTA: Merge Híbrido expandiu linhas: {pre_len:,} -> {len(df_agendamentos):,}")

    # =====================================================================
    # FASE T: TRANSFORMAÇÃO (Transformation)
    # =====================================================================
    logger.info("--- FASE 2: TRANSFORMAÇÃO ---")

    from transform import DataTransformer
    transformer = DataTransformer()

    logger.info("Processando Limpeza e Tipagem de Agendamentos...")
    df_main = transformer.apply_pipeline(df_agendamentos)

    # -----------------------------------------------------------------
    # CRUZAMENTO COM PRESENÇAS (Merge Semântico)
    # -----------------------------------------------------------------
    # Nota Técnica: Os 'identificador' são distintos entre ficheiros.
    # Implementação de chave composta: data_inicio + UC_name + turno
    # -----------------------------------------------------------------
    if df_presencas is not None and len(df_presencas) > 0:
        logger.info("Processando Presenças e calculando Chave Semântica...")
        df_pres = transformer.apply_pipeline(df_presencas)

        if 'presencas' in df_pres.columns and 'unidade_curricular' in df_pres.columns:
            logger.info("  Estratégia: date-only + UC_UPPER + turno_extraido")

            # 1. Parsing do nome da UC (Remoção do código entre parênteses)
            df_pres['_merge_uc'] = df_pres['unidade_curricular'].astype(str).apply(
                lambda x: re.sub(r'\s*\([^)]*\)\s*$', '', x).strip()
            ).str.upper()

            # 2. Normalização temporal e de turnos
            df_pres['_merge_date'] = df_pres['data_inicio'].dt.date
            df_pres['_merge_turno'] = df_pres['turno'].astype(str).str.strip()

            # 3. Agregação de presenças para evitar duplicação no merge
            pres_agg = df_pres.groupby(
                ['_merge_date', '_merge_uc', '_merge_turno'], dropna=False
            ).agg({'presencas': 'sum'}).reset_index()

            # 4. Preparação das chaves no DataFrame principal
            df_main['_merge_date'] = df_main['data_inicio'].dt.date
            df_main['_merge_uc'] = df_main['designacao_unidade_curricular'].astype(str).str.strip().str.upper()
            df_main['_merge_turno'] = df_main['turno_extraido'].astype(str).str.strip()

            # 5. Execução do Merge Left para associar presenças às ocupações
            pre_len = len(df_main)
            df_main = pd.merge(
                df_main, pres_agg,
                on=['_merge_date', '_merge_uc', '_merge_turno'],
                how='left',
                suffixes=('', '_from_pres')
            )

            # 6. Consolidação da métrica de presenças
            if 'presencas_from_pres' in df_main.columns:
                df_main['presencas'] = df_main['presencas_from_pres'].fillna(df_main.get('presencas', 0)).fillna(0).astype(int)
                df_main.drop(columns=['presencas_from_pres'], inplace=True, errors='ignore')
            elif 'presencas' not in df_main.columns:
                df_main['presencas'] = 0

            # 7. Cleanup de colunas temporárias e verificação de integridade
            df_main.drop(columns=['_merge_date', '_merge_uc', '_merge_turno'], inplace=True, errors='ignore')

            matched = (df_main['presencas'] > 0).sum()
            logger.info(f"  Presenças cruzadas com sucesso: {matched:,}/{len(df_main):,}")

            if len(df_main) != pre_len:
                logger.warning(f"  CORREÇÃO: Removendo duplicados gerados pelo merge semântico...")
                df_main = df_main.sort_values('presencas', ascending=False).drop_duplicates(
                    subset=['data_inicio', 'espaco', 'codigo_unidade_curricular', 'turno_extraido'],
                    keep='first'
                )

    # =====================================================================
    # FASE C: COMPLIANCE - MAPEAMENTO PARA SCHEMA DW
    # =====================================================================
    logger.info("--- FASE 3: COMPLIANCE (Mapping para Star Schema) ---")

    db_mapping = {
        'edificio': 'Edificio', 'espaco': 'Nome_Espaco', 'unidade_respon': 'Unidade_Responsavel',
        'codigo_unidade_curricular': 'Codigo_UC', 'designacao_unidade_curricular': 'Designacao_UC',
        'ciclo_estudo': 'Ciclo_Estudo', 'pessoa_resp': 'Nome_Responsavel',
        'turno_extraido': 'Designacao_Turno', 'tipo': 'Designacao_Atividade',
        'estado': 'Estado', 'duracao_minutos': 'Duracao_Minutos',
        'presencas': 'Numero_Presencas', 'flag_evento_agregado': 'Flag_Evento_Agregado',
        'data_inicio': 'DataInicio', 'data_fim': 'DataFim', 'identificador': 'SourceID'
    }

    rename_map = {k: v for k, v in db_mapping.items() if k in df_main.columns}
    df_main.rename(columns=rename_map, inplace=True)

    # =====================================================================
    # FASE SANITÁRIA: AUDITORIA E TRATAMENTO DE NULOS
    # =====================================================================
    logger.info("--- FASE 3.5: AUDITORIA PRÉ-LOAD ---")

    # Tratamento de IDs para evitar "Float Poisoning" (ex: 20558.0 -> 20558)
    if 'Codigo_UC' in df_main.columns:
        df_main['Codigo_UC'] = pd.to_numeric(df_main['Codigo_UC'], errors='coerce').fillna(0).astype(int).astype(str)
        df_main['Codigo_UC'] = df_main['Codigo_UC'].replace({'0': 'SEM_UNIDADE / RESERVA_ADMIN'})

    # Imputação de valores padrão para Dimensões (Garantir integridade referencial)
    dim_defaults = {
        'Edificio': 'Edificio Desconhecido', 'Nome_Espaco': 'Espaco Desconhecido',
        'Unidade_Responsavel': 'Indefinido/N.D.', 'Designacao_UC': 'SEM_UNIDADE / RESERVA_ADMIN',
        'Ciclo_Estudo': 'N/D', 'Nome_Responsavel': 'Indefinido/N.D.',
        'Designacao_Turno': 'N/D', 'Designacao_Atividade': 'N/D', 'Estado': 'N/D',
    }
    for col, default in dim_defaults.items():
        if col in df_main.columns:
            df_main[col] = df_main[col].fillna(default).replace({'nan': default, '<NA>': default, '': default})

    # Validação final de nulos
    null_report = df_main.isnull().sum()
    if null_report.sum() == 0:
        logger.info("  Integridade confirmada: Zero valores nulos no DataFrame.")

    # =====================================================================
    # FASE L: CARREGAMENTO (Load - MySQL)
    # =====================================================================
    logger.info("--- FASE 4: CARREGAMENTO (MySQL) ---")

    from load import DataLoader
    loader = DataLoader()

    # 1. Geração de Dimensões Estáticas e Dummy Records
    logger.info("[STEP 0] Populando Dimensões de Tempo e Auxiliares...")
    loader.generate_date_dimension()
    loader.generate_hour_dimension()
    loader.ensure_dummy_dimension_records()

    # 2. Cálculo de Surrogate Keys (SKs) Temporais
    logger.info("[STEP 1-2] Calculando SK_Data e SK_Hora...")
    if 'DataInicio' in df_main.columns:
        data_dt = pd.to_datetime(df_main['DataInicio'], errors='coerce')
        df_main['SK_Data'] = data_dt.dt.strftime('%Y%m%d').fillna('0').astype(int)
        df_main['SK_Hora_Inicio'] = (data_dt.dt.hour * 100 + data_dt.dt.minute).fillna(0).astype(int)
    
    if 'DataFim' in df_main.columns:
        fim_dt = pd.to_datetime(df_main['DataFim'], errors='coerce')
        df_main['SK_Hora_Fim'] = (fim_dt.dt.hour * 100 + fim_dt.dt.minute).fillna(0).astype(int)

    # 3. Mapeamento e Lookup de Dimensões
    logger.info("[STEP 4] Sincronizando Dimensões no Data Warehouse...")
    
    dimensions_to_load = [
        ("Dim_Espaco", ['Edificio', 'Nome_Espaco', 'Unidade_Responsavel', 'is_online'], 'SK_Espaco'),
        ("Dim_Unidade_Curricular", ['Codigo_UC', 'Designacao_UC', 'Ciclo_Estudo'], 'SK_Unidade_Curricular'),
        ("Dim_Responsavel", ['Nome_Responsavel'], 'SK_Responsavel'),
        ("Dim_Turno", ['Designacao_Turno'], 'SK_Turno'),
        ("Dim_Tipo_Atividade", ['Designacao_Atividade'], 'SK_Tipo_Atividade'),
        ("Dim_Estado_Agendamento", ['Estado'], 'SK_Estado_Agendamento')
    ]

    for table, keys, sk in dimensions_to_load:
        if all(k in df_main.columns for k in keys):
            logger.info(f"  -> {table}")
            df_main = loader.load_dimension(df_main, table, keys, sk)

    # 5. Geração Dinâmica de ID_Ocupacao
    logger.info("[STEP 5] Gerando Identificadores Únicos (PK)...")
    if 'SourceID' in df_main.columns:
        # Usa o ID original da fonte, garantindo que é string e sem decimais
        df_main['ID_Ocupacao'] = pd.to_numeric(df_main['SourceID'], errors='coerce').fillna(0).astype(int).astype(str)
        # Substitui zeros por um ID composto para evitar duplicados em registos sem ID original
        mask_zero = df_main['ID_Ocupacao'] == '0'
        if mask_zero.any():
            df_main.loc[mask_zero, 'ID_Ocupacao'] = (
                df_main['SK_Data'].astype(str) + "_" + 
                df_main['SK_Hora_Inicio'].astype(str) + "_" + 
                df_main['SK_Espaco'].astype(str)
            )
    else:
        # Fallback: Gera chave composta única baseada em Data + Hora + Espaço
        df_main['ID_Ocupacao'] = (
            df_main['SK_Data'].astype(str) + "_" + 
            df_main['SK_Hora_Inicio'].astype(str) + "_" + 
            df_main['SK_Espaco'].astype(str)
        )

    # 4. Carregamento da Tabela de Factos
    logger.info("[STEP 6] Carregando Facto_Ocupacao...")
    df_payload = loader.prepare_fact_payload(df_main)
    loader.load_fact(df_payload)

    logger.info("=" * 70)
    logger.info("  >> PROCESSO CONCLUÍDO - DADOS DISPONÍVEIS PARA DASHBOARD <<")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()