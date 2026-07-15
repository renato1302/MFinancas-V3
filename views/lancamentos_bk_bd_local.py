import streamlit as st
import pandas as pd
from database import executar_query, ler_dados, carregar_dados
import uuid


def render_lancamentos():
    st.header("📝 Gestão de Lançamentos")

    # Recupera o usuário logado na sessão
    usuario_atual = st.session_state.get('username')

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

            usar_split = False
            if tipo != "Transferência":
                with c1:
                    grupo_sel = st.selectbox("Grupo", sorted(df_cats['grupo'].unique()), key="new_grupo")
                with c2:
                    sub_opts = df_cats[df_cats['grupo'] == grupo_sel]['subgrupo'].unique()
                    subgrupo_sel = st.selectbox("Subgrupo", sorted(sub_opts), key="new_subgrupo")
                with c3:
                    subcat_opts = df_cats[(df_cats['grupo'] == grupo_sel) & (df_cats['subgrupo'] == subgrupo_sel)][
                        'subcategoria'].unique()

                    # Lógica de Desmembramento (Split) recuperada do backup
                    permitir_split = False
                    if 'permite_split' in df_cats.columns:
                        permitir_split = df_cats[(df_cats['grupo'] == grupo_sel) &
                                                 (df_cats['subgrupo'] == subgrupo_sel)]['permite_split'].any()

                    if permitir_split:
                        usar_split = st.toggle("🧩 Desmembrar valor por subcategorias?",
                                               help="Ative para distribuir o valor total")

                    if not usar_split:
                        subcat_sel = st.selectbox("Subcategoria", sorted(subcat_opts), key="new_subcat")
            else:
                subcat_sel = "Transferência"
                grupo_sel = "Transferência"
                subgrupo_sel = "Transferência"
                st.info("💡 Use 'Transferência' para Cofrinho, Aplicações ou movimentação entre contas.")

            st.divider()

            d1, d2, d3 = st.columns(3)
            with d1:
                valor_total = st.number_input("Valor Total (R$)", min_value=0.0, step=0.01, format="%.2f",
                                              key="new_valor")
            with d2:
                data_lanc = st.date_input("Data", value=pd.Timestamp.now(), key="new_data")
            with d3:
                conta_sel = st.selectbox("Conta / Cartão (Origem)", sorted(df_contas['nome'].unique()), key="new_conta")

            desc = st.text_input("Descrição (Opcional)", key="new_desc")

            if tipo == "Transferência":
                conta_dest = st.selectbox("Conta de Destino", sorted(df_contas['nome'].unique()), key="new_conta_dest")

            # --- PROCESSAMENTO DO BOTÃO SALVAR ---

            # Caso A: Desmembramento (Split)
            if usar_split:
                st.info("Distribua o valor total abaixo:")
                df_split_data = pd.DataFrame({'Subcategoria': sorted(subcat_opts), 'Valor (R$)': 0.0})
                res_editor = st.data_editor(df_split_data, width='stretch', hide_index=True, key="editor_split")

                soma_atual = res_editor['Valor (R$)'].sum()
                diferenca = valor_total - soma_atual
                st.write(f"Soma: **R$ {soma_atual:.2f}** | Restante: **R$ {diferenca:.2f}**")

                if st.button("🚀 Confirmar Lançamento Desmembrado", type="primary"):
                    if abs(diferenca) > 0.01:
                        st.error("A soma das subcategorias não bate com o valor total.")
                    elif valor_total <= 0:
                        st.error("O valor deve ser maior que zero.")
                    else:
                        try:
                            id_agrupador = str(uuid.uuid4())[:8]
                            for _, row in res_editor.iterrows():
                                if row['Valor (R$)'] > 0:
                                    v_f = -row['Valor (R$)'] if tipo == "Gasto" else row['Valor (R$)']
                                    # ADICIONADO: username na query e nos parâmetros
                                    executar_query("""
                                            INSERT INTO transacoes (valor, tipo, grupo, subgrupo, subcategoria, conta, data, descricao, id_agrupador, username)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (v_f, tipo, grupo_sel, subgrupo_sel, row['Subcategoria'], conta_sel,
                                              data_lanc, f"{desc} [{row['Subcategoria']}]", id_agrupador,
                                              usuario_atual))
                            st.success("Nota desmembrada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar split: {e}")

            # Caso B: Lançamento Simples ou Transferência
            else:
                if st.button("🚀 Confirmar Lançamento", type="primary"):
                    if valor_total > 0:
                        try:
                            if tipo == "Transferência":
                                id_transf = str(uuid.uuid4())
                                # Saída
                                executar_query("""
                                        INSERT INTO transacoes (valor, tipo, grupo, subgrupo, subcategoria, conta, data, descricao, id_agrupador, username)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (-valor_total, "Transferência", "Transferência", "Transferência", "Saída",
                                          conta_sel,
                                          data_lanc, f"TR: {desc}", id_transf, usuario_atual))
                                # Entrada
                                executar_query("""
                                        INSERT INTO transacoes (valor, tipo, grupo, subgrupo, subcategoria, conta, data, descricao, id_agrupador, username)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (valor_total, "Transferência", "Transferência", "Transferência", "Entrada",
                                          conta_dest,
                                          data_lanc, f"TR: {desc}", id_transf, usuario_atual))
                                st.success("Transferência realizada!")
                            else:
                                valor_final = -valor_total if tipo == "Gasto" else valor_total
                                executar_query("""
                                        INSERT INTO transacoes (valor, tipo, grupo, subgrupo, subcategoria, conta, data, descricao, username)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (valor_final, tipo, grupo_sel, subgrupo_sel, subcat_sel, conta_sel, data_lanc,
                                          desc, usuario_atual))
                                st.success("Lançamento registrado!")

                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                    else:
                        st.error("O valor deve ser maior que zero.")

    # --- SEÇÃO 2: VISUALIZAÇÃO E EDIÇÃO ---
    st.divider()
    st.subheader("🔍 Lançamentos Recentes")

    # Carregando dados filtrados pelo usuário logado (Passo 1 do banco de dados)
    df_lista = carregar_dados(username=usuario_atual)

    if not df_lista.empty:
        # Preparação dos dados para exibição
        df_display = df_lista.copy()
        df_display['data'] = pd.to_datetime(df_display['data'])
        df_display = df_display.sort_values(by='data', ascending=False)

        # Filtro de Mês/Ano (Preservado do seu código original)
        df_display['mes_ano'] = df_display['data'].dt.strftime('%m/%Y')
        meses_disp = sorted(df_display['mes_ano'].unique(), reverse=True)
        mes_filtro = st.selectbox("Filtrar por Mês/Ano", ["Todos"] + meses_disp)

        if mes_filtro != "Todos":
            df_display = df_display[df_display['mes_ano'] == mes_filtro]

        colunas_vistas = ['id', 'data', 'tipo', 'grupo', 'subcategoria', 'conta', 'valor', 'descricao']
        st.dataframe(df_display[colunas_vistas], use_container_width=True, hide_index=True)

        # --- BLOCO DE EDIÇÃO (Suas funções originais integradas com segurança de usuário) ---
        with st.expander("🛠️ Editar ou Excluir Lançamento"):
            st.write("Identifique o ID na tabela acima para realizar alterações.")
            id_para_editar = st.number_input("Digite o ID do lançamento:", step=1, value=0)

            if id_para_editar > 0:
                # Segurança: Filtramos no DF que já pertence ao usuário
                row_sel = df_lista[df_lista['id'] == id_para_editar]

                if not row_sel.empty:
                    row = row_sel.iloc[0]
                    st.info(f"Editando registro: {row['tipo']} | Conta: {row['conta']} | Valor: R$ {row['valor']:.2f}")

                    with st.form("form_edicao_lanc"):
                        c_ed1, c_ed2, c_ed3 = st.columns(3)
                        nova_data_ed = c_ed1.date_input("Nova Data", value=pd.to_datetime(row['data']))

                        contas_lista = sorted(list(df_contas['nome'].unique()))
                        idx_conta = contas_lista.index(row['conta']) if row['conta'] in contas_lista else 0
                        nova_conta_ed = c_ed2.selectbox("Nova Conta", contas_lista, index=idx_conta)

                        novo_valor_ed = c_ed3.number_input("Novo Valor (R$)", value=abs(float(row['valor'])))
                        nova_desc_ed = st.text_input("Nova Descrição",
                                                     value=row['descricao'] if row['descricao'] else "")

                        col_btn1, col_btn2, _ = st.columns([1, 1, 2])

                        if col_btn1.form_submit_button("💾 Salvar Alterações", type="primary"):
                            # Lógica de sinais preservada
                            if row['tipo'] == "Transferência":
                                valor_final_ed = -novo_valor_ed if row['valor'] < 0 else novo_valor_ed
                            else:
                                valor_final_ed = -novo_valor_ed if row['tipo'] == "Gasto" else novo_valor_ed

                            executar_query("""
                                UPDATE transacoes 
                                SET valor=?, data=?, conta=?, descricao=?
                                WHERE id=? AND username=?
                            """, (valor_final_ed, nova_data_ed, nova_conta_ed, nova_desc_ed, id_para_editar,
                                  usuario_atual))
                            st.success("Registro atualizado com sucesso!")
                            st.rerun()

                        if col_btn2.form_submit_button("🗑️ Excluir"):
                            if row['id_agrupador']:
                                # Exclui o par (split ou transferência) apenas do usuário logado
                                executar_query("DELETE FROM transacoes WHERE id_agrupador=? AND username=?",
                                               (row['id_agrupador'], usuario_atual))
                                st.warning("Grupo de lançamentos excluído!")
                            else:
                                executar_query("DELETE FROM transacoes WHERE id=? AND username=?",
                                               (id_para_editar, usuario_atual))
                                st.warning("Lançamento excluído!")
                            st.rerun()
                else:
                    st.error("Erro: Lançamento não encontrado ou não pertence ao seu utilizador.")
    else:
        st.info(
            f"Olá {usuario_atual}, não encontramos lançamentos para a sua conta. Use o formulário acima para começar!")