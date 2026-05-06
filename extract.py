import pandas as pd
import logging
import csv
from pathlib import Path
from typing import Optional
from io import StringIO


class DataExtractor:
    """
    Responsável estritamente pela ingestão de dados de fontes heterogéneas.
    Garante que os dados chegam à Staging Area com colunas normalizadas em
    snake_case e sem qualquer transformação de negócio.
    """

    def __init__(self, base_path: str = "Dados"):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)

    # -----------------------------------------------------------------
    # NORMALIZAÇÃO DE COLUNAS (snake_case)
    # -----------------------------------------------------------------
    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza todos os nomes de colunas para snake_case."""
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(r'[,]+$', '', regex=True)   # Remove trailing commas (e.g. "semestre,,")
            .str.replace(r'\s+', '_', regex=True)
            .str.replace(r'[^\w]', '_', regex=True)
            .str.strip('_')
        )
        return df

    @staticmethod
    def _sanitize_strings(df: pd.DataFrame) -> pd.DataFrame:
        """
        Sanitização universal de strings após extração.
        Remove \r (carriage return) e caracteres ? espúrios de todas as colunas texto.
        """
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = (
                df[col]
                .str.replace('\r', '', regex=False)      # Bug 4: Remove CR literal
                .str.replace('\\r', '', regex=False)     # Bug 4: Remove escaped \r from SQL dumps
                .str.replace(r'^\?+', '', regex=True)     # Bug 5: Remove leading ? (encoding artefact)
                .str.strip()
            )
        return df

    # -----------------------------------------------------------------
    # CSV GENÉRICO
    # -----------------------------------------------------------------
    def extract_csv(self, filename: str, sep: str = ",", encoding: str = "cp1252") -> Optional[pd.DataFrame]:
        """
        Extrai dados brutos de ficheiros CSV.
        - Carrega tudo como string (dtype=str) para evitar inferências erradas.
        - Normaliza nomes de colunas para snake_case.
        """
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro {filename} não encontrado em {self.base_path}.")
            return None

        try:
            self.logger.info(f"A extrair dados brutos (Raw) de: {filename}")
            df = pd.read_csv(file_path, sep=sep, encoding=encoding, low_memory=False, dtype=str)
            df = self._normalize_columns(df)
            df = self._sanitize_strings(df)
            self.logger.info(f"[{filename}] Extração concluída: {df.shape[0]:,} linhas | Colunas: {list(df.columns)}")
            return df

        except Exception as e:
            self.logger.error(f"Erro na extração de {filename}: {e}")
            return None

    # -----------------------------------------------------------------
    # SQL DUMP (Staging para enriquecimento de responsáveis)
    # -----------------------------------------------------------------
    def extract_sql_staging(self, filename: str) -> Optional[pd.DataFrame]:
        """
        Realiza o parsing manual de ficheiros .sql para extrair registos brutos.
        Nota: Colunas já são devolvidas em snake_case.
        """
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro SQL {filename} não encontrado.")
            return None

        try:
            self.logger.info(f"A processar dump SQL: {filename}")

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            data = []
            # Esquema original conforme o dump (conforme identificado na Tarefa 1)
            columns = [
                'id', 'desig_edf', 'espaco', 'datainicio', 'datafim', 'unidade_respon',
                'tipo', 'cod_disc', 'nome_disci', 'ciclo', 'descricao', 'estado', 'pessoa_resp'
            ]

            blocks = content.split('INSERT INTO `turnos`')

            for block in blocks[1:]:
                val_idx = block.find('VALUES')
                if val_idx != -1:
                    tuples_str = block[val_idx+6:].strip().rstrip(';')
                    rows = tuples_str.split('),')
                    for row in rows:
                        row = row.strip().strip('()')

                        reader = csv.reader(
                            StringIO(row),
                            quotechar="'",
                            delimiter=',',
                            skipinitialspace=True
                        )

                        for parsed_row in reader:
                            # Correções de escape + remoção de \r literal (Bug 4)
                            clean_row = [
                                str(x).replace("\\'", "'").replace('\\r', '').replace('\r', '').strip()
                                for x in parsed_row
                            ]
                            data.append(clean_row)

            df = pd.DataFrame(data, columns=columns)
            df = self._sanitize_strings(df)
            self.logger.info(f"[SQL Staging] Parsing concluído: {len(df):,} registos.")
            return df

        except Exception as e:
            self.logger.error(f"Falha no parsing do SQL {filename}: {e}")
            return None

    # -----------------------------------------------------------------
    # DICIONÁRIO DE CURSOS (Reference Data)
    # -----------------------------------------------------------------
    def extract_courses(self, filename: str = "curso_ucs(in).csv") -> Optional[pd.DataFrame]:
        """
        Extrai a listagem mestre de cursos/UCs.
        Ficheiro utiliza separador ';' e encoding latin-1.
        """
        self.logger.info(f"A iniciar extração da tabela mestre de cursos: {filename}")
        df_courses = self.extract_csv(filename, sep=";", encoding="latin-1")

        if df_courses is not None:
            self.logger.info(f"Cursos extraídos com sucesso. Colunas detetadas: {list(df_courses.columns)}")
            return df_courses

        return None