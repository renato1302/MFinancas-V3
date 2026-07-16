import streamlit as st
# Removida a importação do init_db que não existe mais

# 1. Configuração da página (DEVE ser o primeiro comando)
st.set_page_config(page_title="Finanças Pro 2026", layout="wide")

# 2. CSS para Mobile (iPhone)
st.markdown("""
    <style>
    /* ... seu código CSS continua igual ... */
    </style>
    """, unsafe_allow_html=True)

# 3. Importações das Visões
from views.auth import render_auth
from views.lancamentos import render_lancamentos
from views.dashboard import render_dashboard
from views.configuracoes import render_configuracoes
from views.investimentos import render_investimentos

# 4. Inicialização do Banco (LINHA REMOVIDA)
# O Supabase já está inicializado dentro do database.py

# 5. Inicialização do Estado da Sessão
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.session_state['role'] = None

# 6. Lógica de Navegação Principal
if not st.session_state['logged_in']:
    render_auth()
else:
    # Este bloco só executa se o usuário estiver logado
    with st.sidebar:
        st.write(f"👤 Bem-vindo(a), **{st.session_state['username']}**!")
        st.caption(f"🛡️ Acesso: {st.session_state['role']}")

        if st.button("Sair (Logout)"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = None
            st.session_state['role'] = None
            st.rerun()

        # --- SELETOR DE TEMA (MODO CLARO/ESCURO) ---
        st.divider()
        tema = st.radio(
            "🌓 Aparência",
            ["Escuro", "Claro"],
            horizontal=True,
            key="tema_global"
        )

        # Define as variáveis de cores baseadas na escolha para os gráficos
        if tema == "Escuro":
            st.session_state['template_grafico'] = "plotly_dark"
            st.session_state['cor_texto'] = "white"
        else:
            st.session_state['template_grafico'] = "plotly_white"
            st.session_state['cor_texto'] = "#1E1E1E"

        st.divider()
        st.title("💰 Finanças Pro")

        # --- MENU DINÂMICO ---
        opcoes_menu = ["Dashboard", "Lançamentos", "Investimentos"]
        if st.session_state['role'] == "Administrador":
            opcoes_menu.append("Configurações")

        menu = st.radio("Navegação", opcoes_menu)

    # 7. Renderização das Páginas conforme o Menu Selecionado
    if menu == "Dashboard":
        render_dashboard()
    elif menu == "Lançamentos":
        render_lancamentos()
    elif menu == "Investimentos":
        render_investimentos()
    elif menu == "Configurações":
        render_configuracoes()