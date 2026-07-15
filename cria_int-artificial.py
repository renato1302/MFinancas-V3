CREATE TABLE inteligencia_categorias (
    id BIGSERIAL PRIMARY KEY,
    usuario_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    termo_extrato TEXT NOT NULL, -- Ex: 'ifood', 'uber', 'posto shell'
    grupo TEXT NOT NULL,         -- Ex: 'Despesas'
    subgrupo TEXT NOT NULL,      -- Ex: 'Alimentação'
    subcategoria TEXT,           -- Ex: 'Delivery'
    frequencia INTEGER DEFAULT 1, -- Quantas vezes você confirmou essa associação
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_usuario_termo UNIQUE (usuario_id, termo_extrato)
);