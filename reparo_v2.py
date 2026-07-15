import duckdb
import os

caminho_db = os.path.join(os.getcwd(), 'financas.db')
con = duckdb.connect(caminho_db)

print("🚀 Iniciando reparo com bypass de segurança...")

try:
    # 1. Desativar verificações temporariamente e ajustar transacoes_invest
    # Vamos renomear as colunas da tabela de transações primeiro
    colunas_trans = [row[1] for row in con.execute("PRAGMA table_info('transacoes_invest')").fetchall()]

    if 'username' in colunas_trans:
        con.execute("ALTER TABLE transacoes_invest RENAME COLUMN username TO usuario_id;")
        print("- Coluna 'username' corrigida para 'usuario_id'")

    if 'valor_unitario' in colunas_trans:
        con.execute("ALTER TABLE transacoes_invest RENAME COLUMN valor_unitario TO preco_unitario;")
        print("- Coluna 'valor_unitario' corrigida para 'preco_unitario'")

    # 2. Resolver o problema da tabela 'ativos'
    # Como não podemos dar DROP por causa da FK, vamos renomear a coluna existente
    # O erro anterior disse que existe a coluna 'tipo', então vamos ver o que tem lá
    colunas_ativos = [row[1] for row in con.execute("PRAGMA table_info('ativos')").fetchall()]

    if 'ativo' in colunas_ativos:
        con.execute("ALTER TABLE ativos RENAME COLUMN ativo TO ticker;")
        print("- Coluna 'ativo' corrigida para 'ticker' na tabela ativos")
    elif 'ticker' not in colunas_ativos:
        # Se não tem 'ativo' nem 'ticker', mas tem outras, vamos adicionar a coluna ticker
        con.execute("ALTER TABLE ativos ADD COLUMN ticker TEXT;")
        print("- Coluna 'ticker' adicionada à tabela ativos")

    print("✅ Sucesso! O banco foi sincronizado.")

except Exception as e:
    print(f"❌ Erro: {e}")
finally:
    con.close()