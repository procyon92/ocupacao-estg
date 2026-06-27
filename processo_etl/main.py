import logging
import sys
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


def setup_logger():
    # Configura logging para consola e ficheiro — o ficheiro inclui timestamp no nome
    log_format   = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format  = '%Y-%m-%d %H:%M:%S'
    log_filename = datetime.now().strftime("dumpETL_%Y%m%d_%H%M%S.log")

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),                                          # consola
            logging.FileHandler(log_filename, mode="w", encoding="utf-8"),    # ficheiro
        ]
    )
    return logging.getLogger("ETL_Orchestrator")


def main():
    logger = setup_logger()

    logger.info("=" * 70)
    logger.info("  ETL PIPELINE v4.0 — Data Warehouse Ocupação ESTG")
    logger.info("  Modelo Dimensional (Star Schema)")
    logger.info("=" * 70)

    # Fase 1: Extração
    logger.info("--- FASE 1: EXTRAÇÃO ---")
    from extract import DataExtractor

    extractor = DataExtractor(base_path="Dados")

    df_agendamentos = extractor.extract_csv("PorSalaTurno.csv",       sep=",",  encoding="cp1252")
    df_presencas    = extractor.extract_csv("PorTurnoPresencas.csv",  sep=",",  encoding="cp1252")
    df_cursos       = extractor.extract_csv("curso_ucs(in).csv",      sep=";",  encoding="latin-1")

    # Extrai os turnos do dump SQL — as colunas esperadas têm de corresponder exatamente ao schema
    target_table_name = "turnos"
    expected_cols_stg = [
        "id", "desig_edf", "espaco", "datainicio", "datafim",
        "unidade_respon", "tipo", "cod_disc", "nome_disci",
        "ciclo", "descricao", "estado", "pessoa_resp"
    ]
    df_stg = extractor.extract_sql_dump(
        filename="script_espacos_salas_turnos.sql",
        table_name=target_table_name,
        expected_columns=expected_cols_stg
    )

    if df_agendamentos is None or df_stg is None:
        logger.critical("FALHA CRÍTICA: Fontes de agendamento não carregadas.")
        sys.exit(1)

    logger.info(
        f"Volumes: Agendamentos={len(df_agendamentos):,} | "
        f"Presenças={len(df_presencas) if df_presencas is not None else 0:,} | "
        f"Cursos={len(df_cursos) if df_cursos is not None else 0:,}"
    )

    # Fase 2: Transformação
    logger.info("--- FASE 2: TRANSFORMAÇÃO ---")
    from transform import DataTransformer

    transformer = DataTransformer()

    # Dimensão Data gerada de forma autónoma — não depende dos ficheiros de origem
    df_dim_data = transformer.build_date_dimension(start_date='2018-01-01', end_date='2035-12-31')

    # Pipeline principal: limpeza + enriquecimento + alinhamento de schema
    df_transformed = transformer.apply_pipeline(
        df_main=df_agendamentos,
        df_cursos=df_cursos,
        df_presencas=df_presencas,
        df_stg=df_stg
    )

    if df_transformed is None or df_transformed.empty:
        logger.critical("FALHA CRÍTICA: Transformação resultou em DataFrame vazio.")
        sys.exit(1)

    # Fase 3: Carregamento
    logger.info("--- FASE 3: CARREGAMENTO (MySQL) ---")
    from load import DataLoader

    loader = DataLoader()

    # Step 1 — Garante que os dummies SK=0 existem antes de qualquer FK
    logger.info("[STEP 1] Inicializando Dimensões Estáticas...")
    loader.ensure_dummy_dimension_records()

    # Step 2 — Dim_Hora e Dim_Data têm PK fixa (não AUTO_INCREMENT)
    logger.info("[STEP 2] Carregando Dim_Hora e Dim_Data...")
    df_dim_hora = transformer.build_hour_dimension()
    loader.load_fixed_pk_dimension(df_dim_hora, "Dim_Hora", "SK_Hora")
    loader.load_fixed_pk_dimension(df_dim_data, "Dim_Data", "SK_Data")

    # Step 3 — Dimensões dinâmicas: SCD2 para as que têm histórico, SCD1 para as restantes
    logger.info("[STEP 3] Sincronizando Dimensões Dinâmicas...")
    dimensions = [
        ("Dim_Espaco",             ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Escola_Responsavel', 'is_online'], 'SK_Espaco'),
        ("Dim_Unidade_Curricular", ['Codigo_UC', 'Designacao_UC', 'Ciclo_Estudo'],                                    'SK_Unidade_Curricular'),
        ("Dim_Curso",              ['Codigo_Curso', 'Nome_Curso'],                                                     'SK_Curso'),
        ("Dim_Responsavel",        ['Docente_Responsavel'],                                                            'SK_Responsavel'),
        ("Dim_Turno",              ['Designacao_Turno'],                                                               'SK_Turno'),
        ("Dim_Tipo_Atividade",     ['Designacao_Atividade'],                                                           'SK_Tipo_Atividade'),
        ("Dim_Estado_Agendamento", ['Estado'],                                                                         'SK_Estado_Agendamento'),
        ("Dim_Epoca",              ['Descricao_Epoca'],                                                                'SK_Epoca'),
    ]

    scd2_tables = ["Dim_Espaco", "Dim_Unidade_Curricular", "Dim_Curso"]

    for table, keys, sk in dimensions:
        if all(k in df_transformed.columns for k in keys):
            logger.info(f"  -> Processando {table}...")
            if table in scd2_tables:
                df_transformed = loader.load_dimension_scd2(df_transformed, table, keys, sk)
            else:
                df_transformed = loader.load_dimension_scd1(df_transformed, table, keys, sk)

    # Step 4 — Prepara e carrega a tabela de factos
    logger.info("[STEP 4] Preparando e Carregando Facto_Ocupacao...")
    df_payload = loader.prepare_fact_payload(df_transformed)
    loader.print_quality_metrics(df_payload)
    loader.load_fact(df_payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Regista o traceback completo no log antes de terminar
        logging.getLogger("ETL_Orchestrator").critical(
            "ERRO NÃO APANHADO — pipeline terminado inesperadamente.",
            exc_info=True
        )
        sys.exit(1)