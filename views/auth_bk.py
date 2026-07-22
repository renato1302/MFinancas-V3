import streamlit as st
import pandas as pd
from database import buscar_usuario, criar_usuario, hash_password


def render_auth():
    # 1. TÍTULO COMPACTO E RESPONSIVO (Mesmo padrão do Dashboard)
    st.markdown("## 🔐 Finanças Pro  \n<small>Acesso ao Sistema</small>", unsafe_allow_html=True)

    # Reduzimos o texto de instrução para ganhar altura
    st.caption("Identifique-se para continuar.")

    # 2. ABAS OTIMIZADAS PARA IPHONE (Nomes mais curtos evitam quebra lateral)
    tab_login, tab_cadastrar, tab_recuperar = st.tabs(["🔑 Entrar", "📝 Criar", "❓ Senha"])

    with tab_login:
        # Mantemos sua interface limpa para mobile
        usuario = st.text_input("Usuário", key="user_login")
        senha = st.text_input("Senha", type="password", key="pass_login")

        # Botão com largura total para facilitar o toque no iPhone
        if st.button("Entrar no Sistema", type="primary", width='stretch'):
            if usuario and senha:
                # --- MUDANÇA AQUI: Buscamos direto no Supabase ---
                user_info = buscar_usuario(usuario)

                if user_info:
                    # No Supabase, user_info já vem como um dicionário (uma linha de dados)
                    if user_info['senha'] == hash_password(senha):
                        if user_info['aprovado']:
                            st.session_state['logged_in'] = True
                            st.session_state['username'] = usuario
                            st.session_state['role'] = user_info['nivel']

                            # Guardamos o username como ID único, como você já fazia
                            st.session_state['usuario_id'] = usuario

                            st.success(f"Bem-vindo, {usuario}!")
                            st.rerun()
                        else:
                            st.error("⏳ Cadastro pendente de aprovação.")
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não encontrado.")
            else:
                st.warning("Preencha os campos.")

    with tab_cadastrar:
        st.markdown("##### Novo Cadastro")
        novo_user = st.text_input("Usuário", key="reg_user")
        novo_email = st.text_input("E-mail", key="reg_email")
        nova_senha = st.text_input("Senha", type="password", key="reg_pass")

        # Selectbox adaptado para mobile
        nivel = st.selectbox("Nível", ["Usuário", "Administrador"])

        if st.button("Solicitar Acesso", width='stretch'):
            if novo_user and nova_senha and novo_email:
                # 1. VERIFICAÇÃO: Chamamos a função do Supabase para ver se o nome já existe
                user_existente = buscar_usuario(novo_user.strip())

                if user_existente:
                    st.error("Este nome de usuário já está em uso.")
                else:
                    # 2. INSERÇÃO: Usamos a função criar_usuario do seu database.py
                    try:
                        criar_usuario(
                            username=novo_user.strip(),
                            senha=hash_password(nova_senha),
                            email=novo_email.strip(),
                            nivel=nivel
                        )
                        st.success("✅ Solicitação enviada! Aguarde a aprovação do Administrador.")
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")
            else:
                st.warning("⚠️ Por favor, preencha todos os campos.")

    with tab_recuperar:
        st.info("Informe os dados para redefinir.")
        rec_user = st.text_input("Usuário", key="rec_user")
        rec_email = st.text_input("E-mail", key="rec_email")
        nova_senha_rec = st.text_input("Nova Senha", type="password", key="rec_pass")

        if st.button("Atualizar Senha", width='stretch'):
            if rec_user and rec_email and nova_senha_rec:
                # 1. VERIFICAÇÃO: Buscamos o usuário no Supabase
                user_info = buscar_usuario(rec_user)

                # 2. VALIDAMOS: O usuário existe e o e-mail bate com o cadastrado?
                if user_info and user_info['email'] == rec_email.strip():
                    try:
                        # 3. ATUALIZAÇÃO: Comando direto do Supabase
                        supabase.table("usuarios") \
                            .update({"senha": hash_password(nova_senha_rec)}) \
                            .eq("username", rec_user) \
                            .execute()

                        st.success("✅ Senha alterada com sucesso! Agora você pode entrar na aba 'Login'.")
                    except Exception as e:
                        st.error(f"Erro ao atualizar no banco: {e}")
                else:
                    st.error("❌ Dados incorretos. Usuário ou E-mail não conferem.")
            else:
                st.warning("⚠️ Preencha todos os campos.")