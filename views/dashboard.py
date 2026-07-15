import streamlit as st
import plotly.express as px
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta


# IMPORTAÇÕES DO DATABASE (Ajustadas para o Supabase)
from database import (
    carregar_dados,
    carregar_transacoes_invest,
    get_saldo_por_conta,
    get_saldo_por_tipo,
    get_resumo_patrimonio  # <--- Essa função vai facilitar sua vida!
)

# Se você ainda usa investimentos, mantenha esta:
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

    # 2. BUSCA OS DADOS NA NUVEM (SUPABASE)
    # A função get_resumo_patrimonio já faz todo o cálculo pesado para nós
    resumo = get_resumo_patrimonio(usuario_atual)

    # 3. EXIBIÇÃO DAS MÉTRICAS (CARTÕES DO TOPO)
    # Usamos 2 colunas para o iPhone não espremer tudo em uma linha só
    col1, col2 = st.columns(2)

    with col1:
        st.metric("💰 Disponível",
                  f"R$ {resumo['Disponível']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.metric("📈 Ganhos", f"R$ {resumo['Ganhos']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    with col2:
        st.metric("📉 Gastos", f"R$ {resumo['Gastos']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.metric("🏦 Investido", f"R$ {resumo['Investido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # --- FIM DA DICA DE OURO ---

    # 2. Carrega os dados da nuvem
    df = carregar_dados(username=usuario_atual)

    if df.empty:
        st.info(f"Olá {usuario_atual}! Aguardando seus lançamentos...")
        return

    # Garantindo que os tipos estão corretos para o Pandas
    df['data'] = pd.to_datetime(df['data'])
    df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)

    aba_fin, aba_inv = st.tabs(["💰 Financeiro", "📈 Investimentos"])

    with aba_fin:
        # --- TRATAMENTO DE DATAS ---
        df['mes_ano'] = df['data'].dt.strftime('%m/%Y')

        # Ordenação decrescente (mais recente primeiro)
        opcoes_mes = df.sort_values('data', ascending=False)['mes_ano'].unique()
        mes_sel = st.sidebar.selectbox("Mês de Referência", opcoes_mes)

        # --- CONFIGURADOR DE METAS ---
        with st.sidebar.expander("🎯 Definir Metas", expanded=False):
            grupos_reais = sorted(
                [g for g in df['grupo'].unique() if g not in ['Ajuste Cartão', 'Ganho', 'Transferência', None]])
            metas_dinamicas = {grupo: st.number_input(f"Meta: {grupo}", min_value=0.0, step=50.0, key=f"m_{grupo}") for
                               grupo in grupos_reais}

        # Filtragem e Processamento
        df_mes = df[df['mes_ano'] == mes_sel].copy()

        st.subheader(f"📊 MFinanças - {mes_sel}")

        # Lógica de Ajuste de Cartão (Sua sacada de mestre)
        df_processado = df_mes.copy()
        pagamentos_cartao = df_processado[df_processado['grupo'] == 'Pagamento de Cartão'].copy()

        if not pagamentos_cartao.empty:
            # Criamos o estorno virtual para o saldo não ficar negativo injustamente
            entradas_virtuais = pagamentos_cartao[['subcategoria', 'valor']].copy()
            entradas_virtuais.columns = ['conta', 'valor']
            entradas_virtuais['tipo'], entradas_virtuais['grupo'] = 'Ganho', 'Ajuste Cartão'
            entradas_virtuais['valor'] = entradas_virtuais['valor'].abs()
            df_processado = pd.concat([df_processado, entradas_virtuais], ignore_index=True)

        def calcular_impacto(row):
            # 1. Garantimos que os valores não são nulos e limpamos espaços/maiúsculas
            tipo = str(row.get('tipo', '')).strip().lower()
            subcat = str(row.get('subcategoria', '')).strip().lower()
            valor = abs(float(row.get('valor', 0)))

            # 2. Lógica para Gastos (Despesas)
            if tipo in ['gasto', 'despesa']:
                return -valor

            # 3. Lógica para Ganhos (Receitas)
            elif tipo in ['ganho', 'receita']:
                return valor

            # 4. Lógica para Transferências (Entrada/Saída)
            elif 'transferência' in tipo or 'transferencia' in tipo:
                if 'saída' in subcat or 'saida' in subcat:
                    return -valor
                elif 'entrada' in subcat:
                    return valor

            return 0

        # Aplicando ao DataFrame
        df_processado['impacto_saldo'] = df_processado.apply(calcular_impacto, axis=1)

        # --- SEÇÃO 6: ANÁLISES GRÁFICAS (TREEMAP) ---

        # 1. Filtro Robusto: Aceita 'Gasto' ou 'Despesa' e ignora maiúsculas/minúsculas
        # O .str.lower() garante que nada fique de fora se o banco enviar 'DESPESA' ou 'gasto'
        df_gastos_graf = df_mes[df_mes['tipo'].str.lower().isin(['gasto', 'despesa'])].copy()

        # 2. Conversão de Segurança: Garante que 'valor' seja um número positivo
        df_gastos_graf['valor_abs'] = pd.to_numeric(df_gastos_graf['valor'], errors='coerce').abs().fillna(0)

        if not df_gastos_graf.empty:
            st.write("### 🔲 Mapa de Gastos (Treemap)")

            # O Treemap agrupa por Grupo > Subgrupo > Subcategoria
            fig_tree = px.treemap(
                df_gastos_graf,
                path=['grupo', 'subgrupo', 'subcategoria'],
                values='valor_abs',
                color='grupo',
                template=tmpl  # Usa o tema (dark/light) definido no início do dashboard
            )

            # --- AJUSTE DEFINITIVO PARA VISUALIZAÇÃO NO IPHONE ---
            fig_tree.update_traces(
                # Força o texto (Nome + R$) a aparecer fixo dentro dos quadrados
                textinfo="label+value",
                # Formata para o padrão de moeda (R$ 1.234,56)
                texttemplate="<b>%{label}</b><br>R$ %{value:,.2f}",
                textfont=dict(size=14, color="white"),
                # Hover otimizado para toque no celular
                hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<extra></extra>"
            )

            fig_tree.update_layout(
                # Margens mínimas para aproveitar a tela do iPhone
                margin=dict(t=30, l=5, r=5, b=5),
                height=450,  # Altura ideal para leitura sem precisar de muito scroll
                hoverlabel=dict(
                    bgcolor="#1E1E1E",
                    font_size=16,
                    font_color="white",
                    bordercolor="#00FFCC"
                )
            )

            # Renderização otimizada (sem a barra de ferramentas que atrapalha no mobile)
            st.plotly_chart(
                fig_tree,
                width='stretch',
                config={
                    'displayModeBar': False,
                    'staticPlot': False
                }
            )
        else:
            st.info("Nenhum gasto registrado neste mês para gerar o mapa visual.")

            # --- 2. Gráfico de Rosca (Gastos por Conta) ---
            # Usamos o df_gastos_graf que já filtramos na Seção 6 anterior
            if not df_gastos_graf.empty:
                st.write("### 💳 Gastos por Conta")

                # Agrupamos os gastos por conta bancária/cartão
                df_pizza = df_gastos_graf.groupby('conta')['valor_abs'].sum().reset_index()

                fig_pie = px.pie(
                    df_pizza,
                    values='valor_abs',
                    names='conta',
                    hole=0.4,
                    template=tmpl  # Usa o tema (dark/light) definido no início
                )

                # AJUSTE MOBILE: Otimização total para a tela do iPhone
                fig_pie.update_layout(
                    margin=dict(t=30, l=5, r=5, b=80),  # Aumentei a margem inferior (b) para a legenda
                    hoverlabel=dict(
                        bgcolor="#1E1E1E",
                        font_size=14,
                        font_color="white",
                        bordercolor="#00FFCC"
                    ),
                    legend=dict(
                        orientation="h",  # Legenda horizontal
                        yanchor="bottom",
                        y=-0.6,  # Empurra a legenda bem para baixo para não espremer a rosca
                        xanchor="center",
                        x=0.5
                    )
                )

                # Melhora a informação visual direta nas fatias
                fig_pie.update_traces(
                    textinfo='percent+label',  # Nome e % direto na fatia para leitura rápida
                    # Formatação brasileira no hover (ao tocar com o dedo)
                    hovertemplate="<b>%{label}</b><br>Total: R$ %{value:,.2f}<br>Percentual: %{percent}<extra></extra>",
                    marker=dict(line=dict(color='#000000', width=1))  # Linha fina entre fatias para destaque
                )

                # Renderização responsiva e limpa
                st.plotly_chart(
                    fig_pie,
                    width='stretch',
                    config={'displayModeBar': False}
                )
            else:
                st.info("Sem dados de gastos para detalhamento por conta.")

            st.divider()

        # --- SEÇÃO 2: FLUXO DE CAIXA MENSAL (APENAS GANHOS/GASTOS REAIS) ---

        # 1. Filtro Inteligente: Remove transferências e pagamentos de fatura para não duplicar saídas
        # Usamos .str.lower() para garantir que funcione independente de como foi escrito no banco
        termos_ignorar = ['transferência', 'transferencia', 'pagamento de cartão', 'pagamento de cartao']
        df_fluxo = df_mes[~df_mes['grupo'].str.lower().isin(termos_ignorar)].copy()

        # 2. Cálculos de Base (Ganhos vs Despesas)
        # Aceitamos 'Ganho/Receita' e 'Gasto/Despesa' para total compatibilidade com o Supabase
        total_ganhos = df_fluxo[df_fluxo['tipo'].str.lower().isin(['ganho', 'receita'])]['valor'].sum()
        total_gastos = abs(df_fluxo[df_fluxo['tipo'].str.lower().isin(['gasto', 'despesa'])]['valor'].sum())
        saldo_geral = total_ganhos - total_gastos

        st.markdown("### Resumo Mensal  \n<small>(Fluxo de Caixa Real)</small>", unsafe_allow_html=True)

        # 3. Métrica Responsiva para iPhone
        # No mobile, o Streamlit empilha essas colunas, garantindo leitura total
        t1, t2, t3 = st.columns(3)

        # Função auxiliar interna para formatar moeda R$ 1.234,56
        def fmt_br(valor):
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        with t1:
            st.metric("TOTAL ENTRADAS", fmt_br(total_ganhos))

        with t2:
            # Mostramos o gasto como valor positivo para facilitar a leitura da métrica
            st.metric("TOTAL SAÍDAS", fmt_br(total_gastos))

        with t3:
            # Cor dinâmica: Verde se sobrou dinheiro, Vermelho se faltou
            st.metric(
                "SALDO DO MÊS",
                fmt_br(saldo_geral),
                delta=f"{saldo_geral:,.2f}",
                delta_color="normal" if saldo_geral >= 0 else "inverse"
            )

        st.divider()

        # --- SEÇÃO 4: DETALHAMENTO POR CONTA (CARDS BANCÁRIOS) ---
        st.markdown("### 🏦 Contas e Cartões")

        # 1. Agrupamos por conta e tipo para ver Entradas e Saídas separadas
        # Usamos fill_value=0 para evitar erros se uma conta só tiver gastos ou só ganhos
        resumo_contas = df_processado.groupby(['conta', 'tipo'])['valor'].sum().unstack(fill_value=0).reset_index()

        # Padronização para o Supabase: Garante que as colunas existam (independente do nome no banco)
        for col in ['Ganho', 'Receita', 'Gasto', 'Despesa']:
            if col not in resumo_contas: resumo_contas[col] = 0.0

        # 2. Unificamos as colunas para facilitar o cálculo (Soma Ganho+Receita e Gasto+Despesa)
        resumo_contas['Total_Entradas'] = resumo_contas.get('Ganho', 0) + resumo_contas.get('Receita', 0)
        resumo_contas['Total_Saidas'] = resumo_contas.get('Gasto', 0) + resumo_contas.get('Despesa', 0)

        # 3. Calculamos o Saldo Real usando a coluna 'impacto_saldo' que criamos na função anterior
        saldo_real = df_processado.groupby('conta')['impacto_saldo'].sum().reset_index()

        # 4. Mesclamos tudo em um único DataFrame de resumo
        resumo_final_contas = saldo_real.merge(resumo_contas[['conta', 'Total_Entradas', 'Total_Saidas']], on='conta',
                                               how='left').fillna(0)

        # 5. EXIBIÇÃO EM CARDS (Layout Responsivo para iPhone)
        # No Desktop: 3 colunas. No iPhone: O Streamlit empilha automaticamente.
        cols = st.columns(3)

        for i, row in resumo_final_contas.iterrows():
            # O operador % 3 distribui os cards entre as colunas
            with cols[i % 3]:
                # Criamos o Card com borda para destacar cada conta no modo escuro
                with st.container(border=True):
                    saldo_f = row['impacto_saldo']
                    # Cores dinâmicas para o saldo
                    cor_saldo = "#00cc44" if saldo_f >= 0 else "#ff4b4b"

                    # Título da Conta em Negrito
                    st.markdown(f"**{row['conta']}**")

                    # Detalhamento de fluxo em fonte menor (Caption)
                    # Usamos abs() nas saídas para não mostrar sinal de menos duplo
                    st.caption(f"📥 R$ {row['Total_Entradas']:,.2f}  \n📤 R$ {abs(row['Total_Saidas']):,.2f}")

                    # Saldo Final em Destaque Colorido
                    # Aplicamos a formatação brasileira R$ 1.234,56
                    valor_formatado = f"R$ {saldo_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                    st.markdown(
                        f"<p style='color:{cor_saldo}; font-weight:bold; font-size:1.1rem; margin-bottom:0;'>"
                        f"Saldo: {valor_formatado}</p>",
                        unsafe_allow_html=True
                    )

        st.divider()

        # --- SEÇÃO 1: PATRIMÔNIO E ATIVOS ---
        st.markdown("### 🏦 Gestão de Patrimônio  \n<small>(Ativos Totais e Liquidez)</small>", unsafe_allow_html=True)

        # 1. Busca os saldos na nuvem (Supabase) usando o usuario_atual
        # Note que usamos as categorias exatas que estão no seu banco de dados
        saldo_liquidez = get_saldo_por_tipo("Investimento (Liquidez)", username=usuario_atual)
        saldo_imovel = get_saldo_por_tipo("Patrimônio (Imóvel)", username=usuario_atual)
        saldo_dinheiro = get_saldo_por_tipo("Dinheiro", username=usuario_atual)

        # 2. Cálculo do Patrimônio Total (Soma de tudo)
        total_geral_ativos = saldo_liquidez + saldo_imovel + saldo_dinheiro

        # 3. EXIBIÇÃO RESPONSIVA (3 Colunas no Desktop / Empilhado no iPhone)
        c_pat1, c_pat2, c_pat3 = st.columns(3)

        # Função rápida para formatar R$ 1.234,56
        def fmt(v):
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        with c_pat1:
            # Foco em Investimentos/Liquidez (Dinheiro que você pode usar rápido)
            st.metric("💰 Liquidez / Invest.", fmt(saldo_liquidez))

        with c_pat2:
            # Foco em Bens Imobilizados (Casa, Terrenos, etc)
            st.metric("🏢 Patrimônio Imob.", fmt(saldo_imovel))

        with c_pat3:
            # O valor mais importante: Tudo o que você construiu
            # Adicionei um delta opcional que mostra o valor em relação ao total (exemplo visual)
            st.metric("📈 Patrimônio Total", fmt(total_geral_ativos),
                      help="Soma de Investimentos, Imóveis e Dinheiro em conta.")

        st.divider()

        # --- SEÇÃO 5: GRÁFICO DE COMPOSIÇÃO DE PATRIMÔNIO ---
        st.markdown("### 📊 Composição  \n<small>do Patrimônio Atual</small>", unsafe_allow_html=True)

        # 1. Criamos o DataFrame de visualização com os dados já vindos do Supabase
        df_patrimonio_pizza = pd.DataFrame({
            "Categoria": ["Investimentos", "Imóveis", "Dinheiro"],
            "Valor": [saldo_liquidez, saldo_imovel, saldo_dinheiro]
        })

        # Removemos categorias zeradas para o gráfico não ficar poluído
        df_patrimonio_pizza = df_patrimonio_pizza[df_patrimonio_pizza['Valor'] > 0]

        if not df_patrimonio_pizza.empty:
            fig_pat = px.pie(
                df_patrimonio_pizza,
                values='Valor',
                names='Categoria',
                hole=0.5,  # Estilo Rosca: mais elegante para Dashboards
                template=tmpl,  # Usa o tema dinâmico (dark/light)
                color_discrete_sequence=px.colors.qualitative.Pastel
            )

            # --- AJUSTE DEFINITIVO PARA IPHONE ---
            fig_pat.update_layout(
                # Margens mínimas para o gráfico ocupar bem a largura do celular
                margin=dict(t=30, l=5, r=5, b=60),
                # Legenda horizontal na parte inferior
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.4,  # Afasta um pouco para não encostar no gráfico
                    xanchor="center",
                    x=0.5
                ),
                # Remove fundo e bordas desnecessárias
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )

            # Ajuste das fatias para facilitar o toque no celular
            fig_pat.update_traces(
                textinfo='percent+label',  # Mostra a % e o nome direto na fatia
                hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>%: %{percent}<extra></extra>"
            )

            # Renderização responsiva (use_container_width é vital para mobile)
            st.plotly_chart(
                fig_pat,
                width='stretch',
                config={'displayModeBar': False}  # Remove a barra de ferramentas que atrapalha o touch
            )
        else:
            st.info("⚠️ Sem dados de patrimônio para exibir o gráfico de composição.")

        st.divider()

        # --- SEÇÃO 3: CONTROLE DE METAS (CARDS COM BARRA DE PROGRESSO) ---
        st.markdown("### 🎯 Controle de Metas  \n<small>Acompanhamento Real vs Planejado</small>",
                    unsafe_allow_html=True)

        # 1. Agrupamos o que você realmente gastou no mês
        # Usamos .str.lower().isin() para capturar 'Gasto' ou 'Despesa' do Supabase
        df_real = df_mes[df_mes['tipo'].str.lower().isin(['gasto', 'despesa'])]
        gastos_por_grupo = df_real.groupby('grupo')['valor'].sum().abs()

        # 2. Layout Responsivo: No Desktop 2 colunas, no iPhone empilha
        col_meta1, col_meta2 = st.columns(2)

        # 3. Filtramos apenas os grupos que você definiu meta na barra lateral
        grupos_com_meta = {g: v for g, v in metas_dinamicas.items() if v > 0}

        if not grupos_com_meta:
            st.info("💡 Defina os valores das metas no menu lateral (🎯 Definir Metas) para acompanhar aqui.")
        else:
            # Transformamos em lista para distribuir entre as colunas no loop
            itens_meta = list(grupos_com_meta.items())

            for i, (grupo, meta_valor) in enumerate(itens_meta):
                # Pegamos quanto você já gastou desse grupo (se não gastou nada, assume 0.0)
                gasto_atual = gastos_por_grupo.get(grupo, 0.0)

                # Cálculo do percentual para a barra de progresso (limite de 1.0 para o st.progress)
                percentual = float(min(gasto_atual / meta_valor, 1.0)) if meta_valor > 0 else 0.0

                # Distribui os cards entre as colunas
                col_alvo = col_meta1 if i % 2 == 0 else col_meta2

                with col_alvo:
                    # Usamos border=True para criar um "card" destacado no iPhone
                    with st.container(border=True):
                        # Título do Grupo em Negrito
                        st.markdown(f"**{grupo}**")

                        # Formatação dos valores em R$ 1.234,56
                        gasto_f = f"R$ {gasto_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        meta_f = f"R$ {meta_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                        st.caption(f"{gasto_f} de {meta_f}")

                        # Barra de Progresso Visual
                        st.progress(percentual)

                        # Sistema de Alertas Rápidos (UX Mobile)
                        if percentual >= 1.0:
                            st.error("🚨 Limite estourado!")
                        elif percentual >= 0.8:
                            st.warning("⚠️ Próximo do limite!")
                        else:
                            st.success("✅ Dentro da meta")

        st.divider()

        # --- SEÇÃO 7: ABAS DE DETALHAMENTO (FINANCEIRO) ---
        aba1, aba2, aba3 = st.tabs(["🎯 Filtros", "📈 Evolução", "📝 Tabela"])

        with aba1:
            st.markdown("### 🎯 Analisar Filtros  \n<small>Busca Específica</small>", unsafe_allow_html=True)

            c1, c2 = st.columns([1, 1])
            with c1:
                filtro_tipo = st.selectbox("1. Filtrar por:", ["Conta", "Grupo"], key="sb_filtro_tipo")
            with c2:
                opcoes_f = sorted(df_mes[filtro_tipo.lower()].unique())
                val_f = st.selectbox(f"2. Selecione {filtro_tipo}:", opcoes_f, key="sb_filtro_val")

            df_filtrado = df_mes[df_mes[filtro_tipo.lower()] == val_f].copy()

            # Compatibilidade Supabase: Gasto/Despesa e Ganho/Receita
            total_ganhos_f = df_filtrado[df_filtrado['tipo'].str.lower().isin(['ganho', 'receita'])]['valor'].sum()
            total_gastos_f = abs(df_filtrado[df_filtrado['tipo'].str.lower().isin(['gasto', 'despesa'])]['valor'].sum())
            saldo_filtro = total_ganhos_f - total_gastos_f

            cf1, cf2, cf3 = st.columns(3)
            cf1.metric("Entradas", f"R$ {total_ganhos_f:,.2f}")
            cf2.metric("Saídas", f"R$ {total_gastos_f:,.2f}")
            cf3.metric("Saldo", f"R$ {saldo_filtro:,.2f}")

            st.write("#### 📝 Lançamentos")
            st.dataframe(df_filtrado[['data', 'descricao', 'subcategoria', 'valor']], width='stretch',
                         hide_index=True)

            if not df_filtrado.empty:
                st.write(f"#### 🔍 Subcategorias em {val_f}")
                df_sub = df_filtrado.groupby('subcategoria')['valor'].sum().abs().reset_index()
                df_sub = df_sub.sort_values(by='valor', ascending=False)

                fig_sub = px.bar(df_sub, x='valor', y='subcategoria', orientation='h', text_auto=',.2f',
                                 template="plotly_dark")
                fig_sub.update_layout(margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_sub, width='stretch', config={'displayModeBar': False})

        with aba2:
            st.markdown("### 📊 Comparativo  \n<small>Evolução Mensal</small>", unsafe_allow_html=True)
            df_mensal = df[df['tipo'].str.lower().isin(['gasto', 'despesa'])].copy()
            df_mensal['valor_abs'] = df_mensal['valor'].abs()
            df_mensal['mes_ref'] = df_mensal['data'].dt.strftime('%m/%y')

            cat_comp = st.radio("Comparar por:", ["Geral", "Conta", "Grupo"], horizontal=True, key="rad_comparativo")

            if cat_comp == "Geral":
                resumo_m = df_mensal.groupby('mes_ref')['valor_abs'].sum().reset_index()
                fig_m = px.line(resumo_m, x='mes_ref', y='valor_abs', markers=True, template="plotly_dark")
            else:
                col_nome = 'conta' if cat_comp == "Conta" else 'grupo'
                resumo_m = df_mensal.groupby(['mes_ref', col_nome])['valor_abs'].sum().reset_index()
                fig_m = px.bar(resumo_m, x='mes_ref', y='valor_abs', color=col_nome, barmode='group',
                               template="plotly_dark")

            fig_m.update_layout(margin=dict(l=10, r=10, t=30, b=10),
                                legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"))
            st.plotly_chart(fig_m, width='stretch', config={'displayModeBar': False})

        with aba3:
            st.markdown(f"### 📋 Lançamentos  \n<small>Lista Completa de {mes_sel}</small>", unsafe_allow_html=True)
            st.dataframe(df_mes.sort_values(by='data', ascending=False), width='stretch', hide_index=True)

        # --- ABA DE INVESTIMENTOS ---
        with aba_inv:
            st.subheader("📈 Minha Carteira de Ativos")
            # INTEGRAÇÃO SUPABASE: Substitui a consulta local
            df_inv = carregar_investimentos_usuario(usuario_atual)

            if not df_inv.empty:
                tickers_unicos = df_inv['ativo'].unique().tolist()
                precos_atuais = {}

                with st.spinner('🔄 Atualizando cotações via Yahoo Finance...'):
                    for ticker in tickers_unicos:
                        try:
                            t_yf = ticker.strip().upper()
                            if not t_yf.endswith(".SA"): t_yf += ".SA"
                            papel = yf.Ticker(t_yf)
                            # Tentativa fast_info ou regularMarketPrice
                            preco = papel.fast_info.get('last_price') or papel.history(period="1d")['Close'].iloc[-1]
                            precos_atuais[ticker] = float(preco)
                        except:
                            precos_atuais[ticker] = 0.0

                df_inv['Preço Atual'] = df_inv['ativo'].map(precos_atuais)
                df_inv['Valor Total'] = df_inv['qtd_total'] * df_inv['Preço Atual']
                df_inv['Performance'] = df_inv['Preço Atual'] - df_inv['preco_medio']
                df_inv['Tendência'] = df_inv['Performance'].apply(
                    lambda x: "▲ Alta" if x > 0 else ("▼ Baixa" if x < 0 else "▬ Estável"))

                st.dataframe(
                    df_inv,
                    column_config={
                        "ativo": "Ativo",
                        "Preço Atual": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                        "Valor Total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                        "preco_medio": st.column_config.NumberColumn("Médio", format="R$ %.2f"),
                        "Performance": st.column_config.NumberColumn("Perf.", format="R$ %.2f"),
                    },
                    hide_index=True, width="stretch"
                )

                st.divider()
                with st.expander("📈 Detalhar Evolução Patrimonial", expanded=False):
                    st.markdown("### 📈 Comparativo de Ativos")

                    # INTEGRAÇÃO SUPABASE: Busca transações históricas do banco na nuvem
                    df_trans = carregar_transacoes_invest(usuario_atual)

                    if df_trans.empty:
                        st.info("Adicione transações no Supabase para visualizar a evolução.")
                    else:
                        tickers_disponiveis = sorted(df_trans['ativo'].unique().tolist())
                        c_f1, c_f2 = st.columns([2, 1])
                        with c_f1:
                            ativos_selecionados = st.multiselect("Ativos:", options=tickers_disponiveis,
                                                                 default=tickers_disponiveis)
                        with c_f2:
                            data_min = pd.to_datetime(df_trans['data']).min().date()
                            inicio = st.date_input("Início", data_min, key="inv_ini")
                            fim = st.date_input("Fim", datetime.now().date(), key="inv_fim")

                        if st.button("🚀 Gerar Análise Detalhada", width="stretch"):
                            with st.spinner("Buscando dados históricos e calculando posições..."):
                                date_range = pd.date_range(start=inicio, end=fim)
                                df_master = pd.DataFrame({'Data': date_range.date})
                                df_master['Total_Somado'] = 0.0
                                fig_evol = go.Figure()

                                for t in ativos_selecionados:
                                    t_yf = t.strip().upper()
                                    if not t_yf.endswith(".SA"): t_yf += ".SA"
                                    try:
                                        hist = yf.download(t_yf, start=inicio, end=fim + timedelta(days=1),
                                                           progress=False)
                                        if not hist.empty:
                                            # Tratamento para colunas multinível do yfinance novo
                                            if isinstance(hist.columns, pd.MultiIndex):
                                                hist.columns = hist.columns.get_level_values(0)

                                            hist = hist.reset_index()
                                            hist['Date'] = hist['Date'].dt.date
                                            hist = hist[['Date', 'Close']].rename(
                                                columns={'Date': 'Data', 'Close': 'Preco'})

                                            df_ticker = pd.merge(pd.DataFrame({'Data': date_range.date}), hist,
                                                                 on='Data', how='left')
                                            df_ticker['Preco'] = df_ticker['Preco'].ffill().bfill()

                                            # LÓGICA DE QTD ACUMULADA (Mantida 100%)
                                            valores_ativo = []
                                            for data_ref in df_ticker['Data']:
                                                trans_ate_data = df_trans[(df_trans['ativo'] == t) & (
                                                            pd.to_datetime(df_trans['data']).dt.date <= data_ref)]
                                                # Compra soma, Venda subtrai
                                                qtd_acum = trans_ate_data.apply(lambda x: x['quantidade'] if x[
                                                                                                                 'tipo_operacao'].lower() == 'compra' else -
                                                x['quantidade'], axis=1).sum()
                                                valores_ativo.append(qtd_acum * float(
                                                    df_ticker.loc[df_ticker['Data'] == data_ref, 'Preco'].values[0]))

                                            fig_evol.add_trace(
                                                go.Scatter(x=df_ticker['Data'], y=valores_ativo, mode='lines',
                                                           name=f"{t}"))
                                            df_master['Total_Somado'] += valores_ativo
                                    except:
                                        continue

                                fig_evol.add_trace(
                                    go.Scatter(x=df_master['Data'], y=df_master['Total_Somado'], fill='tozeroy',
                                               line=dict(color='#00FFCC', width=4), name="Total Carteira"))
                                fig_evol.update_layout(template="plotly_dark", hovermode="x unified",
                                                       margin=dict(l=10, r=10, t=40, b=10),
                                                       legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"))
                                st.plotly_chart(fig_evol, width="stretch", config={'displayModeBar': False})
