import streamlit as st
import plotly.express as px
import pandas as pd
from database import carregar_dados, get_saldo_por_conta, ler_dados, get_saldo_por_tipo


def render_dashboard():
    df = carregar_dados()
    if df.empty:
        st.info("Aguardando lançamentos para gerar análise...")
        return

    # --- CONFIGURAÇÃO DE METAS ---
    METAS = {
        "Casa": 1500.0,
        "Alimentação": 1000.0,
        "Transporte": 400.0,
        "Lazer": 300.0,
        "Saúde": 500.0
    }

    # --- TRATAMENTO DE DATAS ---
    df['data'] = pd.to_datetime(df['data'])
    df['mes_ano'] = df['data'].dt.strftime('%m/%Y')

    meses_disponiveis = df[['mes_ano', 'data']].copy()
    meses_disponiveis['sort_val'] = meses_disponiveis['data'].dt.to_period('M')
    opcoes_mes = meses_disponiveis.sort_values('sort_val', ascending=False)['mes_ano'].unique()

    # Sidebar - Seleção de Mês
    mes_sel = st.sidebar.selectbox("Mês de Referência", opcoes_mes)

    # Filtrar DF pelo mês selecionado (Base para tudo)
    df_mes = df[df['mes_ano'] == mes_sel].copy()

    st.title(f"📊 Dashboard MFinanças - {mes_sel}")

    # --- PREPARAÇÃO DE DADOS PARA SALDO (INCLUI TRANSFERÊNCIAS) ---
    # Criamos o df_processado diretamente do df_mes para NÃO perder as transferências
    df_processado = df_mes.copy()

    # Ajuste para Pagamentos de Cartão (Entradas virtuais para abater saldo da conta corrente)
    pagamentos_cartao = df_processado[df_processado['grupo'] == 'Pagamento de Cartão'].copy()
    if not pagamentos_cartao.empty:
        entradas_virtuais = pagamentos_cartao[['subcategoria', 'valor']].copy()
        entradas_virtuais.columns = ['conta', 'valor']
        entradas_virtuais['tipo'] = 'Ganho'
        entradas_virtuais['grupo'] = 'Ajuste Cartão'
        entradas_virtuais['valor'] = entradas_virtuais['valor'].abs()
        df_processado = pd.concat([df_processado, entradas_virtuais], ignore_index=True)

    # Função de impacto corrigida com limpeza de string
    def calcular_impacto(row):
        tipo = str(row['tipo']).strip().lower()
        subcat = str(row['subcategoria']).strip().lower()
        valor = abs(row['valor'])

        if tipo == 'gasto':
            return -valor
        elif tipo == 'ganho':
            return valor
        elif 'transferência' in tipo or 'transferencia' in tipo:
            if 'saída' in subcat or 'saida' in subcat:
                return -valor
            elif 'entrada' in subcat:
                return valor
        return 0

    df_processado['impacto_saldo'] = df_processado.apply(calcular_impacto, axis=1)

    # --- SEÇÃO 2: FLUXO DE CAIXA MENSAL (APENAS GANHOS/GASTOS REAIS) ---
    # Aqui filtramos para o resumo não somar transferências como "lucro" ou "prejuízo"
    df_fluxo = df_mes[~df_mes['grupo'].isin(['Transferência', 'Pagamento de Cartão'])].copy()

    total_ganhos = df_fluxo[df_fluxo['tipo'] == 'Ganho']['valor'].sum()
    total_gastos = abs(df_fluxo[df_fluxo['tipo'] == 'Gasto']['valor'].sum())
    saldo_geral = total_ganhos - total_gastos

    st.subheader("Resumo Mensal (Fluxo de Caixa)")
    t1, t2, t3 = st.columns(3)
    t1.metric("TOTAL ENTRADAS", f"R$ {total_ganhos:,.2f}")
    t2.metric("TOTAL SAÍDAS", f"R$ {total_gastos:,.2f}", delta_color="inverse")
    t3.metric("SALDO DO MÊS", f"R$ {saldo_geral:,.2f}")

    st.divider()

    # --- SEÇÃO 4: DETALHAMENTO POR CONTA ---
    st.write("### 🏦 Detalhamento por Conta / Cartão")

    # Agrupamos Ganhos e Gastos para as legendas
    resumo_contas = df_processado.groupby(['conta', 'tipo'])['valor'].sum().unstack(fill_value=0).reset_index()
    for col in ['Ganho', 'Gasto']:
        if col not in resumo_contas: resumo_contas[col] = 0.0

    # Calculamos o Saldo Real (que agora inclui o ID 118 do Mercado Pago)
    saldo_real = df_processado.groupby('conta')['impacto_saldo'].sum().reset_index()
    resumo_final = saldo_real.merge(resumo_contas, on='conta', how='left').fillna(0)

    cols = st.columns(3)
    for i, row in resumo_final.iterrows():
        with cols[i % 3]:
            saldo_f = row['impacto_saldo']
            cor_saldo = "green" if saldo_f >= 0 else "red"

            st.markdown(f"#### {row['conta']}")
            st.caption(f"Entradas: R$ {row['Ganho']:,.2f} | Gastos: R$ {abs(row['Gasto']):,.2f}")
            st.markdown(f"<span style='color:{cor_saldo}'>**Saldo: R$ {saldo_f:,.2f}**</span>",
                        unsafe_allow_html=True)

    st.divider()

    # --- SEÇÃO 6: ANÁLISES GRÁFICAS ---
    df_gastos_graf = df_mes[df_mes['tipo'] == 'Gasto'].copy()
    df_gastos_graf['valor_abs'] = df_gastos_graf['valor'].abs()

    if not df_gastos_graf.empty:
        st.write("### 🔲 Mapa de Gastos (Treemap)")
        fig_tree = px.treemap(df_gastos_graf, path=['grupo', 'subgrupo', 'subcategoria'],
                              values='valor_abs', color='grupo', template="plotly_dark")
        st.plotly_chart(fig_tree, use_container_width=True)

        st.write("### 💳 Gastos por Conta")
        df_pizza = df_gastos_graf.groupby('conta')['valor_abs'].sum().reset_index()
        fig_pie = px.pie(df_pizza, values='valor_abs', names='conta', hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- SEÇÃO 1: PATRIMÔNIO E ATIVOS ---
    st.markdown("### 🏦 Gestão de Patrimônio (Ativos Totais)")
    saldo_liquidez = get_saldo_por_tipo("Investimento (Liquidez)")
    saldo_imovel = get_saldo_por_tipo("Patrimônio (Imóvel)")
    saldo_dinheiro = get_saldo_por_tipo("Dinheiro")

    c_pat1, c_pat2, c_pat3 = st.columns(3)
    c_pat1.metric("💰 Liquidez / Investimentos", f"R$ {saldo_liquidez:,.2f}")
    c_pat2.metric("🏢 Patrimônio Imobiliário", f"R$ {saldo_imovel:,.2f}")
    total_geral_ativos = saldo_liquidez + saldo_imovel + saldo_dinheiro
    c_pat3.metric("📈 Patrimônio Total", f"R$ {total_geral_ativos:,.2f}")

    st.divider()

    # --- SEÇÃO 5: GRÁFICO DE COMPOSIÇÃO DE PATRIMÔNIO ---
    st.write("### 📊 Composição do Patrimônio Atual")
    df_patrimonio_pizza = pd.DataFrame({
        "Categoria": ["Investimentos", "Imóveis", "Dinheiro"],
        "Valor": [saldo_liquidez, saldo_imovel, saldo_dinheiro]
    })
    df_patrimonio_pizza = df_patrimonio_pizza[df_patrimonio_pizza['Valor'] > 0]

    if not df_patrimonio_pizza.empty:
        fig_pat = px.pie(df_patrimonio_pizza, values='Valor', names='Categoria',
                         hole=0.5, template="plotly_dark",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pat, use_container_width=True)

    st.divider()

    # --- SEÇÃO 3: CONTROLE DE METAS ---
    st.write("### 🎯 Controle de Metas por Grupo")
    gastos_por_grupo = df_mes[df_mes['tipo'] == 'Gasto'].groupby('grupo')['valor'].sum().abs()

    col_meta1, col_meta2 = st.columns(2)
    for i, (grupo, meta_valor) in enumerate(METAS.items()):
        gasto_atual = gastos_por_grupo.get(grupo, 0.0)
        percentual = float(min(gasto_atual / meta_valor, 1.0))
        with col_meta1 if i % 2 == 0 else col_meta2:
            st.markdown(f"**{grupo}**: R$ {gasto_atual:,.2f} de R$ {meta_valor:,.2f}")
            st.progress(percentual)

    st.divider()

    # --- SEÇÃO 7: ABAS DE DETALHAMENTO ---
    aba1, aba2, aba3 = st.tabs(["Filtros Detalhados", "Evolução Mensal", "Tabela de Lançamentos"])

    with aba1:
        st.write("### Analisar por Filtro Específico")
        c1, c2 = st.columns(2)
        filtro_tipo = c1.selectbox("1. Filtrar por:", ["Conta", "Grupo"])

        opcoes_f = sorted(df_mes[filtro_tipo.lower()].unique())
        val_f = c2.selectbox(f"2. Selecione {filtro_tipo}:", opcoes_f)

        # Aplica o filtro
        df_filtrado = df_mes[df_mes[filtro_tipo.lower()] == val_f].copy()

        # --- CÁLCULOS DE TOTAIS DO FILTRO ---
        total_ganhos_f = df_filtrado[df_filtrado['tipo'] == 'Ganho']['valor'].sum()
        total_gastos_f = abs(df_filtrado[df_filtrado['tipo'] == 'Gasto']['valor'].sum())
        saldo_filtro = total_ganhos_f - total_gastos_f

        # Exibição dos cards de resumo do filtro
        cf1, cf2, cf3 = st.columns(3)
        cf1.metric("Entradas Filtradas", f"R$ {total_ganhos_f:,.2f}")
        cf2.metric("Saídas Filtradas", f"R$ {total_gastos_f:,.2f}")
        cf3.metric("Saldo do Filtro", f"R$ {saldo_filtro:,.2f}")

        st.write("#### 📝 Lançamentos Detalhados")
        st.dataframe(
            df_filtrado[['data', 'descricao', 'subcategoria', 'valor']],
            use_container_width=True,
            hide_index=True
        )

        # --- NOVO: AGRUPAMENTO POR SUBCATEGORIA ---
        if not df_filtrado.empty:
            st.write(f"#### 🔍 Distribuição de {val_f} por Subcategoria")
            # Agrupamos para ver onde está o volume financeiro
            df_sub = df_filtrado.groupby('subcategoria')['valor'].sum().reset_index()
            df_sub['valor_abs'] = df_sub['valor'].abs()
            df_sub = df_sub.sort_values(by='valor_abs', ascending=False)

            # Exibe uma tabela resumida ou gráfico de barras horizontal
            fig_sub = px.bar(
                df_sub,
                x='valor_abs',
                y='subcategoria',
                orientation='h',
                text_auto=',.2f',
                title=f"Volumes por Subcategoria em {val_f}",
                template="plotly_dark",
                labels={'valor_abs': 'Valor Total (R$)', 'subcategoria': 'Subcategoria'}
            )
            st.plotly_chart(fig_sub, use_container_width=True)

    with aba2:
        st.write("### 📈 Comparativo entre Meses")
        df_mensal = df[df['tipo'] == 'Gasto'].copy()
        df_mensal['valor_abs'] = df_mensal['valor'].abs()
        df_mensal['mes_ref'] = df_mensal['data'].dt.strftime('%Y-%m')

        cat_comp = st.radio("Comparar por:", ["Total Geral", "Conta", "Grupo"], horizontal=True)
        if cat_comp == "Total Geral":
            resumo_m = df_mensal.groupby('mes_ref')['valor_abs'].sum().reset_index()
            fig_m = px.line(resumo_m, x='mes_ref', y='valor_abs', markers=True, template="plotly_dark")
        else:
            col_nome = 'conta' if cat_comp == "Conta" else 'grupo'
            resumo_m = df_mensal.groupby(['mes_ref', col_nome])['valor_abs'].sum().reset_index()
            fig_m = px.bar(resumo_m, x='mes_ref', y='valor_abs', color=col_nome, barmode='group',
                           template="plotly_dark")
        st.plotly_chart(fig_m, use_container_width=True)

    with aba3:
        st.write(f"### 📝 Todos os Lançamentos de {mes_sel}")
        st.dataframe(df_mes.sort_values(by='data', ascending=False), use_container_width=True, hide_index=True)