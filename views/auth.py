import streamlit as st
from database import supabase


def render_auth():
    # 1. TÍTULO COMPACTO E RESPONSIVO
    st.markdown("## 🔐 Finanças Pro  \n<small>Acesso ao Sistema</small>", unsafe_allow_html=True)
    st.caption("Identifique-se para continuar.")

    # 2. ABAS OTIMIZADAS
    tab_login, tab_cadastrar, tab_recuperar = st.tabs(["🔑 Entrar", "📝 Criar", "❓ Senha"])

    # --- ABA 1: LOGIN COM SUPABASE AUTH ---
    with tab_login:
        email = st.text_input("E-mail", key="email_login")
        senha = st.text_input("Senha", type="password", key="pass_login")

        if st.button("Entrar no Sistema", type="primary", width='stretch'):
            if email and senha:
                try:
                    resposta = supabase.auth.sign_in_with_password({
                        "email": email.strip(),
                        "password": senha
                    })

                    if resposta.user:
                        user = resposta.user
                        metadata = user.user_metadata or {}

                        # Armazena na sessão
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = metadata.get('username', user.email)

                        # Se não tiver nível definido, assume 'Usuário' por padrão
                        st.session_state['role'] = metadata.get('nivel', 'Usuário')

                        st.session_state['usuario_id'] = user.id
                        st.session_state['user_id'] = user.id

                        st.success(f"Bem-vindo, {st.session_state['username']}!")
                        st.rerun()

                except Exception as e:
                    st.error("❌ E-mail ou senha incorretos. Verifique seus dados.")
            else:
                st.warning("⚠️ Preencha todos os campos.")

    # --- ABA 2: CADASTRO COM SUPABASE AUTH ---
    with tab_cadastrar:
        st.markdown("##### Novo Cadastro")
        novo_user = st.text_input("Usuário", key="reg_user")
        novo_email = st.text_input("E-mail", key="reg_email")
        nova_senha = st.text_input("Senha (mínimo 6 caracteres)", type="password", key="reg_pass")

        # 🚨 REMOVIDO: O selectbox de Nível foi removido para evitar que o usuário escolha ser admin.

        if st.button("Criar Conta", width='stretch'):
            if novo_user and nova_senha and novo_email:
                if len(nova_senha) < 6:
                    st.warning("⚠️ A senha deve ter no mínimo 6 caracteres.")
                else:
                    try:
                        # ✅ Cadastro Nativo: Força o nível 'Usuário' por padrão
                        resposta = supabase.auth.sign_up({
                            "email": novo_email.strip(),
                            "password": nova_senha,
                            "options": {
                                "data": {
                                    "username": novo_user.strip(),
                                    "nivel": "Usuário"  # <-- Nível padrão automático
                                }
                            }
                        })

                        if resposta.user:
                            st.success("✅ Conta criada com sucesso! Você já pode entrar e utilizar o sistema.")
                    except Exception as e:
                        st.error(f"Erro ao criar conta: {e}")
            else:
                st.warning("⚠️ Por favor, preencha todos os campos.")

    # --- ABA 3: RECUPERAÇÃO DE SENHA ---
    with tab_recuperar:
        st.info("Informe seu e-mail para receber as instruções de redefinição de senha.")
        rec_email = st.text_input("E-mail Cadastrado", key="rec_email")

        if st.button("Enviar E-mail de Recuperação", width='stretch'):
            if rec_email:
                try:
                    supabase.auth.reset_password_for_email(rec_email.strip())
                    st.success("✅ E-mail de recuperação enviado! Verifique sua caixa de entrada/spam.")
                except Exception as e:
                    st.error(f"Erro ao solicitar redefinição: {e}")
            else:
                st.warning("⚠️ Informe o e-mail cadastrado.")