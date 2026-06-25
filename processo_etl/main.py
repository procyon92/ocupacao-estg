"""
main.py — Orquestrador do Pipeline ETL
Plataforma para a Análise da Ocupação de Espaços Letivos (ESTG)

Coordena a execução sequencial das fases Extract → Transform → Load.
Não contém lógica de transformação ou negócio.
"""
import logging
import sys
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


def setup_logger():
    """Configuração do sistema de logging para auditoria do processo."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    log_filename = datetime.now().strftime("dumpETL_%Y%m%d_%H%M%S.log")

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),                                                # consola
            logging.FileHandler(log_filename, mode="w", encoding="utf-8"),         # ficheiro log
        ]
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
    
    # CORREÇÃO 1: Utilização do conector genérico CSV com inferência de encoding padrão.
    # Nota: Confirmar se o separador real é ',' ou ';' para este dataset.
    df_cursos       = extractor.extract_csv("curso_ucs(in).csv", sep=";", encoding="latin-1")
    
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

    # 2. Dim_Hora e Dim_Data (PK fixa — método dedicado)
    logger.info("[STEP 2] Carregando Dim_Hora e Dim_Data...")
    df_dim_hora = transformer.build_hour_dimension()
    loader.load_fixed_pk_dimension(df_dim_hora, "Dim_Hora", "SK_Hora")
    loader.load_fixed_pk_dimension(df_dim_data, "Dim_Data", "SK_Data")

    # 3. Dimensões Dinâmicas (Misto SCD1 / SCD2)
    logger.info("[STEP 3] Sincronizando Dimensões Dinâmicas...")
    
    # Atualizado conforme schema_dw.sql
    dimensions = [
        ("Dim_Espaco",                ['Edificio', 'Nome_Espaco', 'Categoria_Espaco', 'Escola_Responsavel', 'is_online'], 'SK_Espaco'),
        ("Dim_Unidade_Curricular",    ['Codigo_UC', 'Designacao_UC', 'Ciclo_Estudo'],                 'SK_Unidade_Curricular'),
        ("Dim_Curso",                 ['Codigo_Curso', 'Nome_Curso'],                                 'SK_Curso'),
        ("Dim_Responsavel",           ['Docente_Responsavel'],                                        'SK_Responsavel'),
        ("Dim_Turno",                 ['Designacao_Turno'],                                           'SK_Turno'),
        ("Dim_Tipo_Atividade",        ['Designacao_Atividade'],                                       'SK_Tipo_Atividade'),
        ("Dim_Estado_Agendamento",    ['Estado'],                                                     'SK_Estado_Agendamento'),
        ("Dim_Epoca",                 ['Descricao_Epoca'],                                            'SK_Epoca') # Adicionado
    ]

    scd2_tables = ["Dim_Espaco", "Dim_Unidade_Curricular", "Dim_Curso"]

    for table, keys, sk in dimensions:
        if all(k in df_transformed.columns for k in keys):
            logger.info(f"  -> Processando {table}...")
            if table in scd2_tables:
                df_transformed = loader.load_dimension_scd2(df_transformed, table, keys, sk)
            else:
                df_transformed = loader.load_dimension_scd1(df_transformed, table, keys, sk)

    # 4. Preparação e Carga da Facto
    logger.info("[STEP 4] Preparando e Carregando Facto_Ocupacao...")
    # O loader.prepare_fact_payload deve agora garantir a inclusão de SK_Epoca
    df_payload = loader.prepare_fact_payload(df_transformed)
    loader.print_quality_metrics(df_payload)
    loader.load_fact(df_payload)


if __name__ == "__main__":
    main()