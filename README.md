# Pipeline ETL — Plataforma de Análise de Ocupação ESTG

Pipeline de Extração, Transformação e Carregamento (ETL) para o Data Warehouse de suporte à análise da ocupação de espaços letivos da ESTG. Processa dados brutos de agendamentos e presenças num modelo dimensional (Star Schema) para fins de Business Intelligence.

## Requisitos do Sistema

* **Interpretador:** Python 3.10+
* **Base de Dados:** MySQL Server 8.0+
* **Esquema:** Executar `schema_dw.sql` antes da primeira utilização.

## Configuração do Ambiente

O pipeline utiliza um ficheiro `.env` para credenciais de acesso:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<password>
DB_NAME=dw_ocupacao
```

Dependências:
```bash
pip install pandas sqlalchemy pymysql python-dotenv
```

## Estrutura de Dados (Input)

O pipeline espera uma diretoria `Dados/` com:

| Ficheiro | Descrição | Encoding | Separador |
|---|---|---|---|
| `PorSalaTurno.csv` | Registo de agendamentos de espaços | `cp1252` | `,` |
| `PorTurnoPresencas.csv` | Registo de assiduidade académica | `cp1252` | `,` |
| `curso_ucs(in).csv` | Dicionário mestre de cursos/UCs | `latin-1` | `;` |
| `script_espacos_salas_turnos.sql` | Dump SQL com metadados de responsáveis | `utf-8` | — |

## Arquitetura dos Módulos (SRP)

Cada módulo tem responsabilidade única:

| Módulo | Responsabilidade |
|---|---|
| **`extract.py`** | Ingestão de dados. Lê CSVs/SQL e normaliza colunas para `snake_case`. Sem transformações de negócio. |
| **`transform.py`** | Transformação e regras de negócio. Limpeza de strings, imputação de nulos, normalização de edifícios, extração de turnos (regex), flag `is_online`, filtros de outliers, merge semântico de presenças, e mapeamento final para PascalCase do schema DW. |
| **`load.py`** | Materialização no MySQL. Gestão de Surrogate Keys (SCD Tipo 1), geração de Dim_Hora, inserção de dummies (SK=0), e carregamento em lote da Facto_Ocupacao. |
| **`main.py`** | Orquestrador. Coordena E→T→L sem conter lógica de negócio. |
| **`cleanup_dw.py`** | Utilitário para limpeza (truncate) e reposição de dummies. |

## Regras de Transformação Aplicadas

Conforme definido no `mapa_logico_dados.xlsx` e `relatorio_projeto_ESTG.pdf`:

1. **Normalização de Edifícios:** Remoção de sufixos em parênteses (e.g. `Edifício A (ESTG)` → `EDIFÍCIO A`) para resolver as 320+ inconsistências hierárquicas.
2. **Imputação de Responsáveis:** `pessoa_resp` com 77% de nulos → `'Indefinido/N.D.'` na `Dim_Responsavel`.
3. **Reservas sem UC:** 2.502 registos sem atributos académicos → `'SEM_UNIDADE / RESERVA_ADMIN'` na `Dim_Unidade_Curricular`.
4. **Extração de Turnos:** Regex `\b(TP\d*|T\d+|P\d+|PL\d+|S\d+|OT\d+)\b` aplicada ao campo de descrição. Falhas → `'N/D'`.
5. **Flag Online (RF05):** `is_online = TRUE` quando `edificio` ou `estado` contém `Online|Ensino a Distância|Virtual|Zoom`. Atributo reside na `Dim_Espaco`.
6. **Filtro de Outliers:** Sessões com duração ≤ 0 ou > 360 minutos (6h) são eliminadas. Datas nulas/corrompidas (`0000-00-00`) são excluídas.
7. **Merge de Presenças:** Chave semântica `Data (date-part) + UPPER(Nome_UC) + Turno`, com imputação de `0` onde não há correspondência.
8. **Codigo_UC:** Casting estrito para string com remoção de sufixo `.0` (anti float-poisoning).
9. **Dim_Data:** Calendário de 2018-01-01 a 2035-12-31, com `Numero_Semana`, `Ano_Letivo`, `Semestre`, `Epoca_Exame`, `Tipo_Dia` e `DiaSemana` em português.

## Execução

1. **Limpeza do ambiente (opcional — Fresh Start):**
   ```bash
   python cleanup_dw.py
   ```

2. **Execução do pipeline:**
   ```bash
   python main.py
   ```

O sistema gera logs detalhados na consola com volumes processados e métricas de integridade das Surrogate Keys.

## Modelo Dimensional (Star Schema)

```
                  ┌── Dim_Data (Calendário Académico)
                  ├── Dim_Hora (Relógio 0-2359)
                  ├── Dim_Espaco (Edifício + Sala + is_online)
                  ├── Dim_Unidade_Curricular (Código + Designação + Ciclo)
Facto_Ocupacao ───┼── Dim_Curso (Código + Nome)
                  ├── Dim_Responsavel (Nome)
                  ├── Dim_Turno (Designação)
                  ├── Dim_Tipo_Atividade (Designação)
                  └── Dim_Estado_Agendamento (Estado)
```

Métricas da Facto: `Duracao_Minutos`, `Numero_Presencas`, `Flag_Evento_Agregado`.
