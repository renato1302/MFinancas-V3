import duckdb
import os

# Caminho para o seu banco atual
caminho_db = os.path.join(os.getcwd(), 'financas.db')
con = duckdb.connect(caminho_db)

try:
    # 1. Ajustando a tabela de transações de investimentos
    # Renomeia 'username' para 'usuario_id' se necessário
    con.execute("ALTER TABLE transacoes_invest RENAME COLUMN username TO usuario_id;")
    # Renomeia 'valor_unitario' para 'preco_unitario'
    con.execute("ALTER TABLE transacoes_invest RENAME COLUMN valor_unitario TO preco_unitario;")

    # 2. Ajustando a tabela de ativos
    # Renomeia 'ativo' para 'ticker' para bater com seus JOINs
    con.execute("ALTER TABLE ativos RENAME COLUMN ativo TO ticker;")

    print("✅ Banco de dados atualizado com sucesso! Seus dados foram preservados.")
except Exception as e:
    print(f"⚠️ Aviso: Algumas colunas já podem estar corretas ou o erro foi: {e}")
finally:
    con.close()