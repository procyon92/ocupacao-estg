import pandas as pd
import logging
import csv
import re
from pathlib import Path
from typing import Optional
from io import StringIO

class DataExtractor:
    """
    Responsável pela ingestão de dados de fontes heterogéneas (CSV e SQL Dumps).
    Implementa a primeira camada de limpeza (Sanitização) e normalização de esquema.
    """

    def __init__(self, base_path: str = "Dados"):
        """
        Inicializa o Extractor definindo o diretório base para as fontes de dados.
        """
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Padroniza os nomes das colunas para snake_case e remove caracteres especiais.
        Garante consistência para as fases de transformação e merge.
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
        Realiza a limpeza de strings em todo o DataFrame.
        Trata especificamente o 'Float Poisoning' e resíduos de formatação SQL (\r, \n).
        """
        for col in df.select_dtypes(include=['object']).columns:
            # Remoção de carriage returns e espaços em branco nas extremidades
            df[col] = df[col].astype(str).str.replace('\r', '', regex=False).str.strip()
            
            # Reconversão de strings 'nan' para objetos nulos reais (pandas NA)
            df[col] = df[col].replace('nan', pd.NA)
        return df

    def extract_csv(self, filename: str, sep: str = ",", encoding: str = "cp1252") -> Optional[pd.DataFrame]:
        """
        Extrai dados de ficheiros CSV, aplicando normalização de colunas e limpeza de strings.
        """
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro {filename} não encontrado em: {self.base_path.absolute()}")
            return None

        try:
            self.logger.info(f"A iniciar extração de CSV: {filename}")
            # low_memory=False garante a correta inferência de tipos em datasets grandes
            df = pd.read_csv(file_path, sep=sep, encoding=encoding, low_memory=False)
            
            self.logger.info(f"[{filename}] Sucesso: {df.shape[0]:,} linhas detetadas.")
            
            df = self._normalize_columns(df)
            df = self._sanitize_strings(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Erro na extração de {filename}: {e}")
            return None

    def extract_sql_staging(self, filename: str) -> Optional[pd.DataFrame]:
        """
        Extrai dados diretamente de um ficheiro de dump SQL (.sql).
        Utiliza um parser customizado para extrair blocos 'INSERT INTO' sem necessidade de DB intermédia.
        """
        file_path = self.base_path / filename
        if not file_path.exists():
            self.logger.error(f"Ficheiro SQL {filename} não encontrado.")
            return None

        try:
            self.logger.info(f"A processar dump SQL: {filename} (Parsing manual de INSERTs)")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            data = []
            # Definição do esquema esperado conforme o dump fornecido pela ESTG
            columns = [
                'id', 'desig_edf', 'espaco', 'datainicio', 'datafim', 'unidade_respon', 
                'tipo', 'cod_disc', 'nome_disci', 'ciclo', 'descricao', 'estado', 'pessoa_resp'
            ]
            
            # Segmentação do ficheiro por comandos de inserção
            blocks = content.split('INSERT INTO `turnos`')
            
            for block in blocks[1:]: # Omitir o primeiro bloco (CREATE TABLE / Header)
                val_idx = block.find('VALUES')
                if val_idx != -1:
                    # Extração da string contendo os tuplos de dados
                    tuples_str = block[val_idx+6:].strip().rstrip(';')
                    
                    # Split por '),(' para isolar cada registo, tratando a pontuação SQL
                    rows = tuples_str.split('),')
                    for row in rows:
                        row = row.strip()
                        if row.startswith('('): row = row[1:]
                        if row.endswith(')'): row = row[:-1]
                        
                        # Utilização do módulo csv para processar vírgulas dentro de strings quotes
                        reader = csv.reader(
                            StringIO(row), 
                            quotechar="'", 
                            delimiter=',', 
                            skipinitialspace=True
                        )
                        
                        for parsed_row in reader:
                            # Tratamento de escape characters específicos de dumps SQL (MySQL style)
                            clean_row = [
                                str(x).replace("\\'", "'").replace("\\r", "").replace("\\n", " ") 
                                for x in parsed_row
                            ]
                            data.append(clean_row)
            
            df_stg = pd.DataFrame(data, columns=columns)
            
            self.logger.info(f"[{filename}] Sucesso no parsing: {df_stg.shape[0]:,} linhas extraídas.")
            
            # Aplicação de limpeza padrão
            df_stg = self._normalize_columns(df_stg)
            df_stg = self._sanitize_strings(df_stg)
            
            return df_stg

        except Exception as e:
            self.logger.error(f"Falha no processamento do ficheiro SQL {filename}: {e}")
            return None