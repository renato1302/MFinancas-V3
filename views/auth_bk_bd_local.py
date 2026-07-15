import streamlit as st
import pandas as pd
from database import ler_dados, executar_query, hash_password


def render_auth():
    # 1. TÍTULO COMPACTO E RESPONSIVO (Mesmo padrão do Dashboard)
    st.markdown("## 🔐 Finanças Pro  \n<small>Acesso ao Sistema</small>", unsafe_allow_html=True)

    # Reduzimos o texto de instrução para ganhar altura
    st.caption("Identifique-se para continuar.")

    # 2. ABAS OTIMIZADAS PARA IPHONE (Nomes mais curtos evitam quebra lateral)
    tab_login, tab_cadastrar, tab_recuperar = st.tabs(["🔑 Entrar", "📝 Criar", "❓ Senha"])

    with tab_login:
        # Removi o st.form em favor de uma lógica direta para evitar bordas duplas que roubam espaço
        usuario = st.text_input("Usuário", key="user_login")
        senha = st.text_input("Senha", type="password", key="pass_login")

        # Botão com largura total (use_container_width) para facilitar o toque com o polegar
        if st.button("Entrar no Sistema", type="primary", use_container_width=True):
            if usuario and senha:
                df_users = ler_dados("usuarios")
                if not df_users.empty:
                    user_row = df_users[df_users['username'] == usuario]
                    if not user_row.empty:
                        if user_row.iloc[0]['senha'] == hash_password(senha):
                            if user_row.iloc[0]['aprovado']:
                                st.session_state['logged_in'] = True
                                st.session_state['username'] = usuario
                                st.session_state['role'] = user_row.iloc[0]['nivel']

                                if 'id' in user_row.columns:
                                    st.session_state['usuario_id'] = user_row.iloc[0]['id']
                                else:
                                    st.session_state['usuario_id'] = usuario

                                st.rerun()
                            else:
                                st.error("⏳ Cadastro pendente de aprovação.")
                        else:
                            st.error("Senha incorreta.")
                    else:
                        st.error("Usuário não encontrado.")
                else:
                    st.error("Banco vazio. Use admin/admin123.")
            else:
                st.warning("Preencha os campos.")

    with tab_cadastrar:
        st.markdown("##### Novo Cadastro")
        novo_user = st.text_input("Usuário", key="reg_user")
        novo_email = st.text_input("E-mail", key="reg_email")
        nova_senha = st.text_input("Senha", type="password", key="reg_pass")

        # Selectbox adaptado
        nivel = st.selectbox("Nível", ["Somente Leitura", "Lançamentos", "Administrador"])

        if st.button("Solicitar Acesso", use_container_width=True):
            if novo_user and nova_senha and novo_email:
                df_users = ler_dados("usuarios")
                if not df_users.empty and novo_user in df_users['username'].values:
                    st.error("Usuário já existe.")
                else:
                    executar_query("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?)",
                                   (novo_user.strip(), hash_password(nova_senha), novo_email.strip(), nivel, False))
                    st.success("Sucesso! Aguarde aprovação.")
            else:
                st.warning("Preencha tudo.")

    with tab_recuperar:
        st.info("Informe os dados para redefinir.")
        rec_user = st.text_input("Usuário", key="rec_user")
        rec_email = st.text_input("E-mail", key="rec_email")
        nova_senha_rec = st.text_input("Nova Senha", type="password", key="rec_pass")

        if st.button("Atualizar Senha", use_container_width=True):
            if rec_user and rec_email and nova_senha_rec:
                df_users = ler_dados("usuarios")
                if not df_users.empty:
                    user_row = df_users[(df_users['username'] == rec_user) & (df_users['email'] == rec_email)]
                    if not user_row.empty:
                        executar_query("UPDATE usuarios SET senha=? WHERE username=?",
                                       (hash_password(nova_senha_rec), rec_user))
                        st.success("Senha alterada! Vá para Login.")
                    else:
                        st.error("Dados incorretos.")
            else:
                st.warning("Preencha tudo.")