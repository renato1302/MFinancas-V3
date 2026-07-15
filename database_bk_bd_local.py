import duckdb
import pandas as pd
import hashlib


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = duckdb.connect('financas.db')

    # Criamos a sequência para o ID se não existir
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_transacoes START 1")
    # Criamos a sequência para o ID de investimentos
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_invest START 1")

    # 1. TABELA DE TRANSAÇÕES (Atualizada com campo 'username')
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
            id_agrupador TEXT,
            username TEXT  -- Nova coluna para multiusuário
        )
    """)

    # 1.1 TABELA DE INVESTIMENTOS (Adicionada para corrigir o erro de ID)
    conn.execute("""
            CREATE TABLE IF NOT EXISTS transacoes_invest (
                id INTEGER PRIMARY KEY DEFAULT nextval('seq_invest'),
                ativo TEXT,
                quantidade FLOAT,
                valor_unitario FLOAT,
                data DATE,
                tipo_operacao TEXT, -- Compra ou Venda
                corretora TEXT,
                username TEXT
            )
        """)

    # MIRAÇÃO AUTOMÁTICA: Se a tabela já existia sem a coluna username, adicionamos agora
    cols = conn.execute("PRAGMA table_info('transacoes')").fetchall()
    if 'username' not in [c[1] for c in cols]:
        conn.execute("ALTER TABLE transacoes ADD COLUMN username TEXT")
        # Atribuímos os dados antigos ao 'admin' para não perder nada
        conn.execute("UPDATE transacoes SET username = 'admin' WHERE username IS NULL")

    # 2. TABELA DE CATEGORIAS (Global - Admin gerencia para todos)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cad_categorias (
            grupo TEXT, subgrupo TEXT, subcategoria TEXT, 
            permite_split BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (grupo, subgrupo, subcategoria)
        )
    """)

    # 3. TABELA DE CONTAS (Global - Admin gerencia para todos)
    conn.execute("CREATE TABLE IF NOT EXISTS cad_contas (nome TEXT PRIMARY KEY, tipo TEXT, vencimento TEXT)")

    # 4. TABELA DE USUÁRIOS
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, 
            senha TEXT, 
            email TEXT, 
            nivel TEXT, 
            aprovado BOOLEAN DEFAULT FALSE
        )
    """)


    # Criar admin padrão se não existir
    admin_exists = conn.execute("SELECT * FROM usuarios WHERE username = 'admin'").fetchone()
    if not admin_exists:
        conn.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?)",
                     ('admin', hash_password('admin123'), 'admin@email.com', 'Administrador', True))

    conn.close()



def executar_query(sql, params=()):
    conn = duckdb.connect('financas.db')
    try:
        conn.execute(sql, params)
    finally:
        conn.close()


def ler_dados(tabela):
    """Lê tabelas globais (categorias, contas, usuários)"""
    conn = duckdb.connect('financas.db')
    try:
        df = conn.execute(f"SELECT * FROM {tabela}").df()
    finally:
        conn.close()
    return df


def carregar_dados(username=None):
    """
    Lê as transações filtrando por usuário.
    Se for Admin, você pode optar por ver tudo ou apenas o seu.
    """
    conn = duckdb.connect('financas.db')
    try:
        if username:
            query = "SELECT * FROM transacoes WHERE username = ? ORDER BY data DESC"
            df = conn.execute(query, (username,)).df()
        else:
            # Caso queira ver tudo (uso administrativo)
            df = conn.execute("SELECT * FROM transacoes ORDER BY data DESC").df()
    finally:
        conn.close()

    if not df.empty:
        df['data'] = pd.to_datetime(df['data'])
    return df


def get_saldo_por_conta(nome_conta, username):
    """Retorna o saldo de uma conta específica para um usuário específico."""
    conn = duckdb.connect('financas.db')
    try:
        res = conn.execute("""
            SELECT COALESCE(SUM(valor), 0.0) 
            FROM transacoes 
            WHERE conta = ? AND username = ?
        """, (nome_conta, username)).fetchone()[0]
    finally:
        conn.close()
    return float(res)


def get_saldo_por_tipo(tipo_conta, username):
    """Soma o saldo de tipos de conta (ex: Investimento) para o usuário logado."""
    conn = duckdb.connect('financas.db')
    try:
        contas = conn.execute("SELECT nome FROM cad_contas WHERE tipo = ?", (tipo_conta,)).fetchall()
        nomes_contas = [c[0] for c in contas]

        if not nomes_contas:
            return 0.0

        placeholder = ', '.join(['?'] * len(nomes_contas))
        query = f"""
            SELECT COALESCE(SUM(valor), 0.0) 
            FROM transacoes 
            WHERE username = ? AND conta IN ({placeholder})
        """
        params = [username] + nomes_contas
        res = conn.execute(query, params).fetchone()[0]
    finally:
        conn.close()
    return float(res)


def get_resumo_patrimonio(username):
    """Retorna o resumo financeiro filtrado pelo usuário."""
    saldo_liquidez = get_saldo_por_tipo('Investimento (Liquidez)', username)
    saldo_contas = get_saldo_por_tipo('Conta Corrente', username)
    # Soma de ganhos e gastos totais para o dashboard
    df = carregar_dados(username)

    ganhos = df[df['valor'] > 0]['valor'].sum() if not df.empty else 0.0
    gastos = df[df['valor'] < 0]['valor'].sum() if not df.empty else 0.0

    return {
        "Disponível": saldo_liquidez + saldo_contas,
        "Ganhos": ganhos,
        "Gastos": abs(gastos),
        "Investido": saldo_liquidez
    }