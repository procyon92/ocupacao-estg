import pandas as pd
import logging
from sqlalchemy import create_engine, text
from typing import List

class DataLoader:
    def __init__(self, host="localhost", user="root", password="dbsecret", db_name="dw_ocupacao", port=3306):
        self.connection_string = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
        self.engine = create_engine(self.connection_string, future=True)
        self.logger = logging.getLogger(__name__)

    def _get_connection(self):
        return self.engine.connect()

    # =========================================================================
    # DIMENSAO DATA
    # =========================================================================
    def generate_date_dimension(self, start_date='2018-01-01', end_date='2035-12-31'):
        self.logger.info("A fabricar a Dimensao Data...")
        date_range = pd.date_range(start=start_date, end=end_date)
        df_dates = pd.DataFrame({'DataCompleta': date_range})
        df_dates['SK_Data'] = df_dates['DataCompleta'].dt.strftime('%Y%m%d').astype(int)
        df_dates['DataCompleta'] = df_dates['DataCompleta'].dt.date
        df_dates['Ano'] = df_dates['DataCompleta'].apply(lambda x: x.year)
        df_dates['Mes'] = df_dates['DataCompleta'].apply(lambda x: x.month)
        df_dates['Dia'] = df_dates['DataCompleta'].apply(lambda x: x.day)
        
        def get_ano_letivo(row):
            if row['Mes'] >= 9:
                return f"{row['Ano']}/{row['Ano']+1}"
            else:
                return f"{row['Ano']-1}/{row['Ano']}"
        df_dates['Ano_Letivo'] = df_dates.apply(get_ano_letivo, axis=1)

        def get_semestre(mes):
            if mes in [9, 10, 11, 12, 1, 2]:
                return 1
            elif mes in [3, 4, 5, 6, 7]:
                return 2
            else:
                return 0
        df_dates['Semestre'] = df_dates['Mes'].apply(get_semestre)

        day_names_pt = {0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira', 3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'}
        # Avoiding nulls by filling missing with 0 safely (though pd.date_range shouldn't have missing dates)
        dow_series = pd.to_datetime(df_dates['DataCompleta']).dt.dayofweek.fillna(-1).astype(int)
        df_dates['DiaSemana'] = dow_series.map(day_names_pt).fillna('Semana N/A')
        
        conn = self._get_connection()
        try:
            existing = pd.read_sql("SELECT SK_Data FROM dim_data", conn)['SK_Data'].values
            novos = df_dates[~df_dates['SK_Data'].isin(existing)]
            if not novos.empty:
                novos.to_sql('dim_data', conn, if_exists='append', index=False)
                conn.commit()
                self.logger.info(f"[Dim_Data] {len(novos)} datas geradas.")
            else:
                self.logger.info("[Dim_Data] Ja populado.")
        except Exception as e:
            self.logger.error(f"Falha Dim_Data: {e}")
        finally:
            conn.close()

    # =========================================================================
    # DIMENSAO HORA
    # =========================================================================
    def generate_hour_dimension(self):
        self.logger.info("A fabricar a Dimensao Hora...")
        rows = []
        for h in range(24):
            for m in range(60):
                rows.append({'SK_Hora': h * 100 + m, 'Hora': h, 'Minuto': m})
        df_hours = pd.DataFrame(rows)
        
        conn = self._get_connection()
        try:
            existing = pd.read_sql("SELECT SK_Hora FROM Dim_Hora", conn)['SK_Hora'].values
            novos = df_hours[~df_hours['SK_Hora'].isin(existing)]
            if not novos.empty:
                novos.to_sql('Dim_Hora', conn, if_exists='append', index=False)
                conn.commit()
                self.logger.info(f"[Dim_Hora] {len(novos)} registos horarios gerados.")
            else:
                self.logger.info("[Dim_Hora] Ja populado.")
        except Exception as e:
            self.logger.error(f"Falha Dim_Hora: {e}")
        finally:
            conn.close()

    # =========================================================================
    # DUMMY RECORDS (ID=0)
    # =========================================================================
    def ensure_dummy_dimension_records(self):
        conn = self._get_connection()
        try:
            self.logger.info("A inserir Dummies (SK=0)...")
            # The NO_AUTO_VALUE_ON_ZERO prevents MySQL from issuing SK=1,2,3 for these dimensions!
            conn.execute(text("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';"))
            queries = [
                "INSERT IGNORE INTO Dim_Data (SK_Data, DataCompleta, Ano, Ano_Letivo, Mes, Dia, DiaSemana, Semestre) VALUES (0, '1900-01-01', 1900, 'N/D', 1, 1, 'N/D', 0)",
                "INSERT IGNORE INTO Dim_Hora (SK_Hora, Hora, Minuto) VALUES (0, 0, 0)",
                "INSERT IGNORE INTO Dim_Espaco (SK_Espaco, Edificio, Nome_Espaco, Unidade_Responsavel, is_online) VALUES (0, 'N/D', 'N/D', 'N/D', 0)",
                "INSERT IGNORE INTO Dim_Unidade_Curricular (SK_Unidade_Curricular, Codigo_UC) VALUES (0, 'N/D')",
                "INSERT IGNORE INTO Dim_Curso (SK_Curso, Codigo_Curso, Nome_Curso) VALUES (0, 'N/D', 'N/D')",
                "INSERT IGNORE INTO Dim_Responsavel (SK_Responsavel, Nome_Responsavel) VALUES (0, 'N/D')",
                "INSERT IGNORE INTO Dim_Tipo_Atividade (SK_Tipo_Atividade, Designacao_Atividade) VALUES (0, 'N/D')",
                "INSERT IGNORE INTO Dim_Estado_Agendamento (SK_Estado_Agendamento, Estado) VALUES (0, 'N/D')",
                "INSERT IGNORE INTO Dim_Turno (SK_Turno, Designacao_Turno) VALUES (0, 'N/D')"
            ]
            for q in queries:
                conn.execute(text(q))
            conn.commit()
            self.logger.info("  Dummies 0 inseridos.")
        except Exception as e:
            self.logger.warning(f"Erro dummy records: {e}")
            conn.rollback() # ensure rollback if anything fails
        finally:
            conn.close()

    # =========================================================================
    # LOAD DIMENSION (SIMPLIFIED & BULLETPROOF)
    # =========================================================================
    def load_dimension(self, df: pd.DataFrame, table_name: str, natural_keys: List[str], sk_name: str) -> pd.DataFrame:
        """
        Simplified dimension loader:
        1. Extract unique NK combinations from DataFrame
        2. Read existing dimension from MySQL (keeping original column names)
        3. Insert new records
        4. Read back ALL records with SKs
        5. Merge SKs into the main DataFrame
        
        IMPORTANT: NO uppercasing — we keep original case and rely on MySQL's
        case-insensitive collation (utf8mb4_general_ci) for matching.
        """
        nk_valid = [k for k in natural_keys if k in df.columns]
        if not nk_valid:
            self.logger.warning(f"[{table_name}] No valid NKs found. SK=0.")
            df[sk_name] = 0
            return df
        
        # Ensure consistent string types (strip whitespace only, NO case change)
        for col in nk_valid:
            df[col] = df[col].astype(str).str.strip()
            # Replace 'nan' and '<NA>' strings with actual empty placeholder
            df[col] = df[col].replace({'nan': 'N/D', '<NA>': 'N/D', '': 'N/D', 'None': 'N/D'})
        
        # Extract unique NK combinations
        dim_df = df[nk_valid].drop_duplicates().copy()
        
        conn = self._get_connection()
        try:
            # Read what's already in MySQL
            # Build SELECT with only the columns we need
            select_cols = [sk_name] + nk_valid
            # Query the dimension table — only select columns that exist
            try:
                # Normaliza query para LOWERCASE eliminando problemas cruzados de OS Sensivity
                existing_df = pd.read_sql(f"SELECT * FROM {table_name.lower()}", conn)
            except Exception:
                existing_df = pd.DataFrame()
            
            # Map MySQL column names to our expected names (case-insensitive)
            if not existing_df.empty:
                col_map = {}
                for mysql_col in existing_df.columns:
                    for expected_col in select_cols:
                        if mysql_col.lower() == expected_col.lower():
                            col_map[mysql_col] = expected_col
                            break
                existing_df = existing_df.rename(columns=col_map)
            
            # Keep only the columns we care about
            keep_cols = [c for c in select_cols if c in existing_df.columns]
            if keep_cols:
                existing_df = existing_df[keep_cols].copy()
            
            # Strip whitespace from existing records for matching
            for col in nk_valid:
                if col in existing_df.columns:
                    existing_df[col] = existing_df[col].astype(str).str.strip()
            
            # Find new records (not already in the dimension)
            if not existing_df.empty and sk_name in existing_df.columns:
                # LEFT JOIN dim_df with existing, keep only non-matched
                check_merge = pd.merge(dim_df, existing_df[nk_valid], on=nk_valid, how='left', indicator=True)
                new_records = check_merge[check_merge['_merge'] == 'left_only'][nk_valid].copy()
            else:
                new_records = dim_df.copy()
            
            # Insert new records
            if not new_records.empty:
                # Only send NK columns (SK is AUTO_INCREMENT)
                insert_df = new_records[nk_valid].copy()
                for col in nk_valid:
                    insert_df[col] = insert_df[col].astype(str)
                insert_df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
                conn.commit()
                self.logger.info(f"[{table_name}] Inseridos {len(insert_df)} novos registos.")
                
                # Re-read full dimension after insert
                existing_df = pd.read_sql(f"SELECT * FROM {table_name.lower()}", conn)
                col_map = {}
                for mysql_col in existing_df.columns:
                    for expected_col in select_cols:
                        if mysql_col.lower() == expected_col.lower():
                            col_map[mysql_col] = expected_col
                            break
                existing_df = existing_df.rename(columns=col_map)
                keep_cols = [c for c in select_cols if c in existing_df.columns]
                if keep_cols:
                    existing_df = existing_df[keep_cols].copy()
                for col in nk_valid:
                    if col in existing_df.columns:
                        existing_df[col] = existing_df[col].astype(str).str.strip()
            else:
                self.logger.info(f"[{table_name}] Nenhum registo novo a inserir.")
                
        except Exception as e:
            self.logger.error(f"[{table_name}] Erro no load_dimension: {e}")
            import traceback
            traceback.print_exc()
            existing_df = pd.DataFrame(columns=[sk_name] + nk_valid)
        finally:
            conn.close()

        # MERGE to assign SKs to main DataFrame
        if sk_name in df.columns:
            df = df.drop(columns=[sk_name])
        
        if sk_name in existing_df.columns and len(existing_df) > 0:
            # Deduplicate the lookup table on NKs (keep first SK)
            merge_cols = [c for c in nk_valid if c in existing_df.columns]
            lookup = existing_df[merge_cols + [sk_name]].drop_duplicates(subset=merge_cols, keep='first')
            
            self.logger.info(f"  [{table_name}] Merging {len(df):,} rows with {len(lookup):,} dimension records on {merge_cols}")
            
            df = pd.merge(df, lookup, on=merge_cols, how='left')
            
            matched = df[sk_name].notna() & (df[sk_name] > 0)
            self.logger.info(f"  [{table_name}] Match result: {matched.sum():,}/{len(df):,} ({matched.mean()*100:.1f}%)")
            
            df[sk_name] = df[sk_name].fillna(0).astype(int)
        else:
            df[sk_name] = 0
        
        return df

    # =========================================================================
    # PREPARE FACT PAYLOAD
    # =========================================================================
    def prepare_fact_payload(self, df: pd.DataFrame) -> pd.DataFrame:
        required_sks = [
            'SK_Data', 'SK_Hora_Inicio', 'SK_Hora_Fim', 
            'SK_Espaco', 'SK_Unidade_Curricular', 'SK_Curso', 
            'SK_Responsavel', 'SK_Tipo_Atividade', 'SK_Estado_Agendamento', 'SK_Turno'
        ]
        for sk in required_sks:
            if sk not in df.columns:
                df[sk] = 0
            df[sk] = pd.to_numeric(df[sk], errors='coerce').fillna(0).astype(int)

        if 'ID_Ocupacao' not in df.columns:
            df['ID_Ocupacao'] = 'DEFAULT_ID'
        
        if 'Duracao_Minutos' not in df.columns:
            df['Duracao_Minutos'] = 0
        df['Duracao_Minutos'] = pd.to_numeric(df['Duracao_Minutos'], errors='coerce').fillna(0).astype(int)

        if 'Numero_Presencas' not in df.columns:
            df['Numero_Presencas'] = 0
        df['Numero_Presencas'] = pd.to_numeric(df['Numero_Presencas'], errors='coerce').fillna(0).astype(int)

        for bool_col in ['Flag_Evento_Agregado']:
            if bool_col not in df.columns:
                df[bool_col] = 0
            df[bool_col] = pd.to_numeric(df[bool_col], errors='coerce').fillna(0).astype(int)
                
        valid_cols = required_sks + ['ID_Ocupacao', 'Duracao_Minutos', 'Numero_Presencas', 'Flag_Evento_Agregado']
        return df[valid_cols].copy()

    # =========================================================================
    # LOAD FACT TABLE
    # =========================================================================
    def load_fact(self, df_fact: pd.DataFrame, table_name: str = "Facto_Ocupacao", chunk_size: int = 5000):
        conn = self._get_connection()
        try:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            
            try:
                existing_ids = set(pd.read_sql(f"SELECT ID_Ocupacao FROM {table_name.lower()}", conn)['ID_Ocupacao'].values)
            except Exception:
                existing_ids = set()

            novos = df_fact[~df_fact['ID_Ocupacao'].isin(existing_ids)].copy()
            
            if novos.empty:
                self.logger.info(f"[{table_name}] Nenhum facto novo.")
            else:
                total = len(novos)
                loaded = 0
                for i in range(0, total, chunk_size):
                    chunk = novos.iloc[i:i+chunk_size]
                    chunk.to_sql(table_name.lower(), conn, if_exists='append', index=False)
                    loaded += len(chunk)
                    if loaded % 10000 == 0 or loaded == total:
                        self.logger.info(f"[{table_name}] Progresso: {loaded:,}/{total:,}")
                
                conn.commit()
                self.logger.info(f"[{table_name}] TOTAL: {total:,} registos carregados.")
                
        except Exception as e:
            self.logger.error(f"[{table_name}] Erro: {e}")
            raise e
        finally:
            try:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
                conn.commit()
            except Exception:
                pass
            conn.close()

    # =========================================================================
    # QUALITY METRICS
    # =========================================================================
    def print_quality_metrics(self, df: pd.DataFrame):
        sk_columns = [c for c in df.columns if c.startswith('SK_')]
        if not sk_columns:
            return
        
        self.logger.info("=" * 60)
        self.logger.info("METRICAS DE QUALIDADE DAS SURROGATE KEYS:")
        self.logger.info("=" * 60)
        
        total = len(df)
        for sk in sk_columns:
            filled = (df[sk] > 0).sum()
            pct = (filled / total * 100) if total > 0 else 0
            self.logger.info(f"  {sk:35s}: {filled:>7,}/{total:>7,} ({pct:6.2f}%)")
        
        all_sks = [c for c in sk_columns if c != 'SK_Data']
        if all_sks:
            overall = (df[all_sks] > 0).mean().mean() * 100
            self.logger.info("-" * 60)
            self.logger.info(f"  {'MEDIA GLOBAL (excl. Data)':35s}: {overall:6.2f}%")
        self.logger.info("=" * 60)
