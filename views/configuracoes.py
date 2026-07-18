import streamlit as st
import pandas as pd
from datetime import datetime

# Conexões com o Supabase criadas no seu database.py
from database import buscar_contas, buscar_categorias, supabase


def render_configuracoes():
    # Recuperamos os dados da sessão (essencial para filtrar no banco remoto)
    usuario_atual = st.session_state.get('username')
    regra_usuario = st.session_state.get('role')

    st.header("⚙️ Configurações e Gestão")

    # Criamos as 4 abas estruturadas
    tab_contas, tab_cats, tab_usuarios, tab_invest = st.tabs([
        "💳 Contas e Cartões",
        "📁 Hierarquia de Categorias",
        "👥 Gerenciar Usuários",
        "📈 Gestão de Investimentos"
    ])

    # ==========================================
    # --- ABA 1: CONTAS E CARTÕES ---
    # ==========================================
    with tab_contas:
        if regra_usuario != 'Administrador':
            st.warning("⚠️ Acesso Restrito: Apenas administradores podem gerenciar contas.")
        else:
            st.subheader("Nova Conta")
            with st.form("form_conta", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                nome_c = c1.text_input("Nome da Conta")
                tipo_c = c2.selectbox("Tipo", ["Conta Corrente", "Cartão", "Dinheiro", "Investimento (Liquidez)",
                                               "Patrimônio (Imóvel)"])
                venc = c3.text_input("Vencimento (Ex: dia 05)")

                if st.form_submit_button("Salvar Conta", width='stretch'):
                    if nome_c:
                        try:
                            # PREPARAÇÃO PARA SUPABASE: Vincula ao username da sessão
                            nova_conta = {
                                "nome": nome_c.strip(),
                                "tipo": tipo_c,
                                "vencimento": venc.strip() if venc else "",
                                "username": usuario_atual
                            }

                            supabase.table("cad_contas").insert(nova_conta).execute()

                            st.success(f"✅ Conta '{nome_c}' adicionada ao Supabase!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar conta: {e}")
                    else:
                        st.error("O campo 'Nome da Conta' é obrigatório.")

            st.divider()
            st.subheader("Contas Cadastradas")

            # BUSCA NO SUPABASE: Usamos a função de busca parametrizada
            df_contas_local = buscar_contas(usuario_atual)

            if not df_contas_local.empty:
                st.dataframe(df_contas_local[['nome', 'tipo', 'vencimento']], width='stretch', hide_index=True)

                with st.expander("🗑| Excluir Conta"):
                    opcoes_contas = sorted(df_contas_local['nome'].unique())
                    conta_excluir = st.selectbox("Selecione a conta para remover", opcoes_contas)

                    if st.button("Confirmar Exclusão", type="secondary", width='stretch'):
                        try:
                            # DELETE NO SUPABASE: Filtramos pelo nome e pelo username por segurança
                            supabase.table("cad_contas").delete().eq("nome", conta_excluir).eq("username",
                                                                                               usuario_atual).execute()

                            st.warning(f"A conta '{conta_excluir}' foi removida.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
            else:
                st.info("Nenhuma conta cadastrada ainda.")

    # ==========================================
    # --- ABA 2: HIERARQUIA DE CATEGORIAS ---
    # ==========================================
    with tab_cats:
        if regra_usuario != 'Administrador':
            st.warning("⚠️ Acesso Restrito: Apenas administradores podem gerenciar a hierarquia de categorias.")
        else:
            st.subheader("Nova Categoria / Subcategoria")

            # Seletor do tipo de fluxo para controlar dinamicamente a necessidade de 2 ou 3 níveis
            tipo_cat_fluxo = st.radio("Tipo do Fluxo:", ["Gasto", "Ganho"], horizontal=True, key="config_tipo_cat")

            with st.form("form_cat", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                g = col1.text_input("Grupo (Ex: Essencial ou Receitas)")
                sg = col2.text_input("Subgrupo (Ex: Moradia ou Salário)")

                # REGRA DE 2 NÍVEIS: Se for receita (Ganho), o terceiro nível é "Padrão" de forma compulsória
                if tipo_cat_fluxo == "Ganho":
                    sc = "Padrão"
                    col3.text_input("Subcategoria (Nível Desativado para Ganhos)", value="Padrão", disabled=True)
                    split = False
                else:
                    sc = col3.text_input("Subcategoria (Ex: Aluguel)")
                    split = st.toggle("Permitir Split (Divisão) nesta categoria?",
                                      help="Ativa o desmembramento de valores")

                if st.form_submit_button("Salvar Categoria", width='stretch'):
                    if g and sg and sc:
                        try:
                            tabela_alvo = "cad_categories" if "cad_categories" in globals() else "cad_categorias"

                            nova_cat = {
                                "grupo": g.strip(),
                                "subgrupo": sg.strip(),
                                "subcategoria": sc.strip(),
                                "permite_split": split if tipo_cat_fluxo == "Gasto" else False,
                                "username": usuario_atual
                            }

                            # Adiciona coluna tipo caso sua tabela suporte este controle explícito
                            nova_cat["tipo"] = tipo_cat_fluxo

                            supabase.table(tabela_alvo).insert(nova_cat).execute()

                            st.success("✅ Hierarquia atualizada no Supabase!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar categoria: {e}")
                    else:
                        st.error("Preencha os campos obrigatórios (Grupo e Subgrupo).")

            st.divider()

            # BUSCA NO SUPABASE
            df_cats_local = buscar_categorias(usuario_atual)

            if not df_cats_local.empty:
                # Garante que nulos venham como "Padrão" visualmente no grid
                df_cats_local['subcategoria'] = df_cats_local['subcategoria'].fillna("Padrão")

                st.write("### Hierarquia Atual")

                # Exibe colunas apropriadas incluindo tipo se disponível
                colunas_grid = ['grupo', 'subgrupo', 'subcategoria', 'permite_split']
                if 'tipo' in df_cats_local.columns:
                    colunas_grid.insert(0, 'tipo')

                st.dataframe(df_cats_local[colunas_grid], width='stretch', hide_index=True)

                with st.expander("🗑️ Remover Categoria"):
                    df_cats_local['identificador'] = df_cats_local['grupo'] + " > " + df_cats_local[
                        'subgrupo'] + " > " + df_cats_local['subcategoria']
                    escolha = st.selectbox("Selecione para excluir", sorted(df_cats_local['identificador'].unique()))

                    if st.button("Confirmar Exclusão de Categoria", type="secondary", width='stretch'):
                        try:
                            parts = escolha.split(" > ")
                            tabela_alvo = "cad_categories" if "cad_categories" in globals() else "cad_categorias"

                            # DELETE NO SUPABASE: Filtrando pelos 3 níveis + username por segurança
                            supabase.table(tabela_alvo).delete() \
                                .eq("grupo", parts[0]) \
                                .eq("subgrupo", parts[1]) \
                                .eq("subcategoria", parts[2]) \
                                .eq("username", usuario_atual) \
                                .execute()

                            st.warning(f"Categoria '{parts[2]}' removida.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
            else:
                st.info("Nenhuma categoria cadastrada. Defina sua estrutura acima.")

    # ==========================================
    # --- ABA 3: GERENCIAR USUÁRIOS ---
    # ==========================================
    with tab_usuarios:
        if regra_usuario != 'Administrador':
            st.warning("⚠️ Acesso Restrito: Apenas administradores podem gerenciar usuários e permissões.")
        else:
            st.subheader("👥 Gestão de Acessos")

            try:
                response = supabase.table("usuarios").select("*").execute()
                df_users = pd.DataFrame(response.data)
            except Exception as e:
                st.error(f"Erro ao carregar usuários: {e}")
                df_users = pd.DataFrame()

            if not df_users.empty:
                colunas_seguras = [c for c in df_users.columns if c != 'senha']
                st.dataframe(df_users[colunas_seguras], width='stretch', hide_index=True)

                st.divider()
                st.write("### Aprovar ou Alterar Usuário")

                lista_usuarios = sorted(df_users['username'].unique())
                user_sel = st.selectbox("Selecione o usuário para gerenciar", lista_usuarios, key="sel_user_admin")

                if user_sel:
                    row_user = df_users[df_users['username'] == user_sel].iloc[0]

                    with st.form("form_edit_user"):
                        col_u1, col_u2 = st.columns(2)

                        opcoes_nivel = ["Administrador", "Consegue Ler e Lançamentos", "Apenas Leitura"]

                        try:
                            nivel_atual = row_user.get('nivel', 'Apenas Leitura')
                            idx_atual = opcoes_nivel.index(nivel_atual)
                        except:
                            idx_atual = 2

                        novo_nivel = col_u1.selectbox("Nível de Acesso", opcoes_nivel, index=idx_atual)
                        novo_aprovado = col_u2.toggle("Aprovado para Login?",
                                                      value=bool(row_user.get('aprovado', False)))

                        btn_salvar, btn_excluir = st.columns(2)

                        if btn_salvar.form_submit_button("💾 Salvar Alterações", type="primary", width='stretch'):
                            try:
                                supabase.table("usuarios").update({
                                    "nivel": novo_nivel,
                                    "aprovado": novo_aprovado
                                }).eq("username", user_sel).execute()

                                st.success(f"✅ Permissões de '{user_sel}' atualizadas!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar: {e}")

                        if btn_excluir.form_submit_button("🗑️ Excluir Usuário", width='stretch'):
                            if user_sel.lower() == "admin" or user_sel == usuario_atual:
                                st.error(
                                    "🚫 Segurança: Você não pode excluir o admin padrão ou o seu próprio usuário logado.")
                            else:
                                try:
                                    supabase.table("usuarios").delete().eq("username", user_sel).execute()
                                    st.warning(f"Usuário '{user_sel}' removido com sucesso.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir usuário: {e}")
            else:
                st.info("Nenhum usuário encontrado no banco de dados.")

    # ==========================================
    # --- ABA 4: GESTÃO DE INVESTIMENTOS ---
    # ==========================================
    with tab_invest:
        st.subheader(f"📊 Gestão de Investimentos - {usuario_atual}")

        st_cad, st_trans = st.tabs(["🆕 Novo Ativo", "💸 Registrar Operação"])

        # SUB-ABA 4.1: NOVO ATIVO
        with st_cad:
            st.write("### Cadastro Global de Ativos")
            st.caption("Cadastre o ticker uma única vez para ficar disponível para todos.")
            with st.form("form_novo_ativo", clear_on_submit=True):
                c1, c2 = st.columns(2)
                ticker = c1.text_input("Ticker (Ex: PETR4)").upper().strip()
                nome_empresa = c2.text_input("Nome da Empresa/Fundo")
                tipo_ativo = c1.selectbox("Classe", ["Ação", "FII", "ETF", "Tesouro", "Cripto", "BDR"])
                setor_ativo = c2.selectbox("Setor", ["Bancos", "Energia", "Varejo", "Saúde", "Tecnologia",
                                                     "Commodities", "Imobiliário", "Saneamento", "Outros"])

                if st.form_submit_button("✅ Salvar Ativo", width='stretch'):
                    if ticker and nome_empresa:
                        try:
                            # UPSERT: Cadastra ou atualiza sem duplicar
                            novo_at = {"ticker": ticker, "nome": nome_empresa, "tipo": tipo_ativo, "setor": setor_ativo}
                            supabase.table("ativos").upsert(novo_at, on_conflict="ticker").execute()
                            st.success(f"✅ Ativo {ticker} sincronizado na nuvem!")
                        except Exception as e:
                            st.error(f"Erro ao salvar ativo: {e}")
                    else:
                        st.error("Preencha o Ticker e o Nome da Empresa.")

        # SUB-ABA 4.2: REGISTRAR OPERAÇÃO
        with st_trans:
            st.write("### Registrar Compra ou Venda")
            try:
                res_at = supabase.table("ativos").select("*").execute()
                df_ativos_disp = pd.DataFrame(res_at.data)
            except Exception as e:
                df_ativos_disp = pd.DataFrame()
                st.error(f"Erro ao buscar ativos: {e}")

            if not df_ativos_disp.empty:
                with st.form("form_trans_invest", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    data_op = c1.date_input("Data da Operação", datetime.now().date())
                    ativo_sel = c1.selectbox("Selecione o Ativo", sorted(df_ativos_disp['ticker'].unique()))
                    tipo_op = c2.radio("Tipo de Operação", ["Compra", "Venda"], horizontal=True)
                    qtd = c2.number_input("Quantidade", min_value=0.000001, step=0.01, format="%.6f")
                    preco_un = c2.number_input("Preço Unitário (R$)", min_value=0.01, step=0.01, format="%.2f")
                    corretora = st.text_input("Corretora", value="Manual")

                    if st.form_submit_button("🚀 Confirmar Lançamento", type="primary", width='stretch'):
                        try:
                            # AJUSTE SUPABASE UNIFICADO: Gravamos o 'username' na coluna 'username' por consistência do banco
                            nova_op = {
                                "username": usuario_atual,
                                "data": str(data_op),
                                "ativo": ativo_sel,
                                "quantidade": qtd,
                                "preco_unitario": preco_un,
                                "tipo_operacao": tipo_op,
                                "corretora": corretora.strip()
                            }
                            supabase.table("transacoes_invest").insert(nova_op).execute()
                            st.success(f"✅ {tipo_op} de {ativo_sel} registrada!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar operação: {e}")
            else:
                st.warning("⚠️ Cadastre os ativos na aba 'Novo Ativo' primeiro.")

            st.divider()
            with st.expander("🔍 Visualizar e Ajustar Lançamentos", expanded=True):
                st.write("### Histórico de Operações")

                try:
                    # AJUSTE SUPABASE UNIFICADO: Filtramos os investimentos do usuário pelo 'username'
                    res_inv = supabase.table("transacoes_invest").select("*").eq("username", usuario_atual).execute()
                    df_user_ops = pd.DataFrame(res_inv.data)
                except Exception as e:
                    df_user_ops = pd.DataFrame()
                    st.error(f"Erro ao carregar operações: {e}")

                if not df_user_ops.empty:
                    df_user_ops['data'] = pd.to_datetime(df_user_ops['data'])

                    # Editor interativo adaptado para celulares
                    df_editavel = st.data_editor(
                        df_user_ops.sort_values(by='data', ascending=False),
                        width='stretch',
                        hide_index=True,
                        column_config={
                            "id": st.column_config.TextColumn("ID", disabled=True),
                            "username": None,  # Oculta a coluna de usuário
                            "data": st.column_config.DateColumn("Data"),
                            "quantidade": st.column_config.NumberColumn("Qtd", format="%.6f"),
                            "preco_unitario": st.column_config.NumberColumn("Preço (R$)", format="%.2f"),
                        },
                        key="editor_investimentos"
                    )

                    col_btn1, col_btn2 = st.columns(2)

                    with col_btn1:
                        if st.button("💾 Salvar Alterações", width='stretch', type="primary"):
                            try:
                                st.info("Sincronizando alterações...")
                                for _, row in df_editavel.iterrows():
                                    supabase.table("transacoes_invest").update({
                                        "data": str(row['data'].date()) if hasattr(row['data'], 'date') else str(
                                            row['data']),
                                        "ativo": row['ativo'],
                                        "quantidade": row['quantidade'],
                                        "preco_unitario": row['preco_unitario'],
                                        "tipo_operacao": row['tipo_operacao'],
                                        "corretora": row['corretora']
                                    }).eq("id", row['id']).eq("username", usuario_atual).execute()
                                st.success("✅ Alterações salvas na nuvem!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar registros: {e}")

                    with col_btn2:
                        id_ajuste = st.text_input("ID para remover (Copie da tabela)", key="id_del_invest")
                        if st.button("🗑️ Excluir Registro", width='stretch'):
                            if id_ajuste:
                                try:
                                    supabase.table("transacoes_invest").delete().eq("id", id_ajuste).eq("username",
                                                                                                        usuario_atual).execute()
                                    st.warning(f"Operação ID {id_ajuste} removida!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir registro: {e}")
                else:
                    st.info("Nenhuma transação de investimento encontrada.")