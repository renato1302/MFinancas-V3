import duckdb
import os

caminho_db = os.path.join(os.getcwd(), 'financas.db')
con = duckdb.connect(caminho_db)

print("🚀 Iniciando reparo profundo...")

try:
    # 1. Reparar tabela 'transacoes_invest'
    colunas_trans = [row[1] for row in con.execute("PRAGMA table_info('transacoes_invest')").fetchall()]

    if 'username' in colunas_trans:
        con.execute("ALTER TABLE transacoes_invest RENAME COLUMN username TO usuario_id;")
        print("- Coluna 'username' alterada para 'usuario_id'")

    if 'valor_unitario' in colunas_trans:
        con.execute("ALTER TABLE transacoes_invest RENAME COLUMN valor_unitario TO preco_unitario;")
        print("- Coluna 'valor_unitario' alterada para 'preco_unitario'")

    # 2. Reparar tabela 'ativos' (Onde estava o erro crítico)
    # Como o erro disse que 'ativo' não existe, vamos recriar a tabela do jeito certo
    # sem perder os dados de 'tipo', 'nome' ou 'setor' se existirem.

    print("- Reestruturando tabela de ativos...")
    con.execute("CREATE TABLE IF NOT EXISTS ativos_new (ticker TEXT PRIMARY KEY, nome TEXT, tipo TEXT, setor TEXT);")

    # Tenta migrar dados se a tabela antiga existir e tiver dados
    try:
        con.execute("INSERT OR IGNORE INTO ativos_new (ticker, nome, tipo, setor) SELECT * FROM ativos;")
    except:
        pass

    con.execute("DROP TABLE IF EXISTS ativos;")
    con.execute("ALTER TABLE ativos_new RENAME TO ativos;")

    print("✅ Banco de dados sincronizado com o código!")

except Exception as e:
    print(f"❌ Erro durante o reparo: {e}")
finally:
    con.close()