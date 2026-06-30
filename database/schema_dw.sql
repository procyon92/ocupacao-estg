-- ==========================================================
-- Data Warehouse DDL - Target: MySQL 8.0+
-- Projeto: Análise da Ocupação de Espaços Letivos
-- ==========================================================

-- Criação da Base de Dados
CREATE DATABASE IF NOT EXISTS dw_ocupacao CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE dw_ocupacao;

-- 1. Dimensão Espaço (SCD Tipo 2)
CREATE TABLE IF NOT EXISTS Dim_Espaco (
    SK_Espaco INT AUTO_INCREMENT PRIMARY KEY,
    Edificio VARCHAR(60) NOT NULL,
    Nome_Espaco VARCHAR(60) NOT NULL,
    Categoria_Espaco VARCHAR(20) DEFAULT 'Sala',
    Escola_Responsavel VARCHAR(50) DEFAULT 'Indefinido/N.D.',
    is_online BOOLEAN DEFAULT FALSE,
    Departamento VARCHAR(60) DEFAULT 'N/D',
    -- Controlo SCD2
    Valid_From DATE NOT NULL,
    Valid_To DATE DEFAULT '9999-12-31',
    Is_Active BOOLEAN DEFAULT TRUE
);

-- 2. Dimensão Data (Calendário Académico)
CREATE TABLE IF NOT EXISTS Dim_Data (
    SK_Data INT PRIMARY KEY,
    DataCompleta DATE NOT NULL,
    Ano INT NOT NULL,
    Ano_Escolar VARCHAR(9) NOT NULL, 
    Mes INT NOT NULL,
    Numero_Semana INT NOT NULL,
    Dia INT NOT NULL,
    DiaSemana VARCHAR(15),
    Semestre INT,
    Tipo_Dia VARCHAR(50) DEFAULT 'Aula',
    Numero_Semana_Escolar INT DEFAULT 0
);

-- 2.1 Dimensão Época
CREATE TABLE IF NOT EXISTS Dim_Epoca (
    SK_Epoca INT AUTO_INCREMENT PRIMARY KEY,
    Descricao_Epoca VARCHAR(50) NOT NULL DEFAULT 'N/D'
);

-- 3. Dimensão Hora (Relógio Fixo)
CREATE TABLE IF NOT EXISTS Dim_Hora (
    SK_Hora INT PRIMARY KEY,
    Hora INT NOT NULL,
    Minuto INT NOT NULL
);

-- 4. Dimensão Unidade Curricular (SCD Tipo 2)
CREATE TABLE IF NOT EXISTS Dim_Unidade_Curricular (
    SK_Unidade_Curricular INT AUTO_INCREMENT PRIMARY KEY,
    Codigo_UC VARCHAR(30) NOT NULL,
    Designacao_UC VARCHAR(120) DEFAULT 'SEM_UNIDADE / RESERVA_ADMIN',
    Ciclo_Estudo VARCHAR(50) DEFAULT 'N/D',
    -- Controlo SCD2
    Valid_From DATE NOT NULL,
    Valid_To DATE DEFAULT '9999-12-31',
    Is_Active BOOLEAN DEFAULT TRUE
);

-- 5. Dimensão Curso (SCD Tipo 2)
CREATE TABLE IF NOT EXISTS Dim_Curso (
    SK_Curso INT AUTO_INCREMENT PRIMARY KEY,
    Codigo_Curso VARCHAR(10) DEFAULT 'N/D',
    Nome_Curso VARCHAR(120) DEFAULT 'N/D',
    -- Controlo SCD2
    Valid_From DATE NOT NULL,
    Valid_To DATE DEFAULT '9999-12-31',
    Is_Active BOOLEAN DEFAULT TRUE
);

-- 6. Dimensão Responsável
CREATE TABLE IF NOT EXISTS Dim_Responsavel (
    SK_Responsavel INT AUTO_INCREMENT PRIMARY KEY,
    Docente_Responsavel VARCHAR(120) NOT NULL DEFAULT 'Indefinido/N.D.' 
);

-- 7. Dimensão Tipo de Atividade
CREATE TABLE IF NOT EXISTS Dim_Tipo_Atividade (
    SK_Tipo_Atividade INT AUTO_INCREMENT PRIMARY KEY,
    Designacao_Atividade VARCHAR(50) NOT NULL
);

-- 8. Dimensão Estado do Agendamento
CREATE TABLE IF NOT EXISTS Dim_Estado_Agendamento (
    SK_Estado_Agendamento INT AUTO_INCREMENT PRIMARY KEY,
    Estado VARCHAR(25) NOT NULL
);

-- 9. Dimensão Turno
CREATE TABLE IF NOT EXISTS Dim_Turno (
    SK_Turno INT AUTO_INCREMENT PRIMARY KEY,
    Designacao_Turno VARCHAR(10) NOT NULL
);

-- 10. Tabela de Factos Ocupação
CREATE TABLE IF NOT EXISTS Facto_Ocupacao (
    SK_Data INT NOT NULL,
    SK_Hora_Inicio INT NOT NULL,
    SK_Hora_Fim INT NOT NULL,
    SK_Espaco INT NOT NULL,
    SK_Unidade_Curricular INT NOT NULL,
    SK_Curso INT NOT NULL,
    SK_Responsavel INT NOT NULL,
    SK_Tipo_Atividade INT NOT NULL,
    SK_Estado_Agendamento INT NOT NULL,
    SK_Turno INT NOT NULL,
    SK_Epoca INT NOT NULL, 
    
    ID_Ocupacao VARCHAR(50) PRIMARY KEY,
    Duracao_Minutos INT DEFAULT 0,
    Numero_Presencas INT DEFAULT 0,
    Flag_Evento_Agregado BOOLEAN DEFAULT FALSE,
    
    FOREIGN KEY (SK_Data) REFERENCES Dim_Data(SK_Data),
    FOREIGN KEY (SK_Hora_Inicio) REFERENCES Dim_Hora(SK_Hora),
    FOREIGN KEY (SK_Hora_Fim) REFERENCES Dim_Hora(SK_Hora),
    FOREIGN KEY (SK_Espaco) REFERENCES Dim_Espaco(SK_Espaco),
    FOREIGN KEY (SK_Unidade_Curricular) REFERENCES Dim_Unidade_Curricular(SK_Unidade_Curricular),
    FOREIGN KEY (SK_Curso) REFERENCES Dim_Curso(SK_Curso),
    FOREIGN KEY (SK_Responsavel) REFERENCES Dim_Responsavel(SK_Responsavel),
    FOREIGN KEY (SK_Tipo_Atividade) REFERENCES Dim_Tipo_Atividade(SK_Tipo_Atividade),
    FOREIGN KEY (SK_Estado_Agendamento) REFERENCES Dim_Estado_Agendamento(SK_Estado_Agendamento),
    FOREIGN KEY (SK_Turno) REFERENCES Dim_Turno(SK_Turno),
    FOREIGN KEY (SK_Epoca) REFERENCES Dim_Epoca(SK_Epoca)
);

-- Criação de Índices (Otimização query)
CREATE INDEX idx_facto_data ON Facto_Ocupacao(SK_Data);
CREATE INDEX idx_facto_espaco ON Facto_Ocupacao(SK_Espaco);
CREATE INDEX idx_facto_uc ON Facto_Ocupacao(SK_Unidade_Curricular);
CREATE INDEX idx_facto_curso ON Facto_Ocupacao(SK_Curso);