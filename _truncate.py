"""
Pre-flight: Truncate Facto_Ocupacao for clean re-load.
Run this once before the main ETL if you need a fresh start.
"""
from sqlalchemy import create_engine, text
import sys

engine = create_engine("mysql+pymysql://root:dbsecret@localhost:3306/dw_ocupacao", future=True)
conn = engine.connect()
try:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE Facto_Ocupacao;"))
    # Also truncate dimensions populated by ETL (not Dim_Data/Dim_Hora which are autonomous)
    for tbl in ['Dim_Espaco', 'Dim_Unidade_Curricular', 'Dim_Responsavel', 
                'Dim_Turno', 'Dim_Tipo_Atividade', 'Dim_Estado_Agendamento', 'Dim_Curso']:
        try:
            conn.execute(text(f"TRUNCATE TABLE {tbl};"))
        except:
            pass
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("OK: All tables truncated for fresh ETL run.")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    conn.close()
