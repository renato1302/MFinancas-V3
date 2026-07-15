import streamlit as st
import plotly.express as px
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import os
import duckdb
from datetime import datetime, timedelta
from database import carregar_dados, get_saldo_por_conta, ler_dados, get_saldo_por_tipo
from views.investimentos import carregar_investimentos_usuario

def render_dashboard():
    # 1. Identifica o usuário logado para filtrar os dados
    usuario_atual = st.session_state.get('username')

    # --- NOVO: CAPTURA O TEMA DEFINIDO NO APP.PY ---
    # Caso não exista (primeiro acesso), definimos um padrão escuro
    tmpl = st.session_state.get('template_grafico', 'plotly_dark')
    cor_txt = st.session_state.get('cor_texto', 'white')

    # --- INÍCIO DA DICA DE OURO (CSS RESPONSIVO) ---
    st.markdown("""
            <style>
            /* Ajustes específicos para telas de Smartphones (iPhone) */
            @media (max-width: 640px) {
                /* Diminui o valor numérico da métrica para não cortar */
                [data-testid="stMetricValue"] {
                    font-size: 1.6rem !important;
                }
                /* Diminui o rótulo (texto acima do número) */
                [data-testid="stMetricLabel"] {
                    font-size: 0.85rem !important;
                }
                /* Reduz o espaçamento interno do container para ganhar tela */
                .main .block-container {
                    padding-top: 1rem !important;
                    padding-left: 0.5rem !important;
                    padding-right: 0.5rem !important;
                }
            }
            </style>
        """, unsafe_allow_html=True)
    # --- FIM DA DICA DE OURO ---

    # 2. Carrega os dados passando o username
    df = carregar_dados(username=usuario_atual)

    if df.empty:
        st.info(f"Olá {usuario_atual}! Aguardando seus primeiros lançamentos para gerar análise...")
        return

    aba_fin, aba_inv = st.tabs(["💰 Financeiro", "📈 Investimentos"])

    with aba_fin:


        # --- TRATAMENTO DE DATAS ---
        df['data'] = pd.to_datetime(df['data'])
        df['mes_ano'] = df['data'].dt.strftime('%m/%Y')

        meses_disponiveis = df[['mes_ano', 'data']].copy()
        meses_disponiveis['sort_val'] = meses_disponiveis['data'].dt.to_period('M')
        opcoes_mes = meses_disponiveis.sort_values('sort_val', ascending=False)['mes_ano'].unique()

        # Sidebar - Seleção de Mês
        mes_sel = st.sidebar.selectbox("Mês de Referência", opcoes_mes)

        # --- NOVO: CONFIGURADOR DE METAS DINÂMICO ---
        with st.sidebar.expander("🎯 Definir Metas do Mês", expanded=False):
            # Pegamos todos os grupos que existem nos seus dados para você não esquecer nenhum
            grupos_reais = sorted(df['grupo'].unique().tolist())

            metas_dinamicas = {}
            for grupo in grupos_reais:
                # Ignora grupos que não fazem sentido ter meta (como ajustes ou ganhos)
                if grupo not in ['Ajuste Cartão', 'Ganho', 'Transferência']:
                    # Cria um campo de número para cada grupo
                    valor_meta = st.number_input(f"Meta para {grupo}", min_value=0.0, value=0.0, step=50.0,
                                                 key=f"meta_{grupo}")
                    metas_dinamicas[grupo] = valor_meta

        # Filtrar DF pelo mês selecionado
        df_mes = df[df['mes_ano'] == mes_sel].copy()

        # Título conforme solicitado
        st.subheader(f"📊 MFinanças - {mes_sel}")
        st.caption(f"Dados filtrados para o usuário: **{usuario_atual}**")

        # --- PREPARAÇÃO DE DADOS PARA SALDO (INCLUI TRANSFERÊNCIAS) ---
        df_processado = df_mes.copy()

        # Ajuste para Pagamentos de Cartão
        pagamentos_cartao = df_processado[df_processado['grupo'] == 'Pagamento de Cartão'].copy()
        if not pagamentos_cartao.empty:
            entradas_virtuais = pagamentos_cartao[['subcategoria', 'valor']].copy()
            entradas_virtuais.columns = ['conta', 'valor']
            entradas_virtuais['tipo'] = 'Ganho'
            entradas_virtuais['grupo'] = 'Ajuste Cartão'
            entradas_virtuais['valor'] = entradas_virtuais['valor'].abs()
            df_processado = pd.concat([df_processado, entradas_virtuais], ignore_index=True)

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

        # --- SEÇÃO 6: ANÁLISES GRÁFICAS ---
        df_gastos_graf = df_mes[df_mes['tipo'] == 'Gasto'].copy()
        df_gastos_graf['valor_abs'] = df_gastos_graf['valor'].abs()

        if not df_gastos_graf.empty:
            # --- 1. Treemap (Mapa de Gastos) ---
            st.write("### 🔲 Mapa de Gastos (Treemap)")

            fig_tree = px.treemap(
                df_gastos_graf,
                path=['grupo', 'subgrupo', 'subcategoria'],
                values='valor_abs',
                color='grupo',
                template="plotly_dark"
            )

            # --- AJUSTE DEFINITIVO PARA VISUALIZAÇÃO DIRETA NO IPHONE ---
            fig_tree.update_traces(
                # 1. Força o texto a aparecer dentro do quadrado (Nome + Valor)
                textinfo="label+value",
                # 2. Formata o valor para Real dentro do quadrado
                texttemplate="<b>%{label}</b><br>R$ %{value:,.2f}",
                # 3. Garante que o texto se ajuste ao tamanho do quadrado
                textfont=dict(size=14, color="white"),
                # 4. Melhora a caixa de detalhes (hover) caso você consiga tocar sem expandir
                hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<extra></extra>"
            )

            fig_tree.update_layout(
                margin=dict(t=30, l=10, r=10, b=10),
                # Ajusta a altura para o iPhone (quadrados maiores facilitam a leitura do texto interno)
                height=450,
                hoverlabel=dict(
                    bgcolor="#1E1E1E",
                    font_size=16,
                    font_color="white",
                    bordercolor="#00FFCC"
                )
            )

            # Renderização com interatividade reduzida para focar na leitura
            st.plotly_chart(
                fig_tree,
                use_container_width=True,
                config={
                    'displayModeBar': False,
                    'staticPlot': False  # Mantemos False para você ainda conseguir expandir se quiser
                }
            )

            # --- 2. Gráfico de Rosca (Gastos por Conta) ---
            st.write("### 💳 Gastos por Conta")
            df_pizza = df_gastos_graf.groupby('conta')['valor_abs'].sum().reset_index()

            fig_pie = px.pie(
                df_pizza,
                values='valor_abs',
                names='conta',
                hole=0.4,
                template="plotly_dark"
            )

            # AJUSTE MOBILE: Coloca a legenda abaixo do gráfico em telas pequenas
            fig_pie.update_layout(
                margin=dict(t=30, l=10, r=10, b=10),
                hoverlabel=dict(
                    bgcolor="#1E1E1E",
                    font_size=14,
                    font_color="white",
                    bordercolor="#00FFCC"
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.4,  # Aumentei um pouco o recuo para não encostar no gráfico
                    xanchor="center",
                    x=0.5
                )
            )
            # Melhora a informação ao tocar na fatia
            fig_pie.update_traces(
                textinfo='percent+label',  # Mostra o nome e % direto na fatia se couber
                hovertemplate="<b>%{label}</b><br>Total: R$ %{value:,.2f}<br>Percentual: %{percent}<extra></extra>"
            )

            # Renderização responsiva
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

        st.divider()

        # --- SEÇÃO 2: FLUXO DE CAIXA MENSAL (APENAS GANHOS/GASTOS REAIS) ---
        df_fluxo = df_mes[~df_mes['grupo'].isin(['Transferência', 'Pagamento de Cartão'])].copy()
        total_ganhos = df_fluxo[df_fluxo['tipo'] == 'Ganho']['valor'].sum()
        total_gastos = abs(df_fluxo[df_fluxo['tipo'] == 'Gasto']['valor'].sum())
        saldo_geral = total_ganhos - total_gastos

        st.markdown("### Resumo Mensal  \n<small>(Fluxo de Caixa)</small>", unsafe_allow_html=True)

        # AJUSTE RESPONSIVO:
        # No desktop serão 3 colunas. No Mobile (iPhone), o Streamlit as empilhará automaticamente.
        t1, t2, t3 = st.columns([1, 1, 1])

        with t1:
            st.metric("TOTAL ENTRADAS", f"R$ {total_ganhos:,.2f}")

        with t2:
            # Use delta para mostrar visualmente se o gasto subiu ou desceu (opcional)
            st.metric("TOTAL SAÍDAS", f"R$ {total_gastos:,.2f}")

        with t3:
            # Adicionei uma cor dinâmica: verde se positivo, vermelho se negativo
            cor_saldo = "normal" if saldo_geral >= 0 else "inverse"
            st.metric("SALDO DO MÊS", f"R$ {saldo_geral:,.2f}", delta_color=cor_saldo)

        st.divider()

        # --- SEÇÃO 4: DETALHAMENTO POR CONTA ---
        st.markdown("### 🏦 Contas e Cartões")

        resumo_contas = df_processado.groupby(['conta', 'tipo'])['valor'].sum().unstack(fill_value=0).reset_index()
        for col in ['Ganho', 'Gasto']:
            if col not in resumo_contas: resumo_contas[col] = 0.0

        saldo_real = df_processado.groupby('conta')['impacto_saldo'].sum().reset_index()
        resumo_final_contas = saldo_real.merge(resumo_contas, on='conta', how='left').fillna(0)

        # AJUSTE RESPONSIVO:
        # Criamos as colunas, mas no iPhone o Streamlit vai empilhar uma por uma automaticamente
        cols = st.columns(3)

        for i, row in resumo_final_contas.iterrows():
            # O operador % 3 distribui entre as 3 colunas no Desktop
            with cols[i % 3]:
                # Criamos um "Card" visual usando st.container
                with st.container(border=True):
                    saldo_f = row['impacto_saldo']
                    cor_saldo = "#00cc44" if saldo_f >= 0 else "#ff4b4b"  # Verde ou Vermelho padrão Streamlit

                    # Título da Conta
                    st.markdown(f"**{row['conta']}**")

                    # Valores de Entradas e Saídas em fonte menor para o iPhone
                    st.caption(f"📥 R$ {row['Ganho']:,.2f}  \n📤 R$ {abs(row['Gasto']):,.2f}")

                    # Saldo em destaque
                    st.markdown(
                        f"<p style='color:{cor_saldo}; font-weight:bold; margin-bottom:0;'>Saldo: R$ {saldo_f:,.2f}</p>",
                        unsafe_allow_html=True)

        st.divider()



        # --- SEÇÃO 1: PATRIMÔNIO E ATIVOS ---
        st.markdown("### 🏦 Gestão de Patrimônio  \n<small>(Ativos Totais)</small>", unsafe_allow_html=True)
        # CORREÇÃO: Passando o usuario_atual para as funções de saldo
        saldo_liquidez = get_saldo_por_tipo("Investimento (Liquidez)", username=usuario_atual)
        saldo_imovel = get_saldo_por_tipo("Patrimônio (Imóvel)", username=usuario_atual)
        saldo_dinheiro = get_saldo_por_tipo("Dinheiro", username=usuario_atual)

        c_pat1, c_pat2, c_pat3 = st.columns(3)
        c_pat1.metric("💰 Liquidez / Investimentos", f"R$ {saldo_liquidez:,.2f}")
        c_pat2.metric("🏢 Patrimônio Imobiliário", f"R$ {saldo_imovel:,.2f}")
        total_geral_ativos = saldo_liquidez + saldo_imovel + saldo_dinheiro
        c_pat3.metric("📈 Patrimônio Total", f"R$ {total_geral_ativos:,.2f}")

        st.divider()

        # --- SEÇÃO 5: GRÁFICO DE COMPOSIÇÃO DE PATRIMÔNIO ---
        st.markdown("### 📊 Composição  \n<small>do Patrimônio Atual</small>", unsafe_allow_html=True)

        df_patrimonio_pizza = pd.DataFrame({
            "Categoria": ["Investimentos", "Imóveis", "Dinheiro"],
            "Valor": [saldo_liquidez, saldo_imovel, saldo_dinheiro]
        })
        df_patrimonio_pizza = df_patrimonio_pizza[df_patrimonio_pizza['Valor'] > 0]

        if not df_patrimonio_pizza.empty:
            fig_pat = px.pie(
                df_patrimonio_pizza,
                values='Valor',
                names='Categoria',
                hole=0.5,
                template="plotly_dark",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )

            # AJUSTE RESPONSIVO PARA IPHONE:
            fig_pat.update_layout(
                # Reduz margens para o gráfico ganhar tamanho na tela do celular
                margin=dict(t=30, l=10, r=10, b=10),
                # Move a legenda para baixo de forma horizontal
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5
                )
            )

            # Renderização usando a largura total do container (essencial para mobile)
            # config={'displayModeBar': False} remove ícones que atrapalham o touch
            st.plotly_chart(fig_pat, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sem dados de patrimônio para exibir o gráfico.")

        st.divider()

        # --- SEÇÃO 3: CONTROLE DE METAS (ATUALIZADO PARA MOBILE) ---
        st.markdown("### 🎯 Controle de Metas  \n<small>Acompanhamento por Grupo</small>", unsafe_allow_html=True)
        gastos_por_grupo = df_mes[df_mes['tipo'] == 'Gasto'].groupby('grupo')['valor'].sum().abs()

        # AJUSTE RESPONSIVO: No Desktop serão 2 colunas, no iPhone elas se empilham
        col_meta1, col_meta2 = st.columns(2)

        # Filtrar apenas grupos que você definiu uma meta maior que zero
        grupos_com_meta = {g: v for g, v in metas_dinamicas.items() if v > 0}

        if not grupos_com_meta:
            st.info("Defina os valores das metas na barra lateral para acompanhar aqui.")
        else:
            # Transformamos em lista para usar o índice no loop de colunas
            itens_meta = list(grupos_com_meta.items())

            for i, (grupo, meta_valor) in enumerate(itens_meta):
                gasto_atual = gastos_por_grupo.get(grupo, 0.0)
                # Garante que o percentual seja entre 0.0 e 1.0 para o st.progress
                percentual = float(min(gasto_atual / meta_valor, 1.0)) if meta_valor > 0 else 0.0

                # Escolhe a coluna (Alterna entre 1 e 2 no Desktop)
                col_alvo = col_meta1 if i % 2 == 0 else col_meta2

                with col_alvo:
                    # Usamos border=True para criar um "card" que facilita a leitura no iPhone
                    with st.container(border=True):
                        st.markdown(f"**{grupo}**")

                        # Texto informativo com valores
                        texto_meta = f"R$ {gasto_atual:,.2f} de R$ {meta_valor:,.2f}"
                        st.caption(texto_meta)

                        # Barra de progresso (ocupa 100% da largura do card)
                        st.progress(percentual)

                        # Alertas de texto simplificados para telas pequenas
                        if percentual >= 1.0:
                            st.error(f"🚨 Limite atingido!")
                        elif percentual >= 0.8:
                            st.warning(f"⚠️ Atenção!")

        st.divider()

        # --- SEÇÃO 7: ABAS DE DETALHAMENTO (OTIMIZADO MOBILE) ---
        aba1, aba2, aba3 = st.tabs(["🎯 Filtros", "📈 Evolução", "📝 Tabela"])

        with aba1:
            st.markdown("### 🎯 Analisar Filtros  \n<small>Busca Específica</small>", unsafe_allow_html=True)

            # AJUSTE: No iPhone, os selectboxes ficarão um embaixo do outro
            c1, c2 = st.columns([1, 1])
            with c1:
                filtro_tipo = st.selectbox("1. Filtrar por:", ["Conta", "Grupo"])
            with c2:
                opcoes_f = sorted(df_mes[filtro_tipo.lower()].unique())
                val_f = st.selectbox(f"2. Selecione {filtro_tipo}:", opcoes_f)

            df_filtrado = df_mes[df_mes[filtro_tipo.lower()] == val_f].copy()
            total_ganhos_f = df_filtrado[df_filtrado['tipo'] == 'Ganho']['valor'].sum()
            total_gastos_f = abs(df_filtrado[df_filtrado['tipo'] == 'Gasto']['valor'].sum())
            saldo_filtro = total_ganhos_f - total_gastos_f

            # AJUSTE: Métricas filtradas com colunas que se empilham
            cf1, cf2, cf3 = st.columns(3)
            cf1.metric("Entradas", f"R$ {total_ganhos_f:,.2f}")
            cf2.metric("Saídas", f"R$ {total_gastos_f:,.2f}")
            cf3.metric("Saldo", f"R$ {saldo_filtro:,.2f}")

            st.write("#### 📝 Lançamentos")
            # AJUSTE: use_container_width=True para a tabela não cortar no iPhone
            st.dataframe(
                df_filtrado[['data', 'descricao', 'subcategoria', 'valor']],
                use_container_width=True,
                hide_index=True
            )

            if not df_filtrado.empty:
                st.write(f"#### 🔍 Subcategorias em {val_f}")
                df_sub = df_filtrado.groupby('subcategoria')['valor'].sum().reset_index()
                df_sub['valor_abs'] = df_sub['valor'].abs()
                df_sub = df_sub.sort_values(by='valor_abs', ascending=False)

                fig_sub = px.bar(
                    df_sub, x='valor_abs', y='subcategoria',
                    orientation='h', text_auto=',.2f',
                    template="plotly_dark"
                )
                # AJUSTE: Margens e responsividade do gráfico de barras
                fig_sub.update_layout(margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_sub, use_container_width=True, config={'displayModeBar': False})

        with aba2:
            st.markdown("### 📊 Comparativo  \n<small>Evolução Mensal</small>", unsafe_allow_html=True)
            df_mensal = df[df['tipo'] == 'Gasto'].copy()
            df_mensal['valor_abs'] = df_mensal['valor'].abs()

            # Simplificamos a visualização de data para o gráfico
            df_mensal['mes_ref'] = df_mensal['data'].dt.strftime('%m/%y')

            cat_comp = st.radio("Comparar por:", ["Geral", "Conta", "Grupo"], horizontal=True)

            if cat_comp == "Geral":
                resumo_m = df_mensal.groupby('mes_ref')['valor_abs'].sum().reset_index()
                fig_m = px.line(resumo_m, x='mes_ref', y='valor_abs', markers=True, template="plotly_dark")
            else:
                col_nome = 'conta' if cat_comp == "Conta" else 'grupo'
                resumo_m = df_mensal.groupby(['mes_ref', col_nome])['valor_abs'].sum().reset_index()
                fig_m = px.bar(resumo_m, x='mes_ref', y='valor_abs', color=col_nome, barmode='group',
                               template="plotly_dark")

            # AJUSTE: Legenda horizontal para não espremer o gráfico no iPhone
            fig_m.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig_m, use_container_width=True, config={'displayModeBar': False})

        with aba3:
            st.markdown(f"### 📋 Lançamentos  \n<small>Lista Completa de {mes_sel}</small>", unsafe_allow_html=True)
            # AJUSTE: Ordenação e largura total
            st.dataframe(
                df_mes.sort_values(by='data', ascending=False),
                use_container_width=True,
                hide_index=True
            )

    with aba_inv:
        st.subheader("Minha Carteira")
        df_inv = carregar_investimentos_usuario(usuario_atual)

        if not df_inv.empty:
            # 1. BUSCA DE PREÇOS (Yahoo Finance) com Spinner para feedback no mobile
            tickers_unicos = df_inv['ativo'].unique().tolist()
            precos_atuais = {}

            with st.spinner('Atualizando cotações...'):
                for ticker in tickers_unicos:
                    try:
                        t_yf = ticker.strip().upper()
                        if not t_yf.endswith(".SA") and len(t_yf) <= 6:
                            t_yf += ".SA"
                        papel = yf.Ticker(t_yf)
                        # fast_info é melhor para mobile por ser mais leve
                        precos_atuais[ticker] = papel.fast_info['last_price']
                    except:
                        precos_atuais[ticker] = 0.0

            # 2. CÁLCULOS
            df_inv['Preço Atual'] = df_inv['ativo'].map(precos_atuais)
            df_inv['Valor Total'] = df_inv['qtd_total'] * df_inv['Preço Atual']
            df_inv['Performance'] = df_inv['Preço Atual'] - df_inv['preco_medio']

            def definir_indicador(row):
                if row['Performance'] > 0:
                    return "▲ Alta"
                elif row['Performance'] < 0:
                    return "▼ Baixa"
                return "▬ Estável"

            df_inv['Tendência'] = df_inv.apply(definir_indicador, axis=1)

            # --- EXIBIÇÃO ---
            st.markdown("### 📊 Meus Ativos  \n<small>Detalhamento da Carteira</small>", unsafe_allow_html=True)

            # AJUSTE PARA IPHONE: Tabela com largura total e colunas otimizadas
            st.dataframe(
                df_inv,
                column_config={
                    "ativo": "Ativo",
                    "Preço Atual": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                    "Valor Total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                    "preco_medio": st.column_config.NumberColumn("Médio", format="R$ %.2f"),
                    "Tendência": "Ref.",
                    "Performance": st.column_config.NumberColumn("Perf.", format="R$ %.2f"),
                },
                hide_index=True,
                use_container_width=True  # Essencial para não quebrar o layout lateral
            )

            # --- GRÁFICO DE PIZZA (Responsivo) ---
            st.divider()
            with st.expander("📈 Detalhar Evolução Patrimonial", expanded=False):
                st.markdown("### 📈 Comparativo  \n<small>Análise de Evolução de Ativos</small>", unsafe_allow_html=True)

                caminho_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'financas.db')
                con = duckdb.connect(caminho_db)
                df_trans = con.execute("SELECT * FROM transacoes_invest WHERE usuario_id = ? ORDER BY data",
                                       [usuario_atual]).df()
                con.close()

                if df_trans.empty:
                    st.info("Adicione transações para visualizar a evolução.")
                else:
                    tickers_disponiveis = sorted(df_trans['ativo'].unique().tolist())

                    col_f1, col_f2 = st.columns([2, 1])
                    with col_f1:
                        ativos_selecionados = st.multiselect(
                            "Selecione os Ativos:",
                            options=tickers_disponiveis,
                            default=tickers_disponiveis
                        )
                    with col_f2:
                        data_min_base = pd.to_datetime(df_trans['data']).min().date()
                        inicio = st.date_input("Início", data_min_base, key="ev_ini")
                        fim = st.date_input("Fim", datetime.now().date(), key="ev_fim")

                    # Botão com largura total para facilitar o toque no iPhone
                    if st.button("🚀 Gerar Análise Detalhada", use_container_width=True):
                        if not ativos_selecionados:
                            st.warning("Selecione pelo menos um ativo.")
                        else:
                            with st.spinner("Buscando dados históricos..."):
                                date_range = pd.date_range(start=inicio, end=fim)
                                df_master = pd.DataFrame({'Data': date_range.date})
                                df_master['Total_Somado'] = 0.0

                                # SOLUÇÃO DO NameError: Inicializamos a figura ANTES do loop
                                fig_evol = go.Figure()

                                for t in ativos_selecionados:
                                    t_yf = t.strip().upper()
                                    if not t_yf.endswith(".SA") and len(t_yf) <= 6:
                                        t_yf += ".SA"

                                    try:
                                        hist = yf.download(t_yf, start=inicio, end=fim + timedelta(days=1),
                                                           progress=False)
                                        if not hist.empty:
                                            hist = hist.reset_index()
                                            # Ajuste para garantir que 'Date' seja acessível (depende da versão do yfinance)
                                            if 'Date' in hist.columns:
                                                hist['Date'] = hist['Date'].dt.date
                                                hist = hist[['Date', 'Close']].copy()
                                                hist.columns = ['Data', 'Preco']

                                                df_ticker = pd.merge(pd.DataFrame({'Data': date_range.date}), hist,
                                                                     on='Data', how='left')
                                                df_ticker['Preco'] = df_ticker['Preco'].ffill().bfill()

                                                valores_ativo = []
                                                for idx, row in df_ticker.iterrows():
                                                    data_ref = row['Data']
                                                    trans_ate_data = df_trans[(df_trans['ativo'] == t) & (
                                                                pd.to_datetime(df_trans['data']).dt.date <= data_ref)]
                                                    qtd_acum = trans_ate_data.apply(lambda x: x['quantidade'] if x[
                                                                                                                     'tipo_operacao'] == 'Compra' else -
                                                    x['quantidade'], axis=1).sum()
                                                    valor_no_dia = (
                                                                qtd_acum * float(row['Preco'])) if qtd_acum > 0 else 0
                                                    valores_ativo.append(valor_no_dia)

                                                fig_evol.add_trace(go.Scatter(
                                                    x=df_ticker['Data'], y=valores_ativo, mode='lines',
                                                    name=f"{t}",
                                                    visible='legendonly' if len(ativos_selecionados) > 1 else True
                                                ))
                                                df_master['Total_Somado'] += valores_ativo
                                    except Exception:
                                        continue

                                # Linha do Patrimônio Total
                                fig_evol.add_trace(go.Scatter(
                                    x=df_master['Data'], y=df_master['Total_Somado'], fill='tozeroy',
                                    line=dict(color='#00FFCC', width=4), name="Patrimônio Total"
                                ))

                                # SOLUÇÃO DO NameError e Layout Mobile
                                fig_evol.update_layout(
                                    template="plotly_dark",
                                    title="Evolução do Patrimônio (R$)",
                                    hovermode="x unified",
                                    margin=dict(l=10, r=10, t=40, b=10),
                                    legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center")
                                )

                                # SOLUÇÃO DO width='stretch': Usando use_container_width=True
                                st.plotly_chart(fig_evol, use_container_width=True, config={'displayModeBar': False})
