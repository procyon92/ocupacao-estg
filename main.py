"""
main.py — Orquestrador do Pipeline ETL
Plataforma para a Análise da Ocupação de Espaços Letivos (ESTG)

Coordena a execução sequencial das fases Extract → Transform → Load.
Não contém lógica de transformação ou negócio.
"""
import logging
import sys
from dotenv import load_dotenv

load_dotenv()


def setup_logger():
    """Configuração do sistema de logging para auditoria do processo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("ETL_Orchestrator")


def main():
    logger = setup_logger()

    logger.info("=" * 70)
    logger.info("  ETL PIPELINE v4.0 — Data Warehouse Ocupação ESTG")
    logger.info("  Modelo Dimensional (Star Schema)")
    logger.info("=" * 70)

    # ==================================================================
    # FASE 1: EXTRAÇÃO (Extract)
    # ==================================================================
    logger.info("--- FASE 1: EXTRAÇÃO ---")
    from extract import DataExtractor

    extractor = DataExtractor(base_path="Dados")

    df_agendamentos = extractor.extract_csv("PorSalaTurno.csv", sep=",", encoding="cp1252")
    df_presencas    = extractor.extract_csv("PorTurnoPresencas.csv", sep=",", encoding="cp1252")
    df_cursos       = extractor.extract_courses("curso_ucs(in).csv")
    df_stg          = extractor.extract_sql_staging("script_espacos_salas_turnos.sql")

    if df_agendamentos is None or df_stg is None:
        logger.critical("FALHA CRÍTICA: Fontes de agendamento não carregadas.")
        sys.exit(1)

    logger.info(
        f"Volumes: Agendamentos={len(df_agendamentos):,} | "
        f"Presenças={len(df_presencas) if df_presencas is not None else 0:,} | "
        f"Cursos={len(df_cursos) if df_cursos is not None else 0:,}"
    )

    # ==================================================================
    # FASE 2: TRANSFORMAÇÃO (Transform)
    # ==================================================================
    logger.info("--- FASE 2: TRANSFORMAÇÃO ---")
    from transform import DataTransformer

    transformer = DataTransformer()

    # 1. Dimensão Data (Autónoma — calendário académico)
    df_dim_data = transformer.build_date_dimension(start_date='2018-01-01', end_date='2035-12-31')

    # 2. Pipeline principal: limpeza + enriquecimento + alinhamento schema
    df_transformed = transformer.apply_pipeline(
        df_main=df_agendamentos,
        df_cursos=df_cursos,
        df_presencas=df_presencas,
        df_stg=df_stg
    )

    if df_transformed is None or df_transformed.empty:
        logger.critical("FALHA CRÍTICA: Transformação resultou em DataFrame vazio.")
        sys.exit(1)

    # ==================================================================
    # FASE 3: CARREGAMENTO (Load → MySQL)
    # ==================================================================
    logger.info("--- FASE 3: CARREGAMENTO (MySQL) ---")
    from load import DataLoader

    loader = DataLoader()

    # 1. Dimensões Estáticas e Dummies (SK=0)
    logger.info("[STEP 1] Inicializando Dimensões Estáticas...")
    loader.ensure_dummy_dimension_records()
    loader.generate_hour_dimension()

    # 2. Dimensão Data (PK fixa — método dedicado)
    logger.info("[STEP 2] Carregando Dim_Data...")
    loader.load_date_dimension(df_dim_data)

    # 3. Dimensões Dinâmicas (SCD Tipo 1)
    logger.info("[STEP 3] Sincronizando Dimensões Dinâmicas...")
    dimensions = [
        ("Dim_Espaco",                ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Unidade_Responsavel', 'is_online'], 'SK_Espaco'),
        ("Dim_Unidade_Curricular",    ['Codigo_UC', 'Designacao_UC', 'Ciclo_Estudo'],                 'SK_Unidade_Curricular'),
        ("Dim_Curso",                 ['Codigo_Curso', 'Nome_Curso'],                                 'SK_Curso'),
        ("Dim_Responsavel",           ['Nome_Responsavel'],                                            'SK_Responsavel'),
        ("Dim_Turno",                 ['Designacao_Turno'],                                            'SK_Turno'),
        ("Dim_Tipo_Atividade",        ['Designacao_Atividade'],                                        'SK_Tipo_Atividade'),
        ("Dim_Estado_Agendamento",    ['Estado'],                                                      'SK_Estado_Agendamento'),
    ]

    for table, keys, sk in dimensions:
        if all(k in df_transformed.columns for k in keys):
            logger.info(f"  -> Processando {table}...")
            df_transformed = loader.load_dimension(df_transformed, table, keys, sk)

    # 4. Preparação e Carga da Facto
    logger.info("[STEP 4] Preparando e Carregando Facto_Ocupacao...")
    df_payload = loader.prepare_fact_payload(df_transformed)
    loader.print_quality_metrics(df_payload)
    loader.load_fact(df_payload)

    logger.info("=" * 70)
    logger.info("  >> PIPELINE ETL CONCLUÍDO COM SUCESSO <<")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()