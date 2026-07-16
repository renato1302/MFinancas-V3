import streamlit as st
import time
from database import CONTAS_MODELO, inserir_contas_onboarding


def exibir_onboarding(username):
    # Configuração de estilo para centralizar e deixar o visual mais limpo
    st.markdown(
        """
        <style>
        .title-container {
            text-align: center;
            padding: 10px;
        }
        .subtitle-container {
            text-align: center;
            color: #6c757d;
            margin-bottom: 30px;
        }
        </style>
        """,
        unsafe_allow_html=True  # <-- CORRIGIDO AQUI!
    )

    st.markdown('<div class="title-container"><h1>🚀 Bem-vindo ao Finanças Pro!</h1></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle-container"><h4>Vamos organizar sua casa? Selecione abaixo os bancos e cartões que você utiliza no dia a dia para criarmos sua estrutura inicial.</h4></div>',
        unsafe_allow_html=True)

    # Abas para separar as opções de forma organizada
    tab_bancos, tab_cartoes, tab_outros = st.tabs([
        "🏦 Bancos e Contas",
        "💳 Cartões de Crédito",
        "💵 Carteira & Benefícios"
    ])

    # Lista temporária para armazenar o que o usuário selecionar
    contas_selecionadas = []

    # --- ABA 1: BANCOS (CONTA CORRENTE) ---
    with tab_bancos:
        st.subheader("Bancos onde você tem conta:")
        st.caption("Selecione os bancos que você utiliza para movimentações, transferências ou recebimentos.")

        # Filtra apenas contas do tipo "Conta Corrente"
        bancos = [c for c in CONTAS_MODELO if c["tipo"] == "Conta Corrente"]

        # Cria uma grade de 3 colunas para distribuir os checkboxes elegantemente
        cols = st.columns(3)
        for idx, banco in enumerate(bancos):
            with cols[idx % 3]:
                # O checkbox retorna True se marcado
                marcado = st.checkbox(
                    label=f" {banco['nome']}",
                    key=f"banco_{banco['nome']}"
                )
                if marcado:
                    contas_selecionadas.append(banco)

    # --- ABA 2: CARTÕES DE CRÉDITO ---
    with tab_cartoes:
        st.subheader("Cartões de crédito que você possui:")
        st.caption("Esses cartões serão criados com suas respectivas datas estimadas de vencimento da fatura.")

        cartoes = [c for c in CONTAS_MODELO if c["tipo"] == "Cartão de Crédito"]

        cols = st.columns(3)
        for idx, cartao in enumerate(cartoes):
            with cols[idx % 3]:
                marcado = st.checkbox(
                    label=f" {cartao['nome']}",
                    key=f"cartao_{cartao['nome']}"
                )
                if marcado:
                    contas_selecionadas.append(cartao)

    # --- ABA 3: OUTROS E VALES ---
    with tab_outros:
        st.subheader("Dinheiro em mãos ou Vales:")
        st.caption("Selecione se costuma usar dinheiro físico ou se recebe vales da empresa.")

        outros = [c for c in CONTAS_MODELO if c["tipo"] in ["Dinheiro", "Outros"]]

        cols = st.columns(3)
        for idx, outro in enumerate(outros):
            with cols[idx % 3]:
                marcado = st.checkbox(
                    label=f" {outro['nome']}",
                    key=f"outro_{outro['nome']}"
                )
                if marcado:
                    contas_selecionadas.append(outro)

    st.markdown("---")

    # Centralização do botão de ação
    col_btn_1, col_btn_2, col_btn_3 = st.columns([1, 2, 1])

    with col_btn_2:
        if st.button("Finalizar Configuração e Entrar no Sistema 🚀", type="primary", use_container_width=True):
            if not contas_selecionadas:
                st.warning("⚠️ Selecione pelo menos uma conta para começarmos!")
            else:
                with st.spinner("Preparando suas contas personalizadas..."):
                    # Grava no Supabase utilizando a função do database.py
                    sucesso = inserir_contas_onboarding(username, contas_selecionadas)

                    if sucesso:
                        st.success("🎉 Tudo pronto! Suas contas foram criadas com sucesso!")
                        time.sleep(1.5)
                        # Força o Streamlit a recarregar o app. O router agora verá que o usuário já tem contas!
                        st.rerun()
                    else:
                        st.error("Ocorreu um erro ao criar suas contas iniciais no banco de dados. Tente novamente.")