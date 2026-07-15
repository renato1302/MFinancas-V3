import streamlit as st
from database import init_db

# Configuração da página DEVE ser o primeiro comando
st.set_page_config(page_title="Finanças Pro 2026", layout="wide")

st.markdown("""
    <style>
    /* Ajuste de margens para telas pequenas */
    @media (max-width: 640px) {
        .main .block-container {
            padding-top: 1rem;
            padding-right: 0.5rem;
            padding-left: 0.5rem;
            padding-bottom: 1rem;
        }
        /* Faz os botões ocuparem a largura total no mobile */
        div.stButton > button {
            width: 100%;
        }
    }
    </style>
    """, unsafe_allow_html=True)

from views.auth import render_auth
from views.lancamentos import render_lancamentos
from views.dashboard import render_dashboard
from views.configuracoes import render_configuracoes
from views.investimentos import render_investimentos  # Importação mantida

init_db()

# Inicializa as variáveis de controle de sessão
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.session_state['role'] = None

if not st.session_state['logged_in']:
    render_auth()
else:
    with st.sidebar:
        st.write(f"👤 Bem-vindo(a), **{st.session_state['username']}**!")
        st.caption(f"🛡️ Acesso: {st.session_state['role']}")

        if st.button("Sair (Logout)"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = None
            st.session_state['role'] = None
            st.rerun()

        st.divider()
        st.title("💰 Finanças Pro")

        # --- MENU DINÂMICO ---
        # Mantendo sua lista original e a lógica de Admin
        opcoes_menu = ["Dashboard", "Lançamentos", "Investimentos"]

        if st.session_state['role'] == "Administrador":
            opcoes_menu.append("Configurações")

        menu = st.radio("Navegação", opcoes_menu)

    # --- RENDERIZAÇÃO DAS PÁGINAS ---
    # Aqui garantimos que o st.session_state['username'] seja passado se necessário,
    # embora os módulos que atualizamos já o capturem diretamente do session_state.

    if menu == "Dashboard":
        render_dashboard()

    elif menu == "Lançamentos":
        render_lancamentos()

    elif menu == "Investimentos":
        render_investimentos()

    elif menu == "Configurações":
        render_configuracoes()

    # Rodapé informativo para o usuário saber que está em ambiente seguro
    st.sidebar.divider()
    st.sidebar.caption(f"Conectado como: {st.session_state['username']}")
    st.sidebar.caption("Versão 2.0 - Multi-user Family")