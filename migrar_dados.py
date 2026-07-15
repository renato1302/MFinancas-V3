import duckdb
import pandas as pd
from database import supabase  # Importa a conexão que já configuramos


def migrar_tabela(nome_tabela):
    print(f"--- Iniciando migração da tabela: {nome_tabela} ---")

    conn = duckdb.connect('financas.db')
    try:
        df = conn.execute(f"SELECT * FROM {nome_tabela}").df()

        if df.empty:
            print(f"Tabela {nome_tabela} está vazia localmente. Pulando...")
            return

        # --- AJUSTE PARA O ERRO DE DATA ---
        # Procuramos colunas que são do tipo 'datetime' e convertemos para texto
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d')
        # ----------------------------------

        # Converte NaN para None
        dados = df.where(pd.notnull(df), None).to_dict(orient='records')

        # Envia para o Supabase
        response = supabase.table(nome_tabela).upsert(dados).execute()

        print(f"Sucesso! {len(dados)} registros migrados para {nome_tabela}.")

    except Exception as e:
        print(f"Erro ao migrar {nome_tabela}: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    # Lista das tabelas que queremos levar para a nuvem
    tabelas_para_migrar = ['cad_categorias', 'cad_contas', 'usuarios', 'transacoes']

    for tabela in tabelas_para_migrar:
        migrar_tabela(tabela)

    print("\n--- Migração Concluída! ---")