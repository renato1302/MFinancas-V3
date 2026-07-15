import duckdb
import pandas as pd
from database import supabase


def migrar_tabela(nome_tabela_local, nome_tabela_supabase, chave_conflito=None):
    print(f"\n--- 🔄 Iniciando migração de: {nome_tabela_local} ---")

    con = duckdb.connect('financas.db')
    try:
        df = con.execute(f"SELECT * FROM {nome_tabela_local}").df()
        con.close()

        if df.empty:
            print(f"⚠️ Tabela {nome_tabela_local} está vazia localmente.")
            return

        registros_limpos = []
        for _, row in df.iterrows():
            dicionario_row = row.to_dict()
            novo_registro = {}

            for col, val in dicionario_row.items():
                if col == 'username': continue

                # 1. TRATAMENTO DE DATAS
                if 'data' in col.lower():
                    if pd.isna(val) or str(val).strip() in ['', 'None', 'NaT']:
                        novo_registro[col] = None
                    else:
                        try:
                            novo_registro[col] = str(pd.to_datetime(val).date())
                        except:
                            novo_registro[col] = None

                # 2. TRATAMENTO DE BOOLEANOS (AQUI ESTAVA O ERRO)
                # Colunas comuns de booleanos no seu projeto: 'pago', 'permite_split'
                elif col in ['pago', 'permite_split'] or isinstance(val, bool):
                    if pd.isna(val) or val == "":
                        novo_registro[col] = None  # Envia Nulo em vez de ""
                    else:
                        # Converte para booleano real
                        novo_registro[col] = bool(val) if str(val).lower() in ['true', '1', 't', 'y'] else False

                # 3. TRATAMENTO DE NÚMEROS E TEXTO
                else:
                    if pd.isna(val):
                        # Se for coluna de valor/numérica, usa 0. Se for texto, usa None ou ""
                        if df[col].dtype in ['float64', 'int64']:
                            novo_registro[col] = 0
                        else:
                            novo_registro[col] = None
                    else:
                        novo_registro[col] = val

            registros_limpos.append(novo_registro)

        # --- ENVIO ---
        sucesso = 0
        for r in registros_limpos:
            try:
                if chave_conflito:
                    supabase.table(nome_tabela_supabase).upsert(r, on_conflict=chave_conflito).execute()
                else:
                    supabase.table(nome_tabela_supabase).insert(r).execute()
                sucesso += 1
            except Exception as e_row:
                if '23505' not in str(e_row):  # Ignora erro de duplicado
                    print(f"❌ Erro no registro {r.get('id', 'S/ID')}: {e_row}")

        print(f"✅ Concluído: {sucesso} registros processados em {nome_tabela_supabase}.")

    except Exception as e:
        print(f"❌ Erro crítico em {nome_tabela_local}: {e}")


if __name__ == "__main__":
    # Mantendo as chaves que validamos na imagem e nos logs anteriores
    migrar_tabela("cad_categorias", "cad_categorias", "grupo,subgrupo,subcategoria")
    migrar_tabela("cad_contas", "cad_contas", "nome")
    migrar_tabela("transacoes", "transacoes", "id")
    migrar_tabela("ativos", "ativos", "ticker")
    migrar_tabela("transacoes_invest", "transacoes_invest", "id")