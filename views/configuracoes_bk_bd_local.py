import streamlit as st
import pandas as pd
from database import executar_query, ler_dados
from views.investimentos import inicializar_banco_investimentos


def render_configuracoes():
    inicializar_banco_investimentos()

    usuario_atual = st.session_state.get('username')
    regra_usuario = st.session_state.get('role')

    st.header("⚙️ Configurações e Gestão")

    # Criamos as 4 abas
    tab_contas, tab_cats, tab_usuarios, tab_invest = st.tabs([
        "💳 Contas e Cartões",
        "📁 Hierarquia de Categorias",
        "👥 Gerenciar Usuários",
        "📈 Gestão de Investimentos"  # <-- Nova aba
    ])

    # --- ABA 1: CONTAS E CARTÕES ---
    # --- ABA 1: CONTAS E CARTÕES ---
    with tab_contas:
        if regra_usuario != 'Administrador':
            st.warning("⚠️ Acesso Restrito: Apenas administradores podem gerenciar contas.")
        else:
            # Tudo que já existia antes agora fica indentado dentro do 'else'
            st.subheader("Nova Conta")
            with st.form("form_conta", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                nome_c = c1.text_input("Nome da Conta")
                tipo_c = c2.selectbox("Tipo", ["Conta Corrente", "Cartão", "Dinheiro", "Investimento (Liquidez)",
                                               "Patrimônio (Imóvel)"])
                venc = c3.text_input("Vencimento (Ex: dia 05)")

                if st.form_submit_button("Salvar Conta"):
                    if nome_c:
                        executar_query("INSERT INTO cad_contas VALUES (?, ?, ?)", (nome_c.strip(), tipo_c, venc))
                        st.success("Conta adicionada com sucesso!")
                        st.rerun()

            st.divider()
            st.subheader("Contas Cadastradas")
            df_contas = ler_dados("cad_contas")
            if not df_contas.empty:
                st.dataframe(df_contas, use_container_width=True, hide_index=True)

            with st.expander("🗑️ Excluir Conta"):
                conta_excluir = st.selectbox("Selecione a conta para remover", df_contas['nome'].unique())
                if st.button("Confirmar Exclusão de Conta"):
                    executar_query("DELETE FROM cad_contas WHERE nome=?", (conta_excluir,))
                    st.warning(f"Conta '{conta_excluir}' removida.")
                    st.rerun()

        # --- ABA 2: HIERARQUIA DE CATEGORIAS ---
        with tab_cats:
            # 1. Colocamos a trava de segurança logo no início da aba
            if regra_usuario != 'Administrador':
                st.warning("⚠️ Acesso Restrito: Apenas administradores podem gerenciar a hierarquia de categorias.")
            else:
                # 2. Todo o seu código original fica indentado (para a direita) dentro do 'else'
                st.subheader("Nova Categoria / Subcategoria")
                with st.form("form_cat", clear_on_submit=True):
                    col1, col2, col3 = st.columns(3)
                    g = col1.text_input("Grupo (Ex: Essencial)")
                    sg = col2.text_input("Subgrupo (Ex: Moradia)")
                    sc = col3.text_input("Subcategoria (Ex: Aluguel)")

                    split = st.checkbox("Permitir Split (Divisão) nesta categoria?")

                    if st.form_submit_button("Salvar Categoria"):
                        if g and sg and sc:
                            # Inserção global (sem username)
                            executar_query("INSERT INTO cad_categorias VALUES (?, ?, ?, ?)",
                                           (g.strip(), sg.strip(), sc.strip(), split))
                            st.success("Hierarquia atualizada!")
                            st.rerun()

                st.divider()
                df_cats = ler_dados("cad_categorias")
                if not df_cats.empty:
                    st.write("### Hierarquia Atual")
                    st.dataframe(df_cats, use_container_width=True, hide_index=True)

                    with st.expander("🗑️ Remover Categoria"):
                        # Lógica para criar identificador de exclusão
                        df_cats['identificador'] = df_cats['grupo'] + " > " + df_cats['subgrupo'] + " > " + df_cats[
                            'subcategoria']
                        escolha = st.selectbox("Selecione para excluir", df_cats['identificador'].unique())

                        if st.button("Excluir Categoria"):
                            parts = escolha.split(" > ")
                            executar_query("""
                                DELETE FROM cad_categorias 
                                WHERE grupo=? AND subgrupo=? AND subcategoria=?
                            """, (parts[0], parts[1], parts[2]))
                            st.warning("Categoria removida.")
                            st.rerun()

        # --- ABA 3: GERENCIAR USUÁRIOS ---
        with tab_usuarios:
            # 1. Trava de segurança no início da aba
            if regra_usuario != 'Administrador':
                st.warning("⚠️ Acesso Restrito: Apenas administradores podem gerenciar usuários e permissões.")
            else:
                # 2. Todo o seu código original de gestão de usuários fica aqui dentro (indentado)
                st.subheader("👥 Gestão de Acessos")
                df_users = ler_dados("usuarios")

                if not df_users.empty:
                    # Mostra a tabela de usuários (removendo a coluna de senha por segurança)
                    df_view = df_users.drop(columns=['senha']) if 'senha' in df_users.columns else df_users
                    st.dataframe(df_view, use_container_width=True, hide_index=True)

                    st.divider()
                    st.write("### Aprovar ou Alterar Usuário")
                    user_sel = st.selectbox("Selecione o usuário para gerenciar", df_users['username'].unique())

                    if user_sel:
                        # Localiza a linha do usuário selecionado
                        row_user = df_users[df_users['username'] == user_sel].iloc[0]

                        with st.form("form_edit_user"):
                            col_u1, col_u2 = st.columns(2)

                            opcoes_nivel = ["Administrador", "Consegue Ler e Lançamentos", "Apenas Leitura"]
                            try:
                                idx_atual = opcoes_nivel.index(row_user['nivel'])
                            except:
                                idx_atual = 1

                            novo_nivel = col_u1.selectbox("Nível de Acesso", opcoes_nivel, index=idx_atual)
                            novo_aprovado = col_u2.checkbox("Aprovado para Login?", value=bool(row_user['aprovado']))

                            col_btn1, col_btn2 = st.columns(2)

                            if col_btn1.form_submit_button("💾 Salvar Alterações"):
                                executar_query("UPDATE usuarios SET nivel=?, aprovado=? WHERE username=?",
                                               (novo_nivel, novo_aprovado, user_sel))

                                if user_sel == st.session_state.get('username') and not novo_aprovado:
                                    st.warning("Atenção: Você removeu sua própria aprovação.")

                                st.success(f"Permissões do usuário '{user_sel}' atualizadas!")
                                st.rerun()

                            if col_btn2.form_submit_button("🗑️ Excluir Usuário"):
                                if user_sel == "admin" or user_sel == st.session_state.get('username'):
                                    st.error("Não é possível excluir o admin padrão ou o seu usuário atual.")
                                else:
                                    executar_query("DELETE FROM usuarios WHERE username=?", (user_sel,))
                                    st.success("Usuário excluído!")
                                    st.rerun()
                else:
                    st.info("Nenhum usuário encontrado.")

            # --- ABA 4: GESTÃO DE INVESTIMENTOS (Livre para todos os usuários) ---
            with tab_invest:
                usuario_atual = st.session_state.get('username')
                st.subheader(f"📊 Gestão de Investimentos - {usuario_atual}")

                # Sub-abas internas para não poluir a tela
                st_cad, st_trans, st_b3 = st.tabs(["🆕 Novo Ativo", "💸 Registrar Operação", "📥 Importar B3"])

                with st_cad:
                    st.write("### Cadastro Global de Ativos")
                    st.caption("Cadastre o ticker uma única vez para que ele fique disponível para todos.")
                    with st.form("form_novo_ativo", clear_on_submit=True):
                        c1, c2 = st.columns(2)
                        ticker = c1.text_input("Ticker (Ex: PETR4)").upper().strip()
                        nome_empresa = c2.text_input("Nome da Empresa/Fundo")
                        tipo_ativo = c1.selectbox("Classe", ["Ação", "FII", "ETF", "Tesouro", "Cripto", "BDR"])
                        setor_ativo = c2.selectbox("Setor", ["Bancos", "Energia", "Varejo", "Saúde", "Tecnologia",
                                                             "Commodities", "Imobiliário", "Saneamento", "Outros"])

                        if st.form_submit_button("✅ Salvar Ativo"):
                            if ticker and nome_empresa:
                                # INSERT OR IGNORE evita erro se o ticker já existir
                                executar_query(
                                    "INSERT OR IGNORE INTO ativos (ticker, nome, tipo, setor) VALUES (?,?,?,?)",
                                    (ticker, nome_empresa, tipo_ativo, setor_ativo))
                                st.success(f"Ativo {ticker} cadastrado com sucesso!")
                            else:
                                st.error("Preencha o Ticker e o Nome da Empresa.")

                with st_trans:
                    st.write("### Registrar Compra ou Venda")
                    df_ativos_disp = ler_dados("ativos")

                    if not df_ativos_disp.empty:
                        with st.form("form_trans_invest", clear_on_submit=True):
                            c1, c2 = st.columns(2)
                            data_op = c1.date_input("Data da Operação", pd.Timestamp.now())
                            ativo_sel = c1.selectbox("Selecione o Ativo", sorted(df_ativos_disp['ticker'].unique()))
                            tipo_op = c2.radio("Tipo de Operação", ["Compra", "Venda"], horizontal=True)
                            qtd = c2.number_input("Quantidade", min_value=0.000001, step=0.01, format="%.6f")
                            preco_un = c2.number_input("Preço Unitário (R$)", min_value=0.01, step=0.01, format="%.2f")
                            corretora = st.text_input("Corretora", value="Manual")

                            if st.form_submit_button("🚀 Confirmar Lançamento"):
                                executar_query("""
                                    INSERT INTO transacoes_invest 
                                    (usuario_id, data, ativo, quantidade, preco_unitario, tipo_operacao, corretora) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (usuario_atual, data_op, ativo_sel, qtd, preco_un, tipo_op, corretora))
                                st.success(f"{tipo_op} de {ativo_sel} registrada com sucesso!")
                                st.rerun()
                    else:
                        st.warning("⚠️ Cadastre os ativos na aba 'Novo Ativo' primeiro.")

                    # --- AGORA FORA DO ELSE (INDENTAÇÃO CORRIGIDA) ---
                    st.divider()
                    with st.expander("🔍 Visualizar e Ajustar Lançamentos", expanded=True):
                        st.write("### Histórico de Operações")
                        st.caption("Você pode editar os valores diretamente na tabela e clicar em 'Salvar Alterações'.")

                        df_ops = ler_dados("transacoes_invest")

                        if not df_ops.empty:
                            df_user_ops = df_ops[df_ops['usuario_id'] == usuario_atual].copy()

                            if not df_user_ops.empty:
                                # 1. Tabela Editável
                                df_editavel = st.data_editor(
                                    df_user_ops.sort_values(by='data', ascending=False),
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "id": st.column_config.NumberColumn("ID", disabled=True),
                                        "usuario_id": None,
                                        "data": st.column_config.DateColumn("Data"),
                                        "quantidade": st.column_config.NumberColumn("Qtd", format="%.6f"),
                                        "preco_unitario": st.column_config.NumberColumn("Preço (R$)", format="%.2f"),
                                    },
                                    key="editor_investimentos"
                                )

                                col_btn1, col_btn2 = st.columns(2)

                                # 2. Lógica para SALVAR EDIÇÕES
                                with col_btn1:
                                    if st.button("💾 Salvar Alterações"):
                                        for index, row in df_editavel.iterrows():
                                            executar_query("""
                                                UPDATE transacoes_invest 
                                                SET data=?, ativo=?, quantidade=?, preco_unitario=?, tipo_operacao=?, corretora=?
                                                WHERE id=? AND usuario_id=?
                                            """, (row['data'], row['ativo'], row['quantidade'], row['preco_unitario'],
                                                  row['tipo_operacao'], row['corretora'], row['id'], usuario_atual))
                                        st.success("Todas as alterações foram salvas!")
                                        st.rerun()

                                # 3. Lógica para EXCLUIR
                                with col_btn2:
                                    id_ajuste = st.number_input("ID para remover", min_value=0, step=1,
                                                                key="id_del_invest")
                                    if st.button("🗑️ Excluir Registro"):
                                        if id_ajuste > 0:
                                            executar_query("DELETE FROM transacoes_invest WHERE id=? AND usuario_id=?",
                                                           (id_ajuste, usuario_atual))
                                            st.warning(f"Operação ID {id_ajuste} removida!")
                                            st.rerun()
                            else:
                                st.info("Você ainda não possui transações registradas.")
                        else:
                            st.info("Nenhuma transação encontrada no banco de dados.")