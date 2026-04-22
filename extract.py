import pandas as pd
import logging
from pathlib import Path
from typing import Optional

class DataExtractor:
    def __init__(self, base_path: str = "Dados"):
        """
        Inicializa o Extractor definindo a base path.
        """
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Garante que todas as colunas possuem nomes consistentes em snake_case.
        """
        df.columns = (
            df.columns.str.strip()
            .str.lower()
            .str.replace(" ", "_", regex=False)
            .str.replace("(", "", regex=False)
            .str.replace(")", "", regex=False)
            .str.replace(".", "", regex=False)
        )
        return df

    def _sanitize_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove carriage returns (\r), trailing whitespace from ALL string columns.
        This is critical because the source SQL dump embeds \r in pessoa_resp.
        """
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.replace('\r', '', regex=False).str.strip()
            # Convert 'nan' string back to actual NaN for proper downstream handling
            df[col] = df[col].replace('nan', pd.NA)
        return df

    def extract_csv(self, filename: str, sep: str = ",", encoding: str = "cp1252") -> Optional[pd.DataFrame]:
        """
        Carrega ficheiro CSV, normaliza colunas, sanitiza strings e reporta métricas iniciais.
        """
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro {filename} não encontrado no diretório: {self.base_path.absolute()}")
            return None

        try:
            self.logger.info(f"A extrair {filename}...")
            df = pd.read_csv(file_path, sep=sep, encoding=encoding, low_memory=False)
            self.logger.info(f"[{filename}] Extração sumária: {df.shape[0]:,} linhas, {df.shape[1]} colunas.")
            
            df = self._normalize_columns(df)
            df = self._sanitize_strings(df)
            
            self.logger.info(f"[{filename}] Colunas normalizadas: {list(df.columns)}")
            return df
            
        except Exception as e:
            self.logger.error(f"Falha na extração de {filename}: {e}")
            return None

    def extract_sql_staging(self, filename: str, engine_str: str = "mysql+pymysql://root:dbsecret@localhost:3306/dw_ocupacao") -> Optional[pd.DataFrame]:
        """
        Lê e executa um script SQL (dump) criando a tabela de staging e retornando um DataFrame.
        Enforça a criação de `stg_turnos`.
        """
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro SQL {filename} não encontrado.")
            return None

        from sqlalchemy import create_engine, text
        import re

        try:
            self.logger.info(f"A executar extracao pura de dados de staging do ficheiro {filename}...")
            
            import re
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.logger.info("Parsing SQL string (extraindo clausulas INSERT INTO turnos)...")
            # Extract the VALUES (...) blocks
            # Find all chunks matching `INSERT INTO... VALUES ( chunk );`
            
            data = []
            columns = ['id', 'desig_edf', 'espaco', 'datainicio', 'datafim', 'unidade_respon', 
                       'tipo', 'cod_disc', 'nome_disci', 'ciclo', 'descricao', 'estado', 'pessoa_resp']
            
            # Since the file can be large but string ops are fast in python:
            blocks = content.split('INSERT INTO `turnos`')
            for block in blocks[1:]: # skip first which is CREATE TABLE etc
                # block usually starts with ` (...) VALUES ` then tuples
                val_idx = block.find('VALUES')
                if val_idx != -1:
                    tuples_str = block[val_idx+6:].strip().rstrip(';')
                    # Now we have string like: (63899, 'Edifício', ...), (...), (...)
                    # Let's split by '),' and handle the closing parenthesis
                    rows = tuples_str.split('),')
                    for row in rows:
                        row = row.strip()
                        if row.startswith('('):
                            row = row[1:]
                        if row.endswith(')'):
                            row = row[:-1]
                        
                        # We use csv to parse the comma separated values factoring in quotes
                        import csv
                        from io import StringIO
                        reader = csv.reader(StringIO(row), quotechar="'", delimiter=',', skipinitialspace=True)
                        for parsed_row in reader:
                            # Also replace \' with '
                            parsed_row = [str(x).replace("\\'", "'").replace("\\r", "").replace("\\n", " ") for x in parsed_row]
                            data.append(parsed_row)
                            
            df_stg = pd.DataFrame(data, columns=columns)
                
            self.logger.info(f"[{filename}] Extração sumária via RegEx/Parse: {df_stg.shape[0]:,} linhas.")
            
            df_stg = self._normalize_columns(df_stg)
            df_stg = self._sanitize_strings(df_stg)
            
            return df_stg

        except Exception as e:
            self.logger.error(f"Falha na extração SQL de {filename}: {e}")
            return None
