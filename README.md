# Pipeline ETL e Dashboard BI — Análise de Ocupação ESTG

## Visão Geral do Projeto

Sistema de Extração, Transformação e Carregamento (ETL) para um Data Warehouse dimensional que suporta a análise de ocupação de espaços letivos da Escola Superior de Tecnologia e Gestão (ESTG). O pipeline processa dados brutos de agendamentos e assiduidade académica, materializando-os num modelo Star Schema em MySQL. Uma camada de Business Intelligence baseada em Streamlit disponibiliza visualizações interativas sobre os dados carregados.

## Pré-requisitos

- **Python 3.10+**
- **MySQL Server 8.0+**
- **Pip** para instalação de dependências Python

### Dependências Python

```bash
pip install pandas sqlalchemy pymysql python-dotenv
```

### Dashboard BI

```bash
pip install -r streamlit-dashboard/requirements.txt
```

### Configuração de Credenciais

O ficheiro `.env.example` deve ser copiado para `.env` na raiz do repositório e preenchido com as credenciais de acesso à base de dados MySQL:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<password>
DB_NAME=dw_ocupacao
```

O mesmo ficheiro `.env` é utilizado tanto pelo pipeline ETL como pelo dashboard.

## Inicialização da Base de Dados

Antes da primeira execução, o script de DDL deve ser aplicado ao servidor MySQL:

```bash
mysql -u root -p < database/schema_dw.sql
```

Este script cria a base de dados `dw_ocupacao` e todas as tabelas do modelo dimensional (dimensões e tabela de factos), incluindo as colunas de controlo SCD2 (`Valid_From`, `Valid_From`, `Valid_To`, `Is_Active`) e as chaves estrangeiras da Facto_Ocupacao.

## Dados de Entrada

O pipeline espera encontrar os seguintes ficheiros no diretório `dados/`:

| Ficheiro | Descricao | Encoding | Separador |
|---|---|---|---|
| `PorSalaTurno.csv` | Registo de agendamentos de espacos | `cp1252` | `,` |
| `PorTurnoPresencas.csv` | Registo de assiduidade academica | `cp1252` | `,` |
| `curso_ucs(in).csv` | Dicionario mestre de cursos e UCs | `latin-1` | `;` |
| `script_espacos_salas_turnos.sql` | Dump SQL com metadados de responsaveis | `utf-8` | — |

## Guia de Execução

> **ATENCAO:** Todos os comandos devem ser executados a executados a partir da directoria raiz do repositorio. Os caminhos para o ficheiro `.env` e para a pasta `dados/` são relativos ao diretório de trabalho atual.

### Passo 1 — Limpeza do Data Warehouse

```bash
python processo_etl/cleanup_dw.py
```

Este utilitario executa as seguintes operacoes:
1. Desativa as verificacoes de chave estrangeira
2. Trunca todas as tabelas dinâmicas
3. Reinsere os registos dummy com Surrogate Key igual a zero em todas as dimensoes

### Passo 2 — Execucao do Pipeline ETL

```bash
python processo_etl/main.py
```

O orquestrador coordena sequencialmente as tres fases:

- **Extracao (Extract):** Le os ficheiros CSV e o dump SQL, normalizando os nomes das colunas para `snake_case`.
- **Transformacao (Transform):** Aplica regras de negocio — normalizacao de edificios, imputacao de valores nulos, extracao de turnos por expressao regular, classificacao de espacos e epocas, filtro de duracao anómala, merge semantico de presencas, e alinhamento final com o schema do Data Warehouse.
- **Carregamento (Load):** Insere ou atualiza dimensoes (SCD tipo 1 e tipo 2), gera as dimensoes estaticas (Dim_Hora, Dim_Data), e carrega a tabela de factos em lotes de 5000 registos.

O sistema produz registos de auditoria detalhados no terminal, incluindo volumes processados e metricas de integridade das Surrogate Keys.

### Passo 3 — Lancamento do Dashboard

```bash
streamlit run streamlit-dashboard/main.py
```

Inicia a interface de Business Intelligence num browser local. O dashboard disponibiliza cinco páginas:

- **Dashboard:** Indicadores-chave (KPIs), série temporal de ocupacao, distribuição por edificio, tabela de ocupações recentes e métricas de qualidade.
- **Ocupacao:** Mapa de calor por hora e dia da semana, top espacos e distribuição por tipo de atividade.
- **Espacos:** Analise detalhada por edificio, espaco e edificio com tabela de resumo agregado.
- **Relatorios:** Exportação dos dados filtrados em formato CSV.
- **ETL / Logs:** Monitorização da qualidade dos dados carregados.

As credenciais de acesso predefinidas sao `admin/estg2025` ou `docente/estg2025`.

## Arquitetura dos Modulos

| Modulo | Responsabilidade |
|---|---|
| `processo_etl/extract.py` | Ingestao de dados a partir de CSV e SQL dump |
| `processo_etl/transform.py` | Regras de transformacao e limpeza |
| `processo_etl/load.py` | Materializacao no MySQL com gestao de Surrogate Keys |
| `processo_etl/main.py` | Orquestrador do pipeline |
| `processo_etl/cleanup_dw.py` | Utilitario de limpeza e reposição de dummies |
| `streamlit-dashboard/` | Aplicacao Streamlit para visualizacao BI |

## Modelo Dimensional (Star Schema)

A Facto_Ocupacao encontra-se no centro do esquema, relacionando-se com oito dimensoes:

- `Dim_Data` — Calendario academico (2018-01-01 a 2035-12-31) com ano letivo, semestre, tipo de-sana, tipo de dia
- `Dim_Hora` — Relogio de 0 a 2359
- `Dim_Espaco` — Edificio, sala, categoria, escola responsavel, indicador online
- `Dim_Unidade_Curricular` — Codigo, designacao, ciclo de estudos (SCD tipo 2)
- `Dim_Curso` — Codigo e nome (SCD tipo 2)
- `Dim_Responsavel` — Docente responsavel
- `Dim_Turno` CH Designacao do turno
- `Dim_Tipo_Atividade` — Designacao da atividade
- `Dim_Estado_Agendamento` — Estado do agendamento
- `Dim_Epoca` — Descricao da epoca letiva

Metricas armazenadas na Facto_Ocupacao: `Duracao_Minutos`, `Numero_Presencas`, `Flag_Evento_Agregado`.

## Estrategia SCD

| Tipo | Dimensoes |
|---|---|
| SCD Tipo 2 | Dim_Espaco, Dim_Unidade_Curricular, Dim_Curso |
| SCD Tipo 1 | Dim_Responsavel, Dim_Turno, Dim_Tipo_Atividade, Dim_Estado_Agendamento, Dim_Epoca |

## Regras de Qualidade Aplicadas

1. Normalizacao de edificios — remocao de sufixos entre parenteses
2. Imputacao de responsaveis — `'Indefinido/N.D.'` para 77% de nulos
3. Reservas sem codigo curricular — mapeadas para `'SEM_UNIDADE / RESERVA_ADMIN'`
4. Extracao de turno via regex — valores nao correspondentes recebem `'N/D'`
5. Sessoes online detetadas por palavras-chave no edificio ou estado
6. Sessoes com duracao <= 0 ou > 360 minutos eliminadas
7. Merge de presencas por chave semantica (data, nome da UC, turno)
8. Codigo_UC tratado como string com remocao de sufixo decimal
