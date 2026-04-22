import os
import pandas as pd
import logging
from sqlalchemy import create_engine, text
from typing import List
from dotenv import load_dotenv

# Carrega as variáveis definidas no ficheiro .env para a memória do sistema
load_dotenv()

class DataLoader:
    """
    Camada de Carregamento (Load) do Pipeline ETL.
    Responsável por materializar o Modelo Dimensional no MySQL.
    Gere a criação de Surrogate Keys (SK), população de Dimensões (Estáticas e Dinâmicas)
    e inserção em lote (chunking) da Tabela de Factos.
    """
    
    def __init__(self, host=None, user=None, password=None, db_name=None, port=None):
        """Inicializa a ligação à base de dados MySQL utilizando variáveis de ambiente (.env)."""
        # Prioriza argumentos passados manualmente; caso contrário, lê do .env
        self.host = host or os.getenv('DB_HOST', 'localhost')
        self.user = user or os.getenv('DB_USER', 'root')
        self.password = password or os.getenv('DB_PASSWORD', '')
        self.db_name = db_name or os.getenv('DB_NAME', 'dw_ocupacao')
        self.port = port or os.getenv('DB_PORT', '3306')

        # Construção dinâmica da string de conexão
        self.connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
        self.engine = create_engine(self.connection_string, future=True)
        self.logger = logging.getLogger(__name__)

    def _get_connection(self):
        """Método auxiliar para abrir uma conexão gerida pelo motor SQLAlchemy."""
        return self.engine.connect()

    # =========================================================================
    # GERAÇÃO DE DIMENSÕES TEMPORAIS (Estáticas)
    # =========================================================================
    def generate_date_dimension(self, start_date='2018-01-01', end_date='2035-12-31'):
        """
        Gera a Dim_Data autonomamente no Python sem depender das fontes de extração.
        Calcula atributos de negócio específicos do domínio académico (Ano Letivo, Semestres).
        """
        self.logger.info("A fabricar a Dimensao Data...")
        date_range = pd.date_range(start=start_date, end=end_date)
        df_dates = pd.DataFrame({'DataCompleta': date_range})
        
        # A Surrogate Key da Data é gerada no formato Smart Key (YYYYMMDD)
        df_dates['SK_Data'] = df_dates['DataCompleta'].dt.strftime('%Y%m%d').astype(int)
        df_dates['DataCompleta'] = df_dates['DataCompleta'].dt.date
        df_dates['Ano'] = df_dates['DataCompleta'].apply(lambda x: x.year)
        df_dates['Mes'] = df_dates['DataCompleta'].apply(lambda x: x.month)
        df_dates['Dia'] = df_dates['DataCompleta'].apply(lambda x: x.day)
        
        # Regra de negócio: O ano letivo começa em setembro
        def get_ano_letivo(row):
            if row['Mes'] >= 9:
                return f"{row['Ano']}/{row['Ano']+1}"
            else:
                return f"{row['Ano']-1}/{row['Ano']}"
        df_dates['Ano_Letivo'] = df_dates.apply(get_ano_letivo, axis=1)

        # Regra de negócio: Divisão semestral da ESTG
        def get_semestre(mes):
            if mes in [9, 10, 11, 12, 1, 2]:
                return 1
            elif mes in [3, 4, 5, 6, 7]:
                return 2
            else:
                return 0
        df_dates['Semestre'] = df_dates['Mes'].apply(get_semestre)

        # Mapeamento do Dia da Semana em Português
        day_names_pt = {0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira', 3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'}
        dow_series = pd.to_datetime(df_dates['DataCompleta']).dt.dayofweek.fillna(-1).astype(int)
        df_dates['DiaSemana'] = dow_series.map(day_names_pt).fillna('Semana N/A')
        
        # Inserção apenas de registos novos (Incremental Load)
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
    # DIMENSÃO HORA
    # =========================================================================
    def generate_hour_dimension(self):
        """
        Gera a matriz da Dim_Hora, com granularidade ao minuto (1440 registos por dia).
        A Surrogate Key é formatada em HHMM (ex: 1430 para 14h30m).
        """
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
    # DUMMY RECORDS (ID=0) - GESTÃO DE DADOS AUSENTES
    # =========================================================================
    def ensure_dummy_dimension_records(self):
        """
        Garante a existência do registo SK=0 em todas as dimensões.
        Prática fundamental para assegurar a Integridade Referencial quando
        existem dados em falta (Missing Values) ou dados de chegada tardia (Late Arriving Data).
        """
        conn = self._get_connection()
        try:
            self.logger.info("A inserir Dummies (SK=0)...")
            # Permite ao MySQL inserir o valor exato '0' em colunas AUTO_INCREMENT
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
            conn.rollback() # Garante rollback em caso de falha de transação
        finally:
            conn.close()

    # =========================================================================
    # CARREGAMENTO DE DIMENSÕES DINÂMICAS E LOOKUP DE SKS
    # =========================================================================
    def load_dimension(self, df: pd.DataFrame, table_name: str, natural_keys: List[str], sk_name: str) -> pd.DataFrame:
        """
        Gere dimensões que dependem da extração de dados (SCD Type 1 logic).
        1. Extrai combinações únicas de Chaves Naturais (NK) do DataFrame.
        2. Lê a dimensão existente no MySQL para comparar.
        3. Insere apenas os registos novos.
        4. Realiza um 'lookup' completo para recuperar e devolver a Surrogate Key (SK) ao DataFrame principal.
        """
        nk_valid = [k for k in natural_keys if k in df.columns]
        if not nk_valid:
            self.logger.warning(f"[{table_name}] No valid NKs found. SK=0.")
            df[sk_name] = 0
            return df
        
        # [CORREÇÃO]: Garante tipos consistentes evitando casting de booleanos para string
        for col in nk_valid:
            if col == 'is_online' or df[col].dtype == bool:
                df[col] = df[col].fillna(False).astype(int) # Converte True/False para 1/0
            else:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace({'nan': 'N/D', '<NA>': 'N/D', '': 'N/D', 'None': 'N/D'})
        
        # Extrai os registos únicos para a dimensão em causa
        dim_df = df[nk_valid].drop_duplicates().copy()
        
        conn = self._get_connection()
        try:
            # 1. Leitura do estado atual da base de dados
            select_cols = [sk_name] + nk_valid
            try:
                existing_df = pd.read_sql(f"SELECT * FROM {table_name.lower()}", conn)
            except Exception:
                existing_df = pd.DataFrame()
            
            # Mapeamento de colunas (Case-insensitive para mitigar problemas OS-MySQL)
            if not existing_df.empty:
                col_map = {}
                for mysql_col in existing_df.columns:
                    for expected_col in select_cols:
                        if mysql_col.lower() == expected_col.lower():
                            col_map[mysql_col] = expected_col
                            break
                existing_df = existing_df.rename(columns=col_map)
            
            # Mantém apenas as colunas relevantes
            keep_cols = [c for c in select_cols if c in existing_df.columns]
            if keep_cols:
                existing_df = existing_df[keep_cols].copy()
            
            # [CORREÇÃO]: Limpeza de espaços e normalização de tipos nos registos lidos do MySQL
            for col in nk_valid:
                if col in existing_df.columns:
                    if col == 'is_online' or existing_df[col].dtype == bool:
                        existing_df[col] = existing_df[col].fillna(0).astype(int)
                    else:
                        existing_df[col] = existing_df[col].astype(str).str.strip()
            
            # 2. Identificação de novos registos via Left Join Semântico
            if not existing_df.empty and sk_name in existing_df.columns:
                check_merge = pd.merge(dim_df, existing_df[nk_valid], on=nk_valid, how='left', indicator=True)
                new_records = check_merge[check_merge['_merge'] == 'left_only'][nk_valid].copy()
            else:
                new_records = dim_df.copy()
            
            # 3. Inserção de novos registos na Dimensão
            if not new_records.empty:
                insert_df = new_records[nk_valid].copy()
                for col in nk_valid:
                    # Garantir que inserimos inteiros no MySQL e não strings
                    if col == 'is_online' or insert_df[col].dtype == bool:
                        insert_df[col] = insert_df[col].astype(int)
                    else:
                        insert_df[col] = insert_df[col].astype(str)
                
                insert_df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
                conn.commit()
                self.logger.info(f"[{table_name}] Inseridos {len(insert_df)} novos registos.")
                
                # Relê a dimensão para atualizar o dicionário de SKs com os registos recém inseridos
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
                
                # [CORREÇÃO]: Re-aplicar normalização de tipos pós-leitura
                for col in nk_valid:
                    if col in existing_df.columns:
                        if col == 'is_online' or existing_df[col].dtype == bool:
                            existing_df[col] = existing_df[col].fillna(0).astype(int)
                        else:
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

        # 4. Lookup: Atribuição das SKs ao DataFrame Principal (Facto Pre-load)
        if sk_name in df.columns:
            df = df.drop(columns=[sk_name])
        
        if sk_name in existing_df.columns and len(existing_df) > 0:
            merge_cols = [c for c in nk_valid if c in existing_df.columns]
            lookup = existing_df[merge_cols + [sk_name]].drop_duplicates(subset=merge_cols, keep='first')
            
            self.logger.info(f"  [{table_name}] Merging {len(df):,} rows with {len(lookup):,} dimension records on {merge_cols}")
            df = pd.merge(df, lookup, on=merge_cols, how='left')
            
            matched = df[sk_name].notna() & (df[sk_name] > 0)
            self.logger.info(f"  [{table_name}] Match result: {matched.sum():,}/{len(df):,} ({matched.mean()*100:.1f}%)")
            
            # SK=0 para registos que falharam o mapeamento
            df[sk_name] = df[sk_name].fillna(0).astype(int)
        else:
            df[sk_name] = 0
        
        return df

    # =========================================================================
    # PREPARE FACT PAYLOAD (Estruturação Final)
    # =========================================================================
    def prepare_fact_payload(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra o DataFrame retendo apenas as Surrogate Keys e as Métricas do Facto.
        Garante tipagem rigorosa para evitar falhas de Foreign Key no MySQL.
        """
        required_sks = [
            'SK_Data', 'SK_Hora_Inicio', 'SK_Hora_Fim', 
            'SK_Espaco', 'SK_Unidade_Curricular', 'SK_Curso', 
            'SK_Responsavel', 'SK_Tipo_Atividade', 'SK_Estado_Agendamento', 'SK_Turno'
        ]
        
        # Garante as SKs como inteiros
        for sk in required_sks:
            if sk not in df.columns:
                df[sk] = 0
            df[sk] = pd.to_numeric(df[sk], errors='coerce').fillna(0).astype(int)

        # Garante Chave e Métricas
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
    # LOAD FACT TABLE (Inserção Segmentada)
    # =========================================================================
    def load_fact(self, df_fact: pd.DataFrame, table_name: str = "Facto_Ocupacao", chunk_size: int = 5000):
        """
        Carrega a Tabela de Factos verificando a linhagem (ID_Ocupacao) para evitar duplicação.
        Utiliza inserção em lote (chunking) por questões de performance.
        """
        conn = self._get_connection()
        try:
            # Desativa FK Temporariamente para performance extrema no Bulk Insert
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            
            # Recupera IDs existentes para efetuar carga estritamente incremental
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
    # AUDITORIA E LOGGING
    # =========================================================================
    def print_quality_metrics(self, df: pd.DataFrame):
        """Produz logs de auditoria detalhados sobre o mapeamento das SKs."""
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