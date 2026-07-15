import streamlit as st
import plotly.express as px
import pandas as pd
from database import carregar_dados, get_saldo_por_conta, ler_dados, get_saldo_por_tipo


def render_dashboard():
    # 1. Identifica o usuário logado para filtrar os dados (Base Zerada)
    usuario_atual = st.session_state.get('username')

    # 2. Carrega os dados passando o username
    df = carregar_dados(username=usuario_atual)

    if df.empty:
        st.info(f"Olá {usuario_atual}! Aguardando seus primeiros lançamentos para gerar análise...")
        return

    # --- CONFIGURAÇÃO DE METAS (Original) ---
    METAS = {
        "Casa": 1500.0,
        "Alimentação": 1000.0,
        "Transporte": 400.0,
        "Lazer": 300.0,
        "Saúde": 500.0
    }

    # --- TRATAMENTO DE DATAS (Original) ---
    df['data'] = pd.to_datetime(df['data'])
    df['mes_ano'] = df['data'].dt.strftime('%m/%Y')

    meses_disponiveis = df[['mes_ano', 'data']].copy()
    meses_disponiveis['sort_val'] = meses_disponiveis['data'].dt.to_period('M')
    opcoes_mes = meses_disponiveis.sort_values('sort_val', ascending=False)['mes_ano'].unique()

    # Sidebar - Seleção de Mês
    mes_sel = st.sidebar.selectbox("Mês de Referência", opcoes_mes)

    # Filtrar DF pelo mês selecionado
    df_mes = df[df['mes_ano'] == mes_sel].copy()

    st.title(f"📊 Dashboard: {mes_sel}")
    st.caption(f"Dados filtrados para o usuário: **{usuario_atual}**")

    # --- KPI CARDS (Original) ---
    c1, c2, c3, c4 = st.columns(4)
    ganhos = df_mes[df_mes['valor'] > 0]['valor'].sum()
    gastos = df_mes[df_mes['valor'] < 0]['valor'].sum()
    saldo_mes = ganhos + gastos

    c1.metric("Ganhos no Mês", f"R$ {ganhos:,.2f}")
    c2.metric("Gastos no Mês", f"R$ {abs(gastos):,.2f}", delta_color="inverse")
    c3.metric("Saldo Mensal", f"R$ {saldo_mes:,.2f}")

    taxa_eco = (saldo_mes / ganhos * 100) if ganhos > 0 else 0
    c4.metric("% Economia", f"{taxa_eco:.1f}%")

    st.divider()

    # --- ABAS DE ANÁLISE ---
    aba1, aba2, aba3 = st.tabs(["🎯 Metas vs Realizado", "📈 Evolução Mensal", "💰 Saldos por Conta"])

    with aba1:
        st.write("### Análise de Gastos por Grupo")
        df_gastos = df_mes[df_mes['valor'] < 0].copy()
        df_gastos['valor_abs'] = df_gastos['valor'].abs()

        if not df_gastos.empty:
            resumo_grupo = df_gastos.groupby('grupo')['valor_abs'].sum().reset_index()

            # Merge com Metas (Lógica original)
            df_metas = pd.DataFrame(list(METAS.items()), columns=['grupo', 'Meta'])
            resumo_final = pd.merge(resumo_grupo, df_metas, on='grupo', how='left').fillna(0)

            fig_meta = px.bar(
                resumo_final,
                x='grupo',
                y=['valor_abs', 'Meta'],
                barmode='group',
                title="Gastos Atuais vs Metas Definidas",
                labels={'value': 'Valor (R$)', 'variable': 'Tipo', 'valor_abs': 'Realizado'},
                template="plotly_dark",
                color_discrete_map={'valor_abs': '#EF553B', 'Meta': '#636EFA'}
            )
            st.plotly_chart(fig_meta, use_container_width=True)

            # Detalhamento por Subcategoria e Gráfico de Rosca (Colunas Originais)
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                grupos_disp = sorted(df_gastos['grupo'].unique())
                val_f = st.selectbox("Escolha um Grupo para detalhar:", grupos_disp)
                df_sub = df_gastos[df_gastos['grupo'] == val_f].groupby('subcategoria')['valor_abs'].sum().reset_index()

                fig_sub = px.bar(
                    df_sub.sort_values('valor_abs'),
                    x='valor_abs',
                    y='subcategoria',
                    orientation='h',
                    text_auto=',.2f',
                    title=f"Volumes por Subcategoria em {val_f}",
                    template="plotly_dark",
                    labels={'valor_abs': 'Valor Total (R$)', 'subcategoria': 'Subcategoria'}
                )
                st.plotly_chart(fig_sub, use_container_width=True)

            with col_f2:
                fig_pizza = px.pie(
                    df_gastos,
                    values='valor_abs',
                    names='grupo',
                    hole=0.4,
                    title="Distribuição Percentual de Gastos",
                    template="plotly_dark"
                )
                st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.info("Nenhum gasto registrado para análise de metas.")

    with aba2:
        st.write("### 📈 Comparativo entre Meses")
        # Filtra apenas gastos do usuário logado
        df_mensal = df[df['tipo'] == 'Gasto'].copy()
        df_mensal['valor_abs'] = df_mensal['valor'].abs()
        df_mensal['mes_ref'] = df_mensal['data'].dt.strftime('%Y-%m')

        # Lógica original de seleção de comparação
        cat_comp = st.radio("Comparar por:", ["Total Geral", "Conta", "Grupo"], horizontal=True)

        if not df_mensal.empty:
            if cat_comp == "Total Geral":
                resumo_m = df_mensal.groupby('mes_ref')['valor_abs'].sum().reset_index()
                fig_m = px.line(resumo_m, x='mes_ref', y='valor_abs', markers=True, template="plotly_dark",
                                title="Evolução Total de Gastos")
            else:
                col_nome = 'conta' if cat_comp == "Conta" else 'grupo'
                resumo_m = df_mensal.groupby(['mes_ref', col_nome])['valor_abs'].sum().reset_index()
                fig_m = px.bar(resumo_m, x='mes_ref', y='valor_abs', color=col_nome, barmode='group',
                               template="plotly_dark", title=f"Gastos por {cat_comp}")

            st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.info("Dados insuficientes para gerar comparativo mensal.")

    with aba3:
        st.write("### 💰 Saldos Atuais por Conta")
        df_c_lista = ler_dados("cad_contas")

        if not df_c_lista.empty:
            saldos = []
            for c in df_c_lista['nome']:
                # Busca o saldo individual do usuário logado nesta conta
                s = get_saldo_por_conta(c, username=usuario_atual)
                saldos.append({"Conta": c, "Saldo": s})

            df_saldos = pd.DataFrame(saldos)

            # Formatação e Estilização Original
            st.dataframe(
                df_saldos.sort_values('Saldo', ascending=False).style.format({'Saldo': 'R$ {:.2f}'}),
                use_container_width=True,
                hide_index=True
            )

            total_patrimonio = df_saldos['Saldo'].sum()
            st.markdown(f"#### Patrimônio Líquido (Base {usuario_atual}): **R$ {total_patrimonio:,.2f}**")

            # Gráfico de barras de saldo (Original)
            fig_balanco = px.bar(
                df_saldos, x='Conta', y='Saldo',
                color='Saldo', color_continuous_scale='Viridis',
                template="plotly_dark", title="Distribuição de Saldo por Instituição"
            )
            st.plotly_chart(fig_balanco, use_container_width=True)
        else:
            st.warning("Cadastre suas contas nas Configurações para visualizar os saldos.")