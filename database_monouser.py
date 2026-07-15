import duckdb
import pandas as pd
import hashlib


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = duckdb.connect('financas.db')
    # Criamos a sequência para o ID se não existir
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_transacoes START 1")

    # Tabela de Transações - Garantindo id_agrupador para transferências
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_transacoes'),
            valor FLOAT, 
            tipo TEXT, 
            grupo TEXT, 
            subgrupo TEXT, 
            subcategoria TEXT,
            conta TEXT, 
            data DATE, 
            pago BOOLEAN, 
            recorrente BOOLEAN, 
            descricao TEXT,
            id_agrupador TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cad_categorias (
            grupo TEXT, subgrupo TEXT, subcategoria TEXT, 
            permite_split BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (grupo, subgrupo, subcategoria)
        )
    """)

    conn.execute("CREATE TABLE IF NOT EXISTS cad_contas (nome TEXT PRIMARY KEY, tipo TEXT, vencimento TEXT)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, 
            senha TEXT, 
            email TEXT, 
            nivel TEXT, 
            aprovado BOOLEAN DEFAULT FALSE
        )
    """)

    # --- MIGRAÇÃO AUTOMÁTICA ---
    # Verifica se a coluna id_agrupador existe (caso a tabela seja antiga)
    cols = conn.execute("PRAGMA table_info('transacoes')").fetchall()
    column_names = [c[1] for c in cols]
    if 'id_agrupador' not in column_names:
        conn.execute("ALTER TABLE transacoes ADD COLUMN id_agrupador TEXT")

    conn.close()


def executar_query(sql, dados=None):
    conn = duckdb.connect('financas.db')
    try:
        if dados:
            conn.execute(sql, dados)
        else:
            conn.execute(sql)
    finally:
        conn.close()


def ler_dados(tabela):
    conn = duckdb.connect('financas.db')
    try:
        df = conn.execute(f"SELECT * FROM {tabela}").df()
    finally:
        conn.close()
    return df


def carregar_dados():
    """Retorna todas as transações formatadas para o Dashboard"""
    conn = duckdb.connect('financas.db')
    try:
        df = conn.execute("SELECT * FROM transacoes ORDER BY data DESC").df()
    finally:
        conn.close()

    if not df.empty:
        # Garantir que a data é datetime para o Pandas não dar erro nos filtros
        df['data'] = pd.to_datetime(df['data'])
    return df


# --- FUNÇÕES DE SALDO (CRUCIAIS PARA O SEU PROBLEMA) ---

def get_saldo_por_conta(nome_conta):
    """
    Soma todos os valores (positivos e negativos) de uma conta específica.
    Se a transferência de saída for -1500 e a de entrada for +1500,
    o saldo refletirá corretamente.
    """
    conn = duckdb.connect('financas.db')
    try:
        # Usamos COALESCE para retornar 0.0 em vez de None caso não haja registros
        res = \
        conn.execute("SELECT COALESCE(SUM(valor), 0.0) FROM transacoes WHERE conta = ?", (nome_conta,)).fetchone()[0]
    finally:
        conn.close()
    return float(res)


def get_saldo_por_tipo(tipo_conta):
    """Soma o saldo de todas as contas que pertencem a um determinado tipo."""
    conn = duckdb.connect('financas.db')
    try:
        # 1. Busca os nomes das contas que possuem o tipo selecionado (ex: 'Investimento (Liquidez)')
        contas = conn.execute("SELECT nome FROM cad_contas WHERE tipo = ?", (tipo_conta,)).fetchall()
        nomes_contas = [c[0] for c in contas]

        if not nomes_contas:
            return 0.0

        # 2. Soma o valor de todas as transações vinculadas a esses nomes
        placeholder = ', '.join(['?'] * len(nomes_contas))
        query = f"SELECT COALESCE(SUM(valor), 0.0) FROM transacoes WHERE conta IN ({placeholder})"
        res = conn.execute(query, nomes_contas).fetchone()[0]
    finally:
        conn.close()
    return float(res)

def get_resumo_patrimonio():
    """
    Retorna um dicionário com os saldos dos seus principais ativos
    para facilitar a chamada no dashboard.
    """
    ativos = {
        "cofrinho": get_saldo_por_conta("Cofrinho CDI"),
        "apartamento": get_saldo_por_conta("Apartamento Planta")
    }
    ativos["total"] = ativos["cofrinho"] + ativos["apartamento"]
    return ativos