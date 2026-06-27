import os
import pandas as pd
import logging
from sqlalchemy import create_engine, text
from typing import List
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class DataLoader:
    # Camada de Load do ETL — materializa o modelo dimensional na BD MySQL.
    # Gere Surrogate Keys, dimensões (SCD1 e SCD2) e inserção da tabela de factos.

    def __init__(self, host=None, user=None, password=None, db_name=None, port=None):
        # Lê as credenciais do .env se não forem passadas diretamente
        self.host     = host     or os.getenv('DB_HOST', 'localhost')
        self.user     = user     or os.getenv('DB_USER', 'root')
        self.password = password or os.getenv('DB_PASSWORD', '')
        self.db_name  = db_name  or os.getenv('DB_NAME', 'dw_ocupacao')
        self.port     = port     or os.getenv('DB_PORT', '3306')
        self.connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
        self.engine = create_engine(self.connection_string, future=True)
        self.logger = logging.getLogger(__name__)

    # Dummy Records (SK=0)

    def ensure_dummy_dimension_records(self):
        # Garante que existe o registo SK=0 em todas as dimensões — usado quando um facto não tem dimensão conhecida
        self.logger.info("A inserir/validar Dummies (SK=0)...")
        queries = [
            "INSERT IGNORE INTO Dim_Data (SK_Data, DataCompleta, Ano, Ano_Escolar, Mes, Numero_Semana, Dia, DiaSemana, Semestre, Tipo_Dia, Numero_Semana_Escolar) VALUES (0, '1900-01-01', 1900, 'N/D', 1, 0, 1, 'N/D', 0, 'N/D', 0)",
            "INSERT IGNORE INTO Dim_Hora (SK_Hora, Hora, Minuto) VALUES (0, 0, 0)",
            "INSERT IGNORE INTO Dim_Epoca (SK_Epoca, Descricao_Epoca) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO Dim_Espaco (SK_Espaco, Edificio, Nome_Espaco, Categoria_Espaco, Escola_Responsavel, is_online, Departamento, Valid_From, Valid_To, Is_Active) VALUES (0, 'N/D', 'N/D', 'N/D', 'N/D', 0, 'N/D', '1900-01-01', '9999-12-31', 1)",
            "INSERT IGNORE INTO Dim_Unidade_Curricular (SK_Unidade_Curricular, Codigo_UC, Designacao_UC, Ciclo_Estudo, Valid_From, Valid_To, Is_Active) VALUES (0, 'N/D', 'N/D', 'N/D', '1900-01-01', '9999-12-31', 1)",
            "INSERT IGNORE INTO Dim_Curso (SK_Curso, Codigo_Curso, Nome_Curso, Valid_From, Valid_To, Is_Active) VALUES (0, 'N/D', 'N/D', '1900-01-01', '9999-12-31', 1)",
            "INSERT IGNORE INTO Dim_Responsavel (SK_Responsavel, Docente_Responsavel) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO Dim_Tipo_Atividade (SK_Tipo_Atividade, Designacao_Atividade) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO Dim_Estado_Agendamento (SK_Estado_Agendamento, Estado) VALUES (0, 'N/D')",
            "INSERT IGNORE INTO Dim_Turno (SK_Turno, Designacao_Turno) VALUES (0, 'N/D')"
        ]
        with self.engine.begin() as conn:
            # NO_AUTO_VALUE_ON_ZERO permite inserir explicitamente SK=0
            conn.execute(text("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';"))
            for q in queries:
                conn.execute(text(q))
        self.logger.info("  Dummies SK=0 inseridos/validados com sucesso.")

    # Dimensões com PK fixa (Data, Hora)

    def load_fixed_pk_dimension(self, df_dim: pd.DataFrame, table_name: str, sk_name: str):
        # Para dimensões onde a PK não é AUTO_INCREMENT — insere só os SKs que ainda não existem
        with self.engine.begin() as conn:
            existing_sks = set(
                pd.read_sql(text(f"SELECT {sk_name} FROM {table_name}"), conn)[sk_name].values
            )
            novos = df_dim[~df_dim[sk_name].isin(existing_sks)].copy()

            if not novos.empty:
                if 'DataCompleta' in novos.columns:
                    novos['DataCompleta'] = novos['DataCompleta'].astype(str)
                novos.to_sql(table_name.lower(), conn, if_exists='append', index=False)
                self.logger.info(f"[{table_name}] {len(novos):,} registos inseridos.")
            else:
                self.logger.info(f"[{table_name}] Já populada.")

    # Dimensões dinâmicas — SCD Tipo 1

    def load_dimension_scd1(self, df: pd.DataFrame, table_name: str, natural_keys: List[str], sk_name: str) -> pd.DataFrame:
        # SCD1 — sem histórico: se o registo já existe, não faz nada; se é novo, insere
        nk_valid = [k for k in natural_keys if k in df.columns]
        if not nk_valid:
            df[sk_name] = 0
            return df

        for col in nk_valid:
            df[col] = df[col].astype(str).str.strip().replace({'nan': 'N/D', '<NA>': 'N/D', '': 'N/D', 'None': 'N/D'})

        dim_df = df[nk_valid].drop_duplicates().copy()

        with self.engine.begin() as conn:
            existing_df = pd.read_sql(text(f"SELECT * FROM {table_name}"), conn)

            if not existing_df.empty:
                for key in nk_valid:
                    if key in dim_df.columns and key in existing_df.columns:
                        dim_df[key]      = dim_df[key].astype(str)
                        existing_df[key] = existing_df[key].astype(str)
                check       = pd.merge(dim_df, existing_df[nk_valid], on=nk_valid, how='left', indicator=True)
                new_records = check[check['_merge'] == 'left_only'][nk_valid].copy()
            else:
                new_records = dim_df.copy()

            if not new_records.empty:
                new_records[nk_valid].to_sql(table_name.lower(), conn, if_exists='append', index=False)
                self.logger.info(f"[{table_name}] {len(new_records)} novos registos inseridos (SCD1).")

            # Lookup dentro da mesma transação — evita abrir uma segunda ligação
            existing_df = pd.read_sql(text(f"SELECT * FROM {table_name}"), conn)

        if sk_name in df.columns:
            df = df.drop(columns=[sk_name])

        if not existing_df.empty:
            merge_cols = [c for c in nk_valid if c in existing_df.columns]
            for key in merge_cols:
                if key in df.columns:
                    df[key]          = df[key].astype(str)
                    existing_df[key] = existing_df[key].astype(str)
            # Faz o lookup da SK pelo(s) natural key(s)
            lookup = existing_df[merge_cols + [sk_name]].drop_duplicates(subset=merge_cols, keep='first')
            df     = pd.merge(df, lookup, on=merge_cols, how='left')
            df[sk_name] = df[sk_name].fillna(0).astype(int)
        else:
            df[sk_name] = 0

        return df

    # Dimensões dinâmicas — SCD Tipo 2

    def load_dimension_scd2(self, df: pd.DataFrame, table_name: str, natural_keys: List[str], sk_name: str) -> pd.DataFrame:
        # SCD2 — com histórico: registo alterado é expirado (Valid_To, Is_Active=0) e inserido novo
        nk_valid = [k for k in natural_keys if k in df.columns]
        if not nk_valid:
            df[sk_name] = 0
            return df

        dim_cols = [c for c in df.columns if c != sk_name]
        dim_df   = df[dim_cols].drop_duplicates(subset=nk_valid).copy()

        for col in dim_df.columns:
            dim_df[col] = dim_df[col].astype(str).str.strip().replace({'nan': 'N/D', '<NA>': 'N/D', '': 'N/D', 'None': 'N/D'})

        current_date = datetime.now().strftime('%Y-%m-%d')

        with self.engine.begin() as conn:
            # Só lê registos ativos — os expirados não interessam para o lookup
            existing_df = pd.read_sql(text(f"SELECT * FROM {table_name} WHERE Is_Active = 1"), conn)

            if not existing_df.empty:
                common_cols = [c for c in dim_df.columns if c in existing_df.columns]
                dim_df      = dim_df[common_cols].copy()
                nk_valid    = [k for k in nk_valid if k in dim_df.columns]

            if not existing_df.empty:
                for key in nk_valid:
                    if key in dim_df.columns and key in existing_df.columns:
                        dim_df[key]      = dim_df[key].astype(str).str.strip()
                        existing_df[key] = existing_df[key].astype(str).str.strip()
                merged      = pd.merge(dim_df, existing_df, on=nk_valid, how='left', suffixes=('', '_db'), indicator=True)
                new_records = merged[merged['_merge'] == 'left_only'][dim_df.columns].copy()

                # Deteta registos cujos atributos mudaram (excluindo as natural keys)
                compare_cols    = [c for c in dim_df.columns if c not in nk_valid and c in existing_df.columns]
                changed_records = pd.DataFrame()

                if compare_cols:
                    both         = merged[merged['_merge'] == 'both'].copy()
                    changed_mask = pd.Series([False] * len(both), index=both.index)
                    for col in compare_cols:
                        changed_mask |= (both[col] != both[f"{col}_db"])
                    changed_records = both[changed_mask]

                if not changed_records.empty:
                    # Expira os registos antigos antes de inserir os novos
                    sks_to_expire = changed_records[f"{sk_name}_db"].tolist()
                    if sks_to_expire:
                        conn.execute(
                            text(f"UPDATE {table_name} SET Valid_To = :current_date, Is_Active = 0 WHERE {sk_name} IN :sks"),
                            {"current_date": current_date, "sks": tuple(sks_to_expire)}
                        )
                    changed_inserts = changed_records[dim_df.columns].copy()
                    new_records     = pd.concat([new_records, changed_inserts], ignore_index=True)
            else:
                new_records = dim_df.copy()

            if not new_records.empty:
                new_records['Valid_From'] = current_date
                new_records['Valid_To']   = '9999-12-31'
                new_records['Is_Active']  = 1
                new_records.to_sql(table_name.lower(), conn, if_exists='append', index=False)
                self.logger.info(f"[{table_name}] {len(new_records)} novos/atualizados registos inseridos (SCD2).")

            # Lookup dentro da mesma transação — evita abrir uma segunda ligação
            lookup_df = pd.read_sql(
                text(f"SELECT {','.join(nk_valid)}, {sk_name} FROM {table_name} WHERE Is_Active = 1"),
                conn
            )

        if sk_name in df.columns:
            df = df.drop(columns=[sk_name])

        merge_cols = [c for c in nk_valid if c in lookup_df.columns]
        for key in merge_cols:
            if key in df.columns:
                df[key]        = df[key].astype(str).str.strip()
                lookup_df[key] = lookup_df[key].astype(str).str.strip()
        lookup      = lookup_df[merge_cols + [sk_name]].drop_duplicates(subset=merge_cols, keep='first')
        df          = pd.merge(df, lookup, on=merge_cols, how='left')
        df[sk_name] = df[sk_name].fillna(0).astype(int)

        return df

    # Tabela de factos

    def prepare_fact_payload(self, df: pd.DataFrame) -> pd.DataFrame:
        # Garante que todas as SKs existem e são inteiros — usa 0 (dummy) se estiverem em falta
        required_sks = [
            'SK_Data', 'SK_Hora_Inicio', 'SK_Hora_Fim',
            'SK_Espaco', 'SK_Unidade_Curricular', 'SK_Curso',
            'SK_Responsavel', 'SK_Tipo_Atividade', 'SK_Estado_Agendamento', 'SK_Turno', 'SK_Epoca'
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
        # Insere só os factos novos — evita duplicados comparando o ID_Ocupacao com o que já está na BD
        with self.engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            try:
                try:
                    existing_ids = set(pd.read_sql(text(f"SELECT ID_Ocupacao FROM {table_name}"), conn)['ID_Ocupacao'].values)
                except Exception:
                    existing_ids = set()

                novos = df_fact[~df_fact['ID_Ocupacao'].isin(existing_ids)].copy()
                if novos.empty:
                    self.logger.info(f"[{table_name}] Nenhum facto novo a carregar.")
                else:
                    total  = len(novos)
                    loaded = 0
                    # Insere em chunks para não sobrecarregar a memória nem a BD
                    for i in range(0, total, chunk_size):
                        chunk = novos.iloc[i:i+chunk_size]
                        chunk.to_sql(table_name.lower(), conn, if_exists='append', index=False)
                        loaded += len(chunk)
                    self.logger.info(f"[{table_name}] TOTAL: {total:,} registos inseridos.")
            finally:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

    # Métricas de qualidade

    def print_quality_metrics(self, df: pd.DataFrame):
        # Mostra a percentagem de factos com SK válida (>0) para cada dimensão
        sk_columns = [c for c in df.columns if c.startswith('SK_')]
        if not sk_columns:
            return
        self.logger.info("=" * 60)
        self.logger.info("MÉTRICAS DE QUALIDADE DAS SURROGATE KEYS:")
        self.logger.info("=" * 60)
        total = len(df)
        for sk in sk_columns:
            filled = (df[sk] > 0).sum()
            pct    = (filled / total * 100) if total > 0 else 0
            self.logger.info(f"  {sk:35s}: {filled:>7,}/{total:>7,} ({pct:6.2f}%)")
        self.logger.info("=" * 60)