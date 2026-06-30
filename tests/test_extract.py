"""
test_extract.py — Testes unitários para o módulo extract.py do pipeline ETL.

Cobre:
  - _normalize_columns  : normalização de nomes de colunas para snake_case
  - _sanitize_strings   : limpeza de caracteres espúrios em colunas de texto
  - extract_csv         : leitura e normalização de ficheiros CSV
  - extract_sql_dump    : parsing de ficheiros SQL e extração de registos

Os testes criam ficheiros temporários em disco e limpam-nos no teardown.

Executar com:
    pytest tests/test_extract.py -v
"""

import pytest
import sys
import os
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'processo_etl'))

from extract import DataExtractor


@pytest.fixture
def tmp_data_dir(tmp_path):
    # Diretório temporário que serve de base_path para o DataExtractor
    return tmp_path


@pytest.fixture
def extractor(tmp_data_dir):
    return DataExtractor(base_path=str(tmp_data_dir))


def write_file(path: Path, content: str, encoding: str = "utf-8"):
    path.write_text(content, encoding=encoding)


# _normalize_columns

class TestNormalizeColumns:

    def test_maiusculas_para_minusculas(self):
        df = pd.DataFrame(columns=["Nome", "EDIFICIO", "DataInicio"])
        result = DataExtractor._normalize_columns(df)
        assert list(result.columns) == ["nome", "edificio", "datainicio"]

    def test_espacos_para_underscore(self):
        df = pd.DataFrame(columns=["data inicio", "nome espaco"])
        result = DataExtractor._normalize_columns(df)
        assert "data_inicio" in result.columns
        assert "nome_espaco" in result.columns

    def test_caracteres_especiais_para_underscore(self):
        df = pd.DataFrame(columns=["col.um", "col-dois", "col/tres"])
        result = DataExtractor._normalize_columns(df)
        for col in result.columns:
            assert col.replace("_", "").isalnum()

    def test_virgula_final_removida(self):
        df = pd.DataFrame(columns=["nome,", "edificio,,"])
        result = DataExtractor._normalize_columns(df)
        for col in result.columns:
            assert not col.endswith(",")

    def test_underscores_inicio_fim_removidos(self):
        df = pd.DataFrame(columns=[" nome ", "_col_"])
        result = DataExtractor._normalize_columns(df)
        for col in result.columns:
            assert not col.startswith("_")
            assert not col.endswith("_")

    def test_coluna_ja_normalizada_inalterada(self):
        df = pd.DataFrame(columns=["edificio", "nome_espaco"])
        result = DataExtractor._normalize_columns(df)
        assert list(result.columns) == ["edificio", "nome_espaco"]


# _sanitize_strings

class TestSanitizeStrings:

    def test_remove_carriage_return(self):
        df = pd.DataFrame({"col": ["valor\r"]})
        result = DataExtractor._sanitize_strings(df)
        assert result["col"].iloc[0] == "valor"

    def test_remove_carriage_return_literal(self):
        df = pd.DataFrame({"col": ["valor\\r"]})
        result = DataExtractor._sanitize_strings(df)
        assert result["col"].iloc[0] == "valor"

    def test_nan_string_para_na(self):
        df = pd.DataFrame({"col": ["nan"]})
        result = DataExtractor._sanitize_strings(df)
        assert pd.isna(result["col"].iloc[0])

    def test_strip_espacos(self):
        df = pd.DataFrame({"col": ["  valor  "]})
        result = DataExtractor._sanitize_strings(df)
        assert result["col"].iloc[0] == "valor"

    def test_remove_interrogacoes_inicio(self):
        df = pd.DataFrame({"col": ["???valor"]})
        result = DataExtractor._sanitize_strings(df)
        assert result["col"].iloc[0] == "valor"

    def test_coluna_numerica_nao_afetada(self):
        df = pd.DataFrame({"num": [1, 2, 3]})
        result = DataExtractor._sanitize_strings(df)
        assert list(result["num"]) == [1, 2, 3]

    def test_valor_normal_inalterado(self):
        df = pd.DataFrame({"col": ["SALA A"]})
        result = DataExtractor._sanitize_strings(df)
        assert result["col"].iloc[0] == "SALA A"


# extract_csv

class TestExtractCsv:

    def test_lê_csv_simples(self, extractor, tmp_data_dir):
        write_file(tmp_data_dir / "test.csv", "nome,edificio\nSALA A,ED. A\nSALA B,ED. B")
        df = extractor.extract_csv("test.csv")
        assert df is not None
        assert len(df) == 2

    def test_colunas_normalizadas(self, extractor, tmp_data_dir):
        write_file(tmp_data_dir / "test.csv", "Nome Espaco,Data Inicio\nSALA A,2024-10-15")
        df = extractor.extract_csv("test.csv")
        assert "nome_espaco" in df.columns
        assert "data_inicio" in df.columns

    def test_ficheiro_inexistente_devolve_none(self, extractor):
        result = extractor.extract_csv("nao_existe.csv")
        assert result is None

    def test_separador_ponto_virgula(self, extractor, tmp_data_dir):
        write_file(tmp_data_dir / "test.csv", "nome;edificio\nSALA A;ED. A")
        df = extractor.extract_csv("test.csv", sep=";")
        assert df is not None
        assert len(df) == 1

    def test_csv_vazio_devolve_dataframe_vazio(self, extractor, tmp_data_dir):
        write_file(tmp_data_dir / "test.csv", "nome,edificio\n")
        df = extractor.extract_csv("test.csv")
        assert df is not None
        assert len(df) == 0

    def test_strings_sanitizadas(self, extractor, tmp_data_dir):
        write_file(tmp_data_dir / "test.csv", "nome\nSALA A\r\n")
        df = extractor.extract_csv("test.csv")
        assert df is not None
        assert df["nome"].iloc[0] == "SALA A"

    def test_todas_colunas_dtype_str(self, extractor, tmp_data_dir):
        write_file(tmp_data_dir / "test.csv", "id,valor\n1,100\n2,200")
        df = extractor.extract_csv("test.csv")
        # dtype=str — todas as colunas devem ser object (string)
        for col in df.columns:
            assert df[col].dtype == object

    def test_encoding_latin1(self, extractor, tmp_data_dir):
        content = "nome\nSALA Ã\n"
        (tmp_data_dir / "test_latin.csv").write_text(content, encoding="latin-1")
        df = extractor.extract_csv("test_latin.csv", encoding="latin-1")
        assert df is not None
        assert len(df) == 1


# extract_sql_dump

class TestExtractSqlDump:

    def _make_sql(self, table: str, rows: list[str]) -> str:
        # Gera um INSERT INTO simples com os valores fornecidos
        values = ", ".join(f"({r})" for r in rows)
        return f"INSERT INTO `{table}` VALUES {values};"

    def test_extrai_registos_simples(self, extractor, tmp_data_dir):
        sql = self._make_sql("ocupacao", ["'001', 'SALA A', '2024-10-15'", "'002', 'SALA B', '2024-10-16'"])
        write_file(tmp_data_dir / "test.sql", sql)
        df = extractor.extract_sql_dump("test.sql", "ocupacao", ["id", "espaco", "data"])
        assert df is not None
        assert len(df) == 2

    def test_colunas_corretas(self, extractor, tmp_data_dir):
        sql = self._make_sql("ocupacao", ["'001', 'SALA A', '2024-10-15'"])
        write_file(tmp_data_dir / "test.sql", sql)
        df = extractor.extract_sql_dump("test.sql", "ocupacao", ["id", "espaco", "data"])
        assert list(df.columns) == ["id", "espaco", "data"]

    def test_ficheiro_inexistente_devolve_none(self, extractor):
        result = extractor.extract_sql_dump("nao_existe.sql", "tabela", ["col"])
        assert result is None

    def test_tabela_inexistente_devolve_dataframe_vazio(self, extractor, tmp_data_dir):
        sql = self._make_sql("outra_tabela", ["'001', 'valor'"])
        write_file(tmp_data_dir / "test.sql", sql)
        df = extractor.extract_sql_dump("test.sql", "tabela_que_nao_existe", ["id", "valor"])
        assert df is not None
        assert len(df) == 0

    def test_linhas_com_schema_errado_descartadas(self, extractor, tmp_data_dir):
        # Primeira linha tem 3 colunas (correto), segunda tem 2 (errado)
        sql = "INSERT INTO `ocupacao` VALUES ('001', 'SALA A', '2024-10-15'), ('002', 'SALA B');"
        write_file(tmp_data_dir / "test.sql", sql)
        df = extractor.extract_sql_dump("test.sql", "ocupacao", ["id", "espaco", "data"])
        assert df is not None
        assert len(df) == 1

    def test_colunas_normalizadas(self, extractor, tmp_data_dir):
        sql = self._make_sql("ocupacao", ["'001', 'SALA A'"])
        write_file(tmp_data_dir / "test.sql", sql)
        df = extractor.extract_sql_dump("test.sql", "ocupacao", ["ID Ocupacao", "Nome Espaco"])
        assert "id_ocupacao" in df.columns
        assert "nome_espaco" in df.columns

    def test_strings_sanitizadas(self, extractor, tmp_data_dir):
        sql = self._make_sql("ocupacao", ["'001', 'SALA A\r'"])
        write_file(tmp_data_dir / "test.sql", sql)
        df = extractor.extract_sql_dump("test.sql", "ocupacao", ["id", "espaco"])
        assert df is not None
        assert df["espaco"].iloc[0] == "SALA A"

    def test_multiplos_inserts(self, extractor, tmp_data_dir):
        sql = (
            "INSERT INTO `ocupacao` VALUES ('001', 'SALA A');\n"
            "INSERT INTO `ocupacao` VALUES ('002', 'SALA B');\n"
        )
        write_file(tmp_data_dir / "test.sql", sql)
        df = extractor.extract_sql_dump("test.sql", "ocupacao", ["id", "espaco"])
        assert df is not None
        assert len(df) == 2