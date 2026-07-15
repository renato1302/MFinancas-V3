import streamlit as st
import pandas as pd
from database import ler_dados, executar_query, hash_password


def render_auth():
    st.title("🔐 Acesso ao Sistema Finanças Pro")
    st.write("Por favor, identifique-se para continuar.")

    tab_login, tab_cadastrar, tab_recuperar = st.tabs(["🔑 Login", "📝 Cadastrar", "❓ Esqueci a Senha"])

    with tab_login:
        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                if usuario and senha:
                    df_users = ler_dados("usuarios")
                    if not df_users.empty:
                        user_row = df_users[df_users['username'] == usuario]
                        if not user_row.empty:
                            if user_row.iloc[0]['senha'] == hash_password(senha):
                                # VERIFICAÇÃO DE APROVAÇÃO ADICIONADA AQUI
                                if user_row.iloc[0]['aprovado']:
                                    st.session_state['logged_in'] = True
                                    st.session_state['username'] = usuario
                                    st.session_state['role'] = user_row.iloc[0]['nivel']
                                    st.rerun()
                                else:
                                    st.error("⏳ Seu cadastro está pendente de aprovação pelo Administrador.")
                            else:
                                st.error("Senha incorreta.")
                        else:
                            st.error("Usuário não encontrado.")
                    else:
                        st.error("Nenhum usuário no banco. Faça o cadastro ou use o admin padrão (admin / admin123).")
                else:
                    st.warning("Preencha usuário e senha.")

    with tab_cadastrar:
        with st.form("form_cadastro"):
            novo_user = st.text_input("Novo Usuário")
            novo_email = st.text_input("E-mail")
            nova_senha = st.text_input("Senha", type="password")
            nivel = st.selectbox("Nível de Acesso Solicitado", ["Somente Leitura", "Consegue Ler e Lançamentos", "Administrador"])

            if st.form_submit_button("Solicitar Cadastro"):
                if novo_user and nova_senha and novo_email:
                    df_users = ler_dados("usuarios")
                    if not df_users.empty and novo_user in df_users['username'].values:
                        st.error("Este nome de usuário já existe.")
                    else:
                        # NOVO USUÁRIO ENTRA COM aprovado = False
                        executar_query("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?)",
                                       (novo_user.strip(), hash_password(nova_senha), novo_email.strip(), nivel, False))
                        st.success("Usuário cadastrado com sucesso! Aguarde o Administrador aprovar seu acesso.")
                else:
                    st.warning("Preencha todos os campos para cadastrar.")

    with tab_recuperar:
        with st.form("form_recuperar"):
            st.info("Digite seu usuário e e-mail cadastrado para redefinir sua senha.")
            rec_user = st.text_input("Usuário")
            rec_email = st.text_input("E-mail Cadastrado")
            nova_senha_rec = st.text_input("Nova Senha", type="password")

            if st.form_submit_button("Redefinir Senha"):
                if rec_user and rec_email and nova_senha_rec:
                    df_users = ler_dados("usuarios")
                    if not df_users.empty:
                        user_row = df_users[(df_users['username'] == rec_user) & (df_users['email'] == rec_email)]
                        if not user_row.empty:
                            executar_query("UPDATE usuarios SET senha=? WHERE username=?",
                                           (hash_password(nova_senha_rec), rec_user))
                            st.success("Senha atualizada! Volte à aba de Login.")
                        else:
                            st.error("Usuário ou e-mail incorretos.")
                else:
                    st.warning("Preencha todos os campos.")