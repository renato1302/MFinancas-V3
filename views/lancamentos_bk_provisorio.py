import streamlit as st
import pandas as pd
from database import executar_query, ler_dados
import uuid


def render_lancamentos():
    st.header("📝 Gestão de Lançamentos")

    df_contas = ler_dados("cad_contas")
    df_cats = ler_dados("cad_categorias")

    if df_contas.empty or df_cats.empty:
        st.warning("⚠️ O Administrador precisa cadastrar Contas e Hierarquia de Categorias nas Configurações primeiro.")
        return

    pode_editar = st.session_state.get('role') in ["Administrador", "Consegue Ler e Lançamentos"]

    # --- SEÇÃO 1: CADASTRO DE NOVO LANÇAMENTO ---
    if pode_editar:
        with st.expander("➕ Novo Lançamento", expanded=True):
            st.markdown("### 1. Tipo de Operação")
            tipo = st.radio("Selecione o tipo de movimentação:", ["Gasto", "Ganho", "Transferência"], horizontal=True)

            st.markdown("### 2. Classificação e Detalhes")
            c1, c2, c3 = st.columns(3)

            if tipo != "Transferência":
                with c1:
                    grupo_sel = st.selectbox("Grupo", sorted(df_cats['grupo'].unique()), key="new_grupo")
                with c2:
                    sub_opts = df_cats[df_cats['grupo'] == grupo_sel]['subgrupo'].unique()
                    subgrupo_sel = st.selectbox("Subgrupo", sorted(sub_opts), key="new_subgrupo")
                with c3:
                    subcat_opts = df_cats[(df_cats['grupo'] == grupo_sel) & (df_cats['subgrupo'] == subgrupo_sel)][
                        'subcategoria'].unique()
                    subcat_sel = st.selectbox("Subcategoria", sorted(subcat_opts), key="new_subcat")
            else:
                subcat_sel = "Transferência"
                grupo_sel = "Transferência"
                subgrupo_sel = "Transferência"
                st.info("Transferência: Selecione as contas de origem e destino abaixo.")

            st.divider()

            d1, d2, d3 = st.columns(3)
            with d1:
                valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f", key="new_valor")
            with d2:
                data_lanc = st.date_input("Data", value=pd.Timestamp.now(), key="new_data")
            with d3:
                conta_sel = st.selectbox("Conta / Cartão", sorted(df_contas['nome'].unique()), key="new_conta")

            desc = st.text_input("Descrição (Opcional)", key="new_desc")

            if tipo == "Transferência":
                conta_dest = st.selectbox("Conta de Destino", sorted(df_contas['nome'].unique()), key="new_conta_dest")

            if st.button("🚀 Confirmar Lançamento", type="primary"):
                if valor > 0:
                    try:
                        if tipo == "Transferência":
                            id_transf = str(uuid.uuid4())
                            # Saída
                            executar_query("""
                                INSERT INTO transacoes (valor, tipo, grupo, subgrupo, subcategoria, conta, data, descricao, id_agrupador)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (-valor, "Transferência", "Transferência", "Transferência", "Saída", conta_sel,
                                  data_lanc, f"TR: {desc}", id_transf))
                            # Entrada
                            executar_query("""
                                INSERT INTO transacoes (valor, tipo, grupo, subgrupo, subcategoria, conta, data, descricao, id_agrupador)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (valor, "Transferência", "Transferência", "Transferência", "Entrada", conta_dest,
                                  data_lanc, f"TR: {desc}", id_transf))
                        else:
                            valor_final = -valor if tipo == "Gasto" else valor
                            executar_query("""
                                INSERT INTO transacoes (valor, tipo, grupo, subgrupo, subcategoria, conta, data, descricao)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (valor_final, tipo, grupo_sel, subgrupo_sel, subcat_sel, conta_sel, data_lanc, desc))

                        st.success("Lançamento registrado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.error("O valor deve ser maior que zero.")

    # --- SEÇÃO 2: VISUALIZAÇÃO E EDIÇÃO/EXCLUSÃO ---
    st.divider()
    st.subheader("🔍 Histórico Recente")

    df_trans = ler_dados("transacoes")

    if not df_trans.empty:
        df_display = df_trans.copy()
        df_display['data'] = pd.to_datetime(df_display['data'])
        st.dataframe(df_display.sort_values(by='data', ascending=False), use_container_width=True)

        if pode_editar:
            with st.expander("📝 Editar ou Excluir Lançamento"):
                col_id, col_load = st.columns([1, 1])
                id_para_editar = col_id.number_input("Digite o ID do lançamento:", min_value=1, step=1)

                # Filtrar o registro
                registro = df_trans[df_trans['id'] == id_para_editar]

                if not registro.empty:
                    row = registro.iloc[0]
                    st.markdown("---")
                    st.caption(f"Editando ID: {id_para_editar}")

                    # Campos de Edição
                    e1, e2, e3 = st.columns(3)
                    with e1:
                        novo_valor_ed = st.number_input("Valor", value=abs(float(row['valor'])), step=0.01)
                    with e2:
                        nova_data_ed = st.date_input("Data", value=pd.to_datetime(row['data']))
                    with e3:
                        nova_conta_ed = st.selectbox("Conta", sorted(df_contas['nome'].unique()),
                                                     index=list(sorted(df_contas['nome'].unique())).index(row['conta']))

                    nova_desc_ed = st.text_input("Descrição", value=row['descricao'])

                    btn_update, btn_delete, _ = st.columns([1, 1, 2])

                    if btn_update.button("💾 Salvar Alterações", type="primary"):
                        # Ajusta o sinal do valor conforme o tipo original
                        valor_final_ed = -novo_valor_ed if row['tipo'] == "Gasto" else novo_valor_ed
                        if row['tipo'] == "Transferência":  # Mantém o sinal original se for TR
                            valor_final_ed = -novo_valor_ed if row['valor'] < 0 else novo_valor_ed

                        executar_query("""
                            UPDATE transacoes 
                            SET valor=?, data=?, conta=?, descricao=?
                            WHERE id=?
                        """, (valor_final_ed, nova_data_ed, nova_conta_ed, nova_desc_ed, id_para_editar))
                        st.success("Atualizado com sucesso!")
                        st.rerun()

                    if btn_delete.button("🗑️ Excluir Lançamento"):
                        # Se for transferência, idealmente excluiria o par (via id_agrupador)
                        if row['id_agrupador']:
                            executar_query("DELETE FROM transacoes WHERE id_agrupador=?", (row['id_agrupador'],))
                        else:
                            executar_query("DELETE FROM transacoes WHERE id=?", (id_para_editar,))

                        st.warning("Lançamento excluído!")
                        st.rerun()
                else:
                    st.info("Insira um ID válido acima para carregar os dados de edição.")
    else:
        st.info("Nenhum lançamento registrado ainda.")