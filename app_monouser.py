import streamlit as st
from database import init_db

# Configuração da página DEVE ser o primeiro comando
st.set_page_config(page_title="Finanças Pro 2026", layout="wide")

from views.auth import render_auth
from views.lancamentos import render_lancamentos
from views.dashboard import render_dashboard
from views.configuracoes import render_configuracoes
from views.investimentos import render_investimentos  # Importação já existente

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

        # --- ATUALIZAÇÃO DO MENU ---
        # Adicionamos "Investimentos" à lista de opções
        opcoes_menu = ["Dashboard", "Lançamentos", "Investimentos"]

        if st.session_state['role'] == "Administrador":
            opcoes_menu.append("Configurações")

        menu = st.radio("Navegação", opcoes_menu)

    # --- ROTEAMENTO DE TELAS ---
    if menu == "Dashboard":
        render_dashboard()
    elif menu == "Lançamentos":
        render_lancamentos()
    # --- NOVA CONDIÇÃO PARA INVESTIMENTOS ---
    elif menu == "Investimentos":
        render_investimentos()
    elif menu == "Configurações":
        render_configuracoes()