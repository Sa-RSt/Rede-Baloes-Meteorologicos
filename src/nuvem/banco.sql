-- Tabela principal de histórico de leituras dos balões
CREATE TABLE IF NOT EXISTS Leituras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    balao_id INTEGER NOT NULL,
    sensor VARCHAR(50) NOT NULL,
    leitura NUMERIC NOT NULL,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
    FOREIGN KEY (balao_id) REFERENCES Balões(id)
);

-- Tabela auxiliar para registo de balões
CREATE TABLE IF NOT EXISTS Baloes (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(50) NOT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Índices para otimizar as consultas da interface web
CREATE INDEX IF NOT EXISTS idx_leituras_balao ON Leituras(balao_id);
CREATE INDEX IF NOT EXISTS idx_leituras_data ON Leituras(data_hora);
