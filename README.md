# Pipeline de ETL - Plataforma de Análise de Ocupação ESTG

Este repositório contém a implementação do processo de Extração, Transformação e Carregamento (ETL) para o Data Warehouse de suporte à análise da ocupação de espaços letivos da Escola Superior de Tecnologia e Gestão (ESTG). O sistema processa dados brutos de agendamentos e presenças num modelo dimensional (Star Schema) para fins de Business Intelligence.

## Requisitos do Sistema

* **Interpretador:** Python 3.10 ou superior.
* **Base de Dados:** MySQL Server 8.0+.
* **Esquema:** O modelo dimensional deve estar previamente criado (ver ficheiro `schema_dw.sql`).

## Configuração do Ambiente

O pipeline utiliza um ficheiro `.env` para gerir as credenciais de acesso à base de dados. Certifique-se de que o ficheiro `.env` está presente na raiz do projeto com as seguintes variáveis:
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.

Para instalar as dependências necessárias, execute:
```bash
pip install pandas sqlalchemy pymysql python-dotenv
```

## Estrutura de Dados (Input)

O pipeline espera encontrar uma diretoria `Dados/` na raiz do projeto com os seguintes ficheiros:

1. `PorSalaTurno.csv`: Registo de agendamentos (Encoding: cp1252).
2. `PorTurnoPresencas.csv`: Registo de assiduidade académica.
3. `script_espacos_salas_turnos.sql`: Dump SQL com metadados para enriquecimento da staging.

## Descrição dos Módulos

* **main.py**: Orquestrador do processo. Coordena a execução sequencial das fases e o cruzamento semântico de dados.
* **extract.py**: Módulo de ingestão. Inclui um parser para leitura de dumps SQL e normalização de nomes de colunas.
* **transform.py**: Motor de transformação. Aplica regras de limpeza, extração de turnos via expressões regulares e lógica de ocupação online (RF05).
* **load.py**: Camada de persistência. Gere Surrogate Keys, dimensões temporais e carregamento incremental da tabela de factos.
* **cleanup_dw.py**: Script utilitário para limpeza das tabelas de factos e dimensões dinâmicas (Fresh Start).

## Execução

1. **Limpeza do ambiente (opcional):**
   ```bash
   python cleanup_dw.py
   ```

2. **Execução do pipeline:**
   ```bash
   python main.py
   ```

O sistema gera logs detalhados na consola sobre o volume de dados processados e métricas de integridade das chaves dimensionais.
