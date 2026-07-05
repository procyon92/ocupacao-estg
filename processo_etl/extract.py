import pandas as pd
import logging
import csv
import re
from pathlib import Path
from typing import Optional, List
from io import StringIO


class DataExtractor:
    # Responsável apenas pela ingestão de dados — sem transformações de negócio.
    # Dados chegam à Staging Area com colunas normalizadas em snake_case.

    def __init__(self, base_path: str = "Dados"):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        # Converte todos os nomes de colunas para snake_case limpo
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(r'[,]+$', '', regex=True)
            .str.replace(r'\s+', '_', regex=True)
            .str.replace(r'[^\w]', '_', regex=True)
            .str.strip('_')
        )
        return df

    @staticmethod
    def _sanitize_strings(df: pd.DataFrame) -> pd.DataFrame:
        # Remove carriage returns e caracteres de encoding espúrios de todas as colunas de texto
        string_cols = df.select_dtypes(include=['object', 'string']).columns
        for col in string_cols:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace('\r', '', regex=False)
                .str.replace('\\r', '', regex=False)
                .str.replace(r'^\?+', '', regex=True)
                .str.strip()
            )
            # "nan" literal gerado pelo astype(str) é revertido para nulo real
            df[col] = df[col].replace('nan', pd.NA)
        return df

    def extract_csv(self, filename: str, sep: str = ",", encoding: str = "utf-8", **kwargs) -> Optional[pd.DataFrame]:
        # Lê um ficheiro delimitado e devolve um DataFrame com colunas normalizadas
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro {filename} não encontrado em {self.base_path}.")
            return None

        try:
            self.logger.info(f"A extrair dados brutos (Raw) de: {filename}")
            df = pd.read_csv(file_path, sep=sep, encoding=encoding, low_memory=False, dtype=str, **kwargs)
            df = self._normalizar_colunas(df)
            df = self._sanitize_strings(df)
            self.logger.info(f"[{filename}] Extração concluída: {df.shape[0]:,} linhas.")
            return df
        except Exception as e:
            self.logger.error(f"Erro na extração de {filename}: {e}")
            return None

    def extract_sql_dump(self, filename: str, table_name: str, expected_columns: List[str]) -> Optional[pd.DataFrame]:
        # Faz parsing de um ficheiro .sql e extrai os registos de uma tabela específica
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro SQL {filename} não encontrado.")
            return None

        try:
            self.logger.info(f"A processar dump SQL: {filename} | Tabela alvo: {table_name}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            data = []
            # Regex dinâmico para capturar blocos VALUES mesmo com quebras de linha no ficheiro
            pattern = rf"INSERT INTO `{table_name}`.*?(?:VALUES\s*)(.+?);"
            matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)

            for match in matches:
                tuples_str = match.group(1).strip()
                # Divide os tuplos pelo padrão ),(  sem partir strings que contenham vírgulas
                rows = re.split(r'\),\s*\(', tuples_str.strip('()'))

                for row in rows:
                    row = row.strip('()')
                    reader = csv.reader(
                        StringIO(row),
                        quotechar="'",
                        delimiter=',',
                        skipinitialspace=True,
                        escapechar='\\'
                    )

                    for parsed_row in reader:
                        clean_row = [str(x).strip() for x in parsed_row]
                        if len(clean_row) == len(expected_columns):
                            data.append(clean_row)
                        else:
                            # Linha com número de colunas diferente do esperado — descartada
                            self.logger.warning(f"Desalinhamento de schema ignorado na tabela {table_name}.")

            df = pd.DataFrame(data, columns=expected_columns)
            df = self._normalizar_colunas(df)
            df = self._sanitize_strings(df)
            self.logger.info(f"[SQL Staging] Parsing concluído: {len(df):,} registos.")
            return df

        except Exception as e:
            self.logger.error(f"Falha no parsing do SQL {filename}: {e}")
            return None