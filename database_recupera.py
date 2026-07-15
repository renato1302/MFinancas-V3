import duckdb


def forcar_recuperacao_total():
    conn = duckdb.connect('financas.db')
    seu_usuario = 'renato'

    try:
        print(f"--- ⚠️ FORÇANDO RECUPERAÇÃO TOTAL PARA: {seu_usuario} ---")

        # 1. Primeiro, vamos ver o que diabos está escrito na coluna username atualmente
        amostra = conn.execute("SELECT DISTINCT username FROM transacoes").fetchall()
        print(f"Valores atuais encontrados na coluna username: {amostra}")

        # 2. Comando "Limpa Tudo": Atribui absolutamente TUDO ao seu usuário
        conn.execute(f"UPDATE transacoes SET username = '{seu_usuario}'")

        # 3. Verifica se funcionou
        verificacao = conn.execute(f"SELECT COUNT(*) FROM transacoes WHERE username = '{seu_usuario}'").fetchone()[0]

        print(f"✅ SUCESSO! Agora, {verificacao} de 124 registros pertencem ao usuário '{seu_usuario}'.")
        print("💡 Seus dados devem reaparecer no Dashboard agora.")

    except Exception as e:
        print(f"❌ Erro ao forçar atualização: {e}")
    finally:
        conn.close()
        print("--- Processo Finalizado ---")


if __name__ == "__main__":
    forcar_recuperacao_total()