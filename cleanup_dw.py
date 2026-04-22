import os
import sys
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Carrega as configurações do ficheiro .env
load_dotenv()

# Configuração de log
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("Cleanup")

def get_engine():
    """Cria o motor de ligação usando as variáveis de ambiente."""
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_NAME', 'dw_ocupacao')
    
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
    return create_engine(url, future=True)

def reset_dw():
    engine = get_engine()
    conn = engine.connect()
    try:
        logger.info("A iniciar limpeza do Data Warehouse (via .env)...")
        
        # 1. Desativar verificações de integridade
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # 2. Tabelas a limpar (Case-insensitive para garantir compatibilidade)
        tables = [
            'facto_ocupacao', 'dim_espaco', 'dim_unidade_curricular', 
            'dim_responsavel', 'dim_turno', 'dim_tipo_atividade', 
            'dim_estado_agendamento', 'dim_curso'
        ]

        for tbl in tables:
            try:
                conn.execute(text(f"TRUNCATE TABLE {tbl};"))
                logger.info(f"  [OK] Tabela {tbl} limpa.")
            except Exception as e:
                logger.warning(f"  [SKIP] Não foi possível limpar {tbl}: {e}")

        # 3. Reativar verificações
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        conn.commit()
        
        # 4. Reposição dos Dummy Records (Essencial para a integridade do ETL)
        logger.info("A repor registos de integridade (SK=0)...")
        conn.execute(text("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';"))
        
        dummies = [
            "INSERT IGNORE INTO dim_espaco (SK_Espaco, Edificio, Nome_Espaco, Unidade_Responsavel, is_online) VALUES (0, 'N/D', 'N/D', 'N/D', 0)",
            "INSERT IGNORE INTO dim_unidade_curricular (SK_Unidade_Curricular, Codigo_UC) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_curso (SK_Curso, Codigo_Curso, Nome_Curso) VALUES (0, 'N/D', 'N/D')",
            "INSERT IGNORE INTO dim_responsavel (SK_Responsavel, Nome_Responsavel) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_tipo_atividade (SK_Tipo_Atividade, Designacao_Atividade) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_estado_agendamento (SK_Estado_Agendamento, Estado) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO dim_turno (SK_Turno, Designacao_Turno) VALUES (0, 'N/D')"
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