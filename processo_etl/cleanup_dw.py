import os
import sys
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("Cleanup")


def get_engine():
    # Lê as credenciais do .env — nunca hardcoded no código
    user     = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    host     = os.getenv('DB_HOST', 'localhost')
    port     = os.getenv('DB_PORT', '3306')
    db_name  = os.getenv('DB_NAME', 'dw_ocupacao')
    return create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}", future=True)


def migrate_schema(engine):
    # Adiciona colunas novas se ainda não existirem — seguro de correr várias vezes
    logger.info("A verificar/migrar colunas novas no schema...")
    with engine.begin() as conn:
        for stmt in [
            "ALTER TABLE Dim_Espaco ADD COLUMN Departamento VARCHAR(60) DEFAULT 'N/D' AFTER is_online",
            "ALTER TABLE Dim_Data ADD COLUMN Numero_Semana_Escolar INT DEFAULT 0 AFTER Tipo_Dia",
        ]:
            try:
                conn.execute(text(stmt))
                logger.info(f"  [OK] {stmt.split('ADD')[1].split('AFTER')[0].strip()}")
            except Exception:
                logger.info(f"  [SKIP] Coluna já existe ou erro ignorado.")


def reset_dw():
    engine = get_engine()
    migrate_schema(engine)
    conn = engine.connect()
    try:
        logger.info("A iniciar limpeza do Data Warehouse...")

        # Desativa as foreign keys para poder truncar as tabelas sem erros de integridade
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))

        tables = [
            'facto_ocupacao', 'dim_espaco', 'dim_unidade_curricular',
            'dim_responsavel', 'dim_turno', 'dim_tipo_atividade',
            'dim_estado_agendamento', 'dim_curso', 'dim_data', 'dim_hora', 'dim_epoca'
        ]
        for tbl in tables:
            try:
                conn.execute(text(f"TRUNCATE TABLE {tbl};"))
                logger.info(f"  [OK] {tbl} limpa.")
            except Exception as e:
                logger.warning(f"  [SKIP] {tbl}: {e}")

        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        conn.commit()

        # Reposição dos Dummy Records (SK=0) — registos especiais para factos sem dimensão conhecida
        logger.info("A repor registos de integridade (SK=0)...")
        # NO_AUTO_VALUE_ON_ZERO permite inserir explicitamente SK=0
        conn.execute(text("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';"))

        dummies = [
            "INSERT IGNORE INTO dim_espaco (SK_Espaco, Edificio, Nome_Espaco, Categoria_Espaco, Escola_Responsavel, is_online, Departamento, Valid_From, Valid_To, Is_Active) VALUES (0, 'N/D', 'N/D', 'N/D', 'N/D', 0, 'N/D', '1900-01-01', '9999-12-31', 1)",
            "INSERT IGNORE INTO dim_unidade_curricular (SK_Unidade_Curricular, Codigo_UC, Designacao_UC, Ciclo_Estudo, Valid_From, Valid_To, Is_Active) VALUES (0, 'N/D', 'N/D', 'N/D', '1900-01-01', '9999-12-31', 1)",
            "INSERT IGNORE INTO dim_curso (SK_Curso, Codigo_Curso, Nome_Curso, Valid_From, Valid_To, Is_Active) VALUES (0, 'N/D', 'N/D', '1900-01-01', '9999-12-31', 1)",
            "INSERT IGNORE INTO dim_responsavel (SK_Responsavel, Docente_Responsavel) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_tipo_atividade (SK_Tipo_Atividade, Designacao_Atividade) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_estado_agendamento (SK_Estado_Agendamento, Estado) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_turno (SK_Turno, Designacao_Turno) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_epoca (SK_Epoca, Descricao_Epoca) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_data (SK_Data, DataCompleta, Ano, Ano_Escolar, Mes, Numero_Semana, Dia, DiaSemana, Semestre, Tipo_Dia, Numero_Semana_Escolar) VALUES (0, '1900-01-01', 1900, 'N/D', 1, 0, 1, 'N/D', 0, 'N/D', 0)",
            "INSERT IGNORE INTO dim_hora (SK_Hora, Hora, Minuto) VALUES (0, 0, 0)"
        ]
        for d in dummies:
            conn.execute(text(d))

        conn.commit()
        logger.info("Estado inicial do DW reposto com sucesso.")

    except Exception as e:
        logger.error(f"FALHA NO CLEANUP: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    reset_dw()