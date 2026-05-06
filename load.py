import os
import pandas as pd
import logging
from sqlalchemy import create_engine, text
from typing import List
from dotenv import load_dotenv

load_dotenv()


class DataLoader:
    """
    Camada de Carregamento (Load) do Pipeline ETL.
    Responsável por materializar o Modelo Dimensional na Base de Dados MySQL.
    Gere Surrogate Keys, população de Dimensões e inserção em lote da Facto.
    """

    def __init__(self, host=None, user=None, password=None, db_name=None, port=None):
        self.host = host or os.getenv('DB_HOST', 'localhost')
        self.user = user or os.getenv('DB_USER', 'root')
        self.password = password or os.getenv('DB_PASSWORD', '')
        self.db_name = db_name or os.getenv('DB_NAME', 'dw_ocupacao')
        self.port = port or os.getenv('DB_PORT', '3306')
        self.connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
        self.engine = create_engine(self.connection_string, future=True)
        self.logger = logging.getLogger(__name__)

    def _get_connection(self):
        return self.engine.connect()

    # =========================================================================
    # DIMENSÃO HORA (Geração Estática — 1440 registos)
    # =========================================================================
    def generate_hour_dimension(self):
        """Gera a Dim_Hora com granularidade ao minuto (SK = HHMM)."""
        self.logger.info("A fabricar a Dim_Hora...")
        rows = [{'SK_Hora': h*100+m, 'Hora': h, 'Minuto': m} for h in range(24) for m in range(60)]
        df_hours = pd.DataFrame(rows)

        conn = self._get_connection()
        try:
            existing = pd.read_sql("SELECT SK_Hora FROM dim_hora", conn)['SK_Hora'].values
            novos = df_hours[~df_hours['SK_Hora'].isin(existing)]
            if not novos.empty:
                novos.to_sql('dim_hora', conn, if_exists='append', index=False)
                conn.commit()
                self.logger.info(f"[Dim_Hora] {len(novos)} registos inseridos.")
            else:
                self.logger.info("[Dim_Hora] Já populado.")
        except Exception as e:
            self.logger.error(f"Falha Dim_Hora: {e}")
        finally:
            conn.close()

    # =========================================================================
    # DUMMY RECORDS (SK=0) — Gestão de Dados Ausentes
    # =========================================================================
    def ensure_dummy_dimension_records(self):
        """Garante a existência do registo SK=0 em todas as dimensões."""
        conn = self._get_connection()
        try:
            self.logger.info("A inserir Dummies (SK=0)...")
            conn.execute(text("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';"))

            queries = [
                "INSERT IGNORE INTO Dim_Data (SK_Data, DataCompleta, Ano, Ano_Letivo, Mes, Numero_Semana, Dia, DiaSemana, Semestre, Epoca_Exame, Tipo_Dia) VALUES (0, '1900-01-01', 1900, 'N/D', 1, 0, 1, 'N/D', 0, 'N/D', 'N/D')",
                "INSERT IGNORE INTO Dim_Hora (SK_Hora, Hora, Minuto) VALUES (0, 0, 0)",
                "INSERT IGNORE INTO Dim_Espaco (SK_Espaco, Edificio, Nome_Espaco, Categoria_Espaco, Unidade_Responsavel, is_online) VALUES (0, 'N/D', 'N/D', 'N/D', 'N/D', 0)",
                "INSERT IGNORE INTO Dim_Unidade_Curricular (SK_Unidade_Curricular, Codigo_UC, Designacao_UC, Ciclo_Estudo) VALUES (0, 'N/D', 'N/D', 'N/D')",
                "INSERT IGNORE INTO Dim_Curso (SK_Curso, Codigo_Curso, Nome_Curso) VALUES (0, 'N/D', 'N/D')",
                "INSERT IGNORE INTO Dim_Responsavel (SK_Responsavel, Nome_Responsavel) VALUES (0, 'N/D')",
                "INSERT IGNORE INTO Dim_Tipo_Atividade (SK_Tipo_Atividade, Designacao_Atividade) VALUES (0, 'N/D')",
                "INSERT IGNORE INTO Dim_Estado_Agendamento (SK_Estado_Agendamento, Estado) VALUES (0, 'N/D')",
                "INSERT IGNORE INTO Dim_Turno (SK_Turno, Designacao_Turno) VALUES (0, 'N/D')"
            ]
            for q in queries:
                conn.execute(text(q))
            conn.commit()
            self.logger.info("  Dummies SK=0 inseridos/validados.")
        except Exception as e:
            self.logger.warning(f"Erro ao inserir dummy records: {e}")
            conn.rollback()
        finally:
            conn.close()

    # =========================================================================
    # CARREGAMENTO DA DIM_DATA (PK fixa, não AUTO_INCREMENT)
    # =========================================================================
    def load_date_dimension(self, df_dates: pd.DataFrame):
        """
        Carrega a Dim_Data com INSERT IGNORE para evitar colisão com o dummy SK=0.
        A Dim_Data usa SK_Data como PK fixa (YYYYMMDD), não AUTO_INCREMENT,
        portanto precisa de tratamento dedicado.
        """
        conn = self._get_connection()
        try:
            existing_sks = set(
                pd.read_sql("SELECT SK_Data FROM dim_data", conn)['SK_Data'].values
            )
            novos = df_dates[~df_dates['SK_Data'].isin(existing_sks)].copy()

            if not novos.empty:
                # Garantir que DataCompleta é string para MySQL
                novos['DataCompleta'] = novos['DataCompleta'].astype(str)
                novos.to_sql('dim_data', conn, if_exists='append', index=False)
                conn.commit()
                self.logger.info(f"[Dim_Data] {len(novos):,} registos inseridos.")
            else:
                self.logger.info("[Dim_Data] Já populada.")
        except Exception as e:
            self.logger.error(f"[Dim_Data] Erro: {e}")
        finally:
            conn.close()

    # =========================================================================
    # CARREGAMENTO DE DIMENSÕES DINÂMICAS (SCD Tipo 1)
    # =========================================================================
    def load_dimension(self, df: pd.DataFrame, table_name: str, natural_keys: List[str], sk_name: str) -> pd.DataFrame:
        """
        Gere dimensões SCD Tipo 1.
        Compara registos com a BD, insere novos, e faz lookup das SKs.
        """
        nk_valid = [k for k in natural_keys if k in df.columns]
        if not nk_valid:
            self.logger.warning(f"[{table_name}] Sem chaves naturais válidas. SK=0.")
            df[sk_name] = 0
            return df

        # Limpeza defensiva
        for col in nk_valid:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({'nan': 'N/D', '<NA>': 'N/D', '': 'N/D', 'None': 'N/D'})

        dim_df = df[nk_valid].drop_duplicates().copy()

        conn = self._get_connection()
        try:
            select_cols = [sk_name] + nk_valid
            try:
                existing_df = pd.read_sql(f"SELECT * FROM {table_name.lower()}", conn)
            except Exception:
                existing_df = pd.DataFrame()

            # Normalização de nomes de colunas (MySQL case-insensitive)
            if not existing_df.empty:
                col_map = {mc: ec for mc in existing_df.columns for ec in select_cols if mc.lower() == ec.lower()}
                existing_df = existing_df.rename(columns=col_map)

            keep_cols = [c for c in select_cols if c in existing_df.columns]
            if keep_cols:
                existing_df = existing_df[keep_cols].copy()

            for col in nk_valid:
                if col in existing_df.columns:
                    existing_df[col] = existing_df[col].astype(str).str.strip()

            # Identificar registos novos
            if not existing_df.empty and sk_name in existing_df.columns:
                check = pd.merge(dim_df, existing_df[nk_valid], on=nk_valid, how='left', indicator=True)
                new_records = check[check['_merge'] == 'left_only'][nk_valid].copy()
            else:
                new_records = dim_df.copy()

            # Inserção no MySQL
            if not new_records.empty:
                insert_df = new_records[nk_valid].copy()
                for col in nk_valid:
                    insert_df[col] = insert_df[col].astype(str)
                insert_df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
                conn.commit()
                self.logger.info(f"[{table_name}] {len(insert_df)} novos registos inseridos.")

                # Re-leitura para capturar SKs AUTO_INCREMENT
                existing_df = pd.read_sql(f"SELECT * FROM {table_name.lower()}", conn)
                col_map = {mc: ec for mc in existing_df.columns for ec in select_cols if mc.lower() == ec.lower()}
                existing_df = existing_df.rename(columns=col_map)
                existing_df = existing_df[[c for c in select_cols if c in existing_df.columns]].copy()
                for col in nk_valid:
                    if col in existing_df.columns:
                        existing_df[col] = existing_df[col].astype(str).str.strip()
            else:
                self.logger.info(f"[{table_name}] Nenhum registo novo.")

        except Exception as e:
            self.logger.error(f"[{table_name}] Erro: {e}")
            existing_df = pd.DataFrame(columns=[sk_name] + nk_valid)
        finally:
            conn.close()

        # Lookup: devolver SK ao DataFrame da Facto
        if sk_name in df.columns:
            df = df.drop(columns=[sk_name])

        if sk_name in existing_df.columns and len(existing_df) > 0:
            merge_cols = [c for c in nk_valid if c in existing_df.columns]
            lookup = existing_df[merge_cols + [sk_name]].drop_duplicates(subset=merge_cols, keep='first')
            df = pd.merge(df, lookup, on=merge_cols, how='left')
            df[sk_name] = df[sk_name].fillna(0).astype(int)
        else:
            df[sk_name] = 0

        return df

    # =========================================================================
    # PAYLOAD DA FACTO E CARREGAMENTO
    # =========================================================================
    def prepare_fact_payload(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filtra o DataFrame retendo apenas SKs e Métricas do Facto."""
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

        for metric in ['Duracao_Minutos', 'Numero_Presencas']:
            if metric not in df.columns:
                df[metric] = 0
            df[metric] = pd.to_numeric(df[metric], errors='coerce').fillna(0).astype(int)

        if 'Flag_Evento_Agregado' not in df.columns:
            df['Flag_Evento_Agregado'] = 0
        df['Flag_Evento_Agregado'] = pd.to_numeric(df['Flag_Evento_Agregado'], errors='coerce').fillna(0).astype(int)

        valid_cols = required_sks + ['ID_Ocupacao', 'Duracao_Minutos', 'Numero_Presencas', 'Flag_Evento_Agregado']
        return df[valid_cols].copy()

    def load_fact(self, df_fact: pd.DataFrame, table_name: str = "Facto_Ocupacao", chunk_size: int = 5000):
        """Carrega a Tabela de Factos em lotes, prevenindo duplicação via ID_Ocupacao."""
        conn = self._get_connection()
        try:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            try:
                existing_ids = set(pd.read_sql(f"SELECT ID_Ocupacao FROM {table_name.lower()}", conn)['ID_Ocupacao'].values)
            except Exception:
                existing_ids = set()

            novos = df_fact[~df_fact['ID_Ocupacao'].isin(existing_ids)].copy()
            if novos.empty:
                self.logger.info(f"[{table_name}] Nenhum facto novo a carregar.")
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
                self.logger.info(f"[{table_name}] TOTAL: {total:,} registos inseridos.")

        except Exception as e:
            self.logger.error(f"[{table_name}] Falha no carregamento: {e}")
            raise
        finally:
            try:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
                conn.commit()
            except Exception:
                pass
            conn.close()

    # =========================================================================
    # MÉTRICAS DE QUALIDADE
    # =========================================================================
    def print_quality_metrics(self, df: pd.DataFrame):
        """Produz logs de auditoria sobre o mapeamento das SKs."""
        sk_columns = [c for c in df.columns if c.startswith('SK_')]
        if not sk_columns:
            return
        self.logger.info("=" * 60)
        self.logger.info("MÉTRICAS DE QUALIDADE DAS SURROGATE KEYS:")
        self.logger.info("=" * 60)
        total = len(df)
        for sk in sk_columns:
            filled = (df[sk] > 0).sum()
            pct = (filled / total * 100) if total > 0 else 0
            self.logger.info(f"  {sk:35s}: {filled:>7,}/{total:>7,} ({pct:6.2f}%)")
        self.logger.info("=" * 60)