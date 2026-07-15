import streamlit as st
# REMOVIDO: import duckdb (Não usaremos mais banco local)
# REMOVIDO: import os, sys (Não precisamos mais gerenciar caminhos de arquivos .db)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
from services.web_tools import obter_preco_atual

# ADICIONADO: Conexão oficial com o seu banco na nuvem
from database import supabase, carregar_dados_config

# --- CONFIGURAÇÃO DO BANCO (UNIFICADO PARA SUPABASE) ---
def inicializar_banco_investimentos():
    """
    No Supabase, as tabelas 'ativos' e 'transacoes_invest' já devem ser
    criadas manualmente no Dashboard do site.
    Esta função fica vazia para manter a compatibilidade com o restante do código.
    """
    pass


# --- CARREGAR INVESTIMENTOS (VERSÃO SUPABASE + PANDAS) ---
def carregar_investimentos_usuario(username):
    try:
        from database import supabase

        # 1. Buscamos todas as transações do usuário e os dados dos ativos (INNER JOIN automático do Supabase)
        # O asterisco (*) traz tudo de transacoes_invest, e ativos(*) traz os detalhes do ticker
        response = supabase.table("transacoes_invest") \
            .select("*, ativos(*)") \
            .eq("usuario_id", username) \
            .execute()

        if not response.data:
            return pd.DataFrame()

        # 2. Transformamos em DataFrame para processar no Python
        df_raw = pd.json_normalize(response.data)

        # Ajuste de nomes de colunas após o normalize (o Supabase traz ativos.tipo, ativos.setor, etc)
        # Vamos renomear para manter a compatibilidade com seus gráficos
        df_raw = df_raw.rename(columns={
            'ativos.tipo': 'tipo',
            'ativos.setor': 'setor'
        })

        # 3. Lógica de Sinais: Compra (+) e Venda (-)
        df_raw['qtd_ajustada'] = df_raw.apply(
            lambda x: x['quantidade'] if x['tipo_operacao'] == 'Compra' else -x['quantidade'], axis=1
        )

        # 4. Agrupamento (O seu antigo GROUP BY)
        # Calculamos a quantidade total e o preço médio ponderado
        df_resumo = df_raw.groupby(['ativo', 'tipo', 'setor']).agg(
            qtd_total=('qtd_ajustada', 'sum'),
            preco_medio=('preco_unitario', 'mean')  # Mantendo sua lógica de média simples do código original
        ).reset_index()

        # 5. Filtro: Mostrar apenas o que você ainda tem em carteira (HAVING qtd_total > 0)
        df_resumo = df_resumo[df_resumo['qtd_total'] > 0.000001]

        return df_resumo

    except Exception as e:
        st.error(f"Erro ao processar investimentos: {e}")
        return pd.DataFrame()

# --- CONEXÃO COM O BANCO (MIGRADO PARA SUPABASE) ---
def conectar_banco():
    """
    No modelo antigo, abria o arquivo DuckDB.
    Agora, apenas retorna o cliente do Supabase já inicializado
    no seu arquivo database.py.
    """
    from database import supabase
    return supabase

def render_investimentos():
    # 1. SEGURANÇA E SESSÃO
    # Captura o username oficial da sessão. Se não houver, para aqui.
    usuario_atual = st.session_state.get('username')

    if not usuario_atual:
        st.warning("⚠️ Por favor, realize o login para acessar seus investimentos.")
        # Se for no iPhone, um botão de redirecionamento ajuda:
        if st.button("Ir para Login", width='stretch'):
            st.session_state.menu_option = "Login" # Ou o nome da sua aba de login
            st.rerun()
        return

    # 2. TÍTULO DINÂMICO
    st.title(f"🏦 Carteira de Investimentos")
    st.caption(f"Usuário: **{usuario_atual}** | Dados sincronizados com Supabase")

    # 3. ORGANIZAÇÃO DAS ABAS (Mantendo sua estrutura original)
    # Note que adicionei ícones, que ajudam na visualização mobile (iPhone)
    tab_dash, tab_evolucao, tab_cadastro, tab_transacao, tab_import = st.tabs([
        "📊 Dashboard",
        "📈 Evolução",
        "🆕 Ativos",
        "💸 Operações",
        "📥 Importar B3"
    ])

    # --- ABA: DASHBOARD DE INVESTIMENTOS (AJUSTADO SUPABASE) ---
    with tab_dash:
        # 1. BUSCA DE DADOS: Usamos a função que centraliza a lógica do Supabase
        # Ela já faz o cálculo de quantidade total e preço médio filtrando pelo seu usuário
        df_posicao = carregar_investimentos_usuario(usuario_atual)

        if not df_posicao.empty:
            # 2. INTEGRAÇÃO COM COTAÇÕES (Manutenção da sua lógica original)
            st.write("### 📈 Sua Carteira Atual")
            st.caption("Valores calculados com base no seu preço médio e saldo atual.")

            # Dica para o iPhone: No mobile, tabelas largas podem sumir.
            # O column_config ajuda a deixar os números bonitos.
            st.dataframe(
                df_posicao,
                width='stretch',
                hide_index=True,
                column_config={
                    "ativo": st.column_config.TextColumn("Ticker"),
                    "tipo": st.column_config.TextColumn("Classe"),
                    "qtd_total": st.column_config.NumberColumn("Qtd", format="%.4f"),
                    "preco_medio": st.column_config.NumberColumn("PME (R$)", format="R$ %.2f")
                }
            )

            # --- ESPAÇO PARA O SEU CÁLCULO DE ROI ---
            # Aqui você continua com sua lógica de:
            # 1. Pegar os ativos únicos: tickers = df_posicao['ativo'].tolist()
            # 2. Buscar preço atual: obter_preco_atual(ticker)
            # 3. Calcular Lucro/Prejuízo

        else:
            st.info(
                f"💡 {usuario_atual}, você ainda não possui ativos em carteira. Vá na aba 'Operações' para registrar sua primeira compra.")

    # --- ABA: OPERAÇÕES DE INVESTIMENTO (AJUSTADO SUPABASE) ---
    with tab_transacao:
        st.subheader("💸 Nova Operação")
        st.info(f"As operações registradas serão vinculadas à conta: **{usuario_atual}**")

        # (Aqui viria o seu formulário de 'Nova Operação' que ajustamos na Aba 4 de Configurações)
        # Certifique-se de usar: supabase.table("transacoes_invest").insert(nova_op).execute()

        st.divider()
        st.subheader("📋 Histórico de Operações")

        # 1. BUSCA DE DADOS NO SUPABASE
        from database import supabase
        try:
            # Buscamos as colunas específicas filtrando pelo usuário logado
            res_hist = supabase.table("transacoes_invest") \
                .select("id, data, ativo, quantidade, preco_unitario, tipo_operacao") \
                .eq("usuario_id", usuario_atual) \
                .order("data", ascending=False) \
                .execute()

            df_historico = pd.DataFrame(res_hist.data)
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")
            df_historico = pd.DataFrame()

        if not df_historico.empty:
            # Exibição otimizada para Mobile
            st.dataframe(
                df_historico,
                width='stretch',
                hide_index=True,
                column_config={
                    "id": st.column_config.TextColumn("ID"),  # Exibe como texto para facilitar cópia
                    "preco_unitario": st.column_config.NumberColumn("Preço (R$)", format="%.2f"),
                    "quantidade": st.column_config.NumberColumn("Qtd", format="%.4f")
                }
            )

            # 2. LÓGICA DE EXCLUSÃO
            st.write("---")
            col_del1, col_del2 = st.columns([1, 1])

            with col_del1:
                # text_input é melhor para copiar/colar o ID no iPhone
                id_para_deletar = st.text_input("Cole o ID para excluir", key="del_inv_id")

            with col_del2:
                st.write(" ")  # Alinhamento visual
                btn_excluir = st.button("🗑️ Excluir Registro", width='stretch', type="secondary")

            if btn_excluir:
                if id_para_deletar:
                    try:
                        # DELETE NO SUPABASE: Sempre com .eq("usuario_id") para segurança total
                        supabase.table("transacoes_invest") \
                            .delete() \
                            .eq("id", id_para_deletar) \
                            .eq("usuario_id", usuario_atual) \
                            .execute()

                        st.success(f"✅ Registro {id_para_deletar} excluído!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir no Supabase: {e}")
                else:
                    st.warning("Informe um ID válido para excluir.")
        else:
            st.info("Nenhuma operação encontrada para este usuário.")

    # --- ABA: EVOLUÇÃO PATRIMONIAL (AJUSTADO SUPABASE) ---
    with tab_evolucao:
        st.subheader("Análise Comparativa de Ativos")

        # 1. BUSCA DE DADOS NO SUPABASE
        from database import supabase
        try:
            # Buscamos todas as transações do usuário logado para reconstruir o histórico
            res_evol = supabase.table("transacoes_invest") \
                .select("*") \
                .eq("usuario_id", usuario_atual) \
                .order("data", ascending=True) \
                .execute()

            df_trans = pd.DataFrame(res_evol.data)
        except Exception as e:
            st.error(f"Erro ao carregar dados de evolução: {e}")
            df_trans = pd.DataFrame()

        if df_trans.empty:
            st.info("💡 Adicione transações na aba 'Operações' para visualizar sua evolução patrimonial.")
        else:
            # O Supabase pode retornar 'ativo' ou 'ticker', ajuste conforme sua tabela
            col_ativo = 'ativo' if 'ativo' in df_trans.columns else 'ticker'
            tickers_disponiveis = sorted(df_trans[col_ativo].unique().tolist())

            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                ativos_selecionados = st.multiselect("Selecione os Ativos:", options=tickers_disponiveis,
                                                     default=tickers_disponiveis)
            with col_f2:
                df_trans['data'] = pd.to_datetime(df_trans['data'])
                data_min_base = df_trans['data'].min().date()
                inicio = st.date_input("Início", data_min_base, key="ev_ini")
                fim = st.date_input("Fim", datetime.now().date(), key="ev_fim")

            if st.button("🚀 Gerar Análise Detalhada", width='stretch', type="primary"):
                if not ativos_selecionados:
                    st.warning("Selecione pelo menos um ativo.")
                else:
                    with st.spinner("Buscando cotações na B3..."):
                        # Criamos a base de tempo para o gráfico
                        date_range = pd.date_range(start=inicio, end=fim)
                        df_master = pd.DataFrame({'Data': date_range.date})
                        df_master['Total_Somado'] = 0.0

                        fig_evol = go.Figure()

                        for t in ativos_selecionados:
                            # Padronização para Yahoo Finance (PETR4 -> PETR4.SA)
                            t_yf = t.strip().upper()
                            if not t_yf.endswith(".SA") and len(t_yf) <= 6:
                                t_yf += ".SA"

                            try:
                                # Download dos preços históricos
                                hist = yf.download(t_yf, start=inicio, end=fim + timedelta(days=1), progress=False)

                                if not hist.empty:
                                    # Reset index e limpeza (Tratando MultiIndex do yfinance se houver)
                                    hist = hist.reset_index()
                                    if isinstance(hist.columns, pd.MultiIndex):
                                        hist.columns = hist.columns.get_level_values(0)

                                    hist['Date'] = pd.to_datetime(hist['Date']).dt.date
                                    hist = hist[['Date', 'Close']].copy()
                                    hist.columns = ['Data', 'Preco']

                                    # Merge com o calendário completo para preencher fins de semana
                                    df_ticker = pd.merge(pd.DataFrame({'Data': date_range.date}), hist, on='Data',
                                                         how='left')
                                    df_ticker['Preco'] = df_ticker['Preco'].ffill().bfill()

                                    # CÁLCULO DE POSIÇÃO HISTÓRICA
                                    valores_ativo = []
                                    for d_ref in df_ticker['Data']:
                                        # Filtra transações até o dia específico
                                        mask = (df_trans[col_ativo] == t) & (df_trans['data'].dt.date <= d_ref)
                                        df_temp = df_trans[mask]

                                        # Soma quantidades (Compra +, Venda -)
                                        qtd_acum = df_temp.apply(
                                            lambda x: x['quantidade'] if x['tipo_operacao'] == 'Compra' else -x[
                                                'quantidade'],
                                            axis=1).sum()

                                        valor_no_dia = (qtd_acum * float(
                                            df_ticker.loc[df_ticker['Data'] == d_ref, 'Preco'].values[
                                                0])) if qtd_acum > 0 else 0
                                        valores_ativo.append(valor_no_dia)

                                    # Adiciona linha individual (escondida por padrão para não poluir no iPhone)
                                    fig_evol.add_trace(go.Scatter(
                                        x=df_ticker['Data'], y=valores_ativo,
                                        mode='lines', name=f"Indiv: {t}",
                                        visible='legendonly'
                                    ))

                                    df_master['Total_Somado'] += valores_ativo
                            except Exception as e:
                                print(f"Erro no ativo {t}: {e}")
                                continue

                        # LINHA PRINCIPAL: PATRIMÔNIO TOTAL
                        fig_evol.add_trace(go.Scatter(
                            x=df_master['Data'], y=df_master['Total_Somado'],
                            fill='tozeroy', line=dict(color='#00FFCC', width=3),
                            name="Patrimônio Total"
                        ))

                        fig_evol.update_layout(
                            template="plotly_dark",
                            height=400,  # Altura fixa para caber na tela do iPhone
                            margin=dict(l=10, r=10, t=40, b=10),
                            legend=dict(orientation="h", y=-0.2),
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig_evol, width='stretch')

        # --- ABA: DASHBOARD DE INVESTIMENTOS (AJUSTADO SUPABASE) ---
        with tab_dash:
            from database import supabase

            # 1. BUSCA DE DADOS BRUTOS
            try:
                # Trazemos as transações e os detalhes dos ativos vinculados
                res = supabase.table("transacoes_invest").select("*, ativos(*)").eq("usuario_id",
                                                                                    usuario_atual).execute()
                df_raw = pd.json_normalize(res.data)
            except Exception as e:
                st.error(f"Erro ao acessar Supabase: {e}")
                df_raw = pd.DataFrame()

            if not df_raw.empty:
                # Padronização de colunas após o normalize
                df_raw.rename(columns={'ativos.tipo': 'tipo', 'ativos.setor': 'setor', 'ativos.nome': 'nome_empresa'},
                              inplace=True)
                # O Supabase pode retornar 'ticker' ou 'ativo', garantimos o nome 'ticker'
                if 'ativo' in df_raw.columns and 'ticker' not in df_raw.columns:
                    df_raw.rename(columns={'ativo': 'ticker'}, inplace=True)

                # 2. CÁLCULO DE POSIÇÃO E PREÇO MÉDIO PONDERADO (Lógica que estava no seu SQL)
                # Separamos compras para o preço médio (conforme sua regra original)
                df_compras = df_raw[df_raw['tipo_operacao'] == 'Compra'].copy()
                df_compras['custo_total'] = df_compras['quantidade'] * df_compras['preco_unitario']

                # Calculamos a quantidade líquida (Compras - Vendas)
                df_raw['qtd_ajustada'] = df_raw.apply(
                    lambda x: x['quantidade'] if x['tipo_operacao'] == 'Compra' else -x['quantidade'], axis=1)

                # Agrupamos para ter a posição atual
                df_posicao = df_raw.groupby(['ticker', 'tipo', 'setor']).agg(
                    qtd_total=('qtd_ajustada', 'sum')).reset_index()

                # Calculamos o Preço Médio Ponderado apenas das compras
                df_pm = df_compras.groupby('ticker').agg(
                    total_investido_pme=('custo_total', 'sum'),
                    total_qtd_pme=('quantidade', 'sum')
                ).reset_index()
                df_pm['preco_medio'] = df_pm['total_investido_pme'] / df_pm['total_qtd_pme']

                # Mesclamos a posição com o preço médio
                df_posicao = pd.merge(df_posicao, df_pm[['ticker', 'preco_medio']], on='ticker', how='left')

                # Filtro: Apenas o que ainda tem em carteira
                df_posicao = df_posicao[df_posicao['qtd_total'] > 0.001].copy()

                if not df_posicao.empty:
                    # 3. ATUALIZAÇÃO DE COTAÇÕES
                    with st.spinner('Sincronizando cotações da B3...'):
                        # Usamos sua função obter_preco_atual (certifique-se que ela está importada)
                        df_posicao['Preço Atual'] = df_posicao['ticker'].apply(obter_preco_atual)

                    # 4. CÁLCULOS FINANCEIROS
                    df_posicao['Total Investido (R$)'] = df_posicao['qtd_total'] * df_posicao['preco_medio']
                    df_posicao['Total Atual (R$)'] = df_posicao['qtd_total'] * df_posicao['Preço Atual']
                    df_posicao['Lucro/Prej (R$)'] = df_posicao['Total Atual (R$)'] - df_posicao['Total Investido (R$)']
                    df_posicao['ROI %'] = (df_posicao['Lucro/Prej (R$)'] / df_posicao['Total Investido (R$)']) * 100

                    # 5. VISUALIZAÇÃO (MÉTRICAS) - Otimizado para iPhone
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.metric("Patrimônio Atual", f"R$ {df_posicao['Total Atual (R$)'].sum():,.2f}")
                    with m2:
                        st.metric("Total Investido", f"R$ {df_posicao['Total Investido (R$)'].sum():,.2f}")
                    with m3:
                        lucro_t = df_posicao['Lucro/Prej (R$)'].sum()
                        st.metric("Lucro/Prejuízo Total", f"R$ {lucro_t:,.2f}", delta=f"{lucro_t:,.2f}")

                    st.divider()

                    # Gráficos (px.pie já é responsivo para celular)
                    c_g1, c_g2 = st.columns(2)
                    fig_classe = px.pie(df_posicao, values='Total Atual (R$)', names='tipo', hole=0.4,
                                        title="Por Classe", template="plotly_dark")
                    fig_setor = px.pie(df_posicao, values='Total Atual (R$)', names='setor', hole=0.4,
                                       title="Por Setor", template="plotly_dark")

                    c_g1.plotly_chart(fig_classe, width='stretch')
                    c_g2.plotly_chart(fig_setor, width='stretch')

                    st.write("### 📝 Detalhes da Carteira")
                    st.dataframe(
                        df_posicao[
                            ['ticker', 'tipo', 'setor', 'qtd_total', 'preco_medio', 'Preço Atual', 'Total Atual (R$)']],
                        width='stretch',
                        hide_index=True
                    )
                else:
                    st.info("Sua carteira está vazia no momento.")
            else:
                st.info("Nenhum investimento registrado no Supabase.")

    # --- ABA: CADASTRO DE ATIVOS (AJUSTADO SUPABASE) ---
    with tab_cadastro:
        st.subheader("🆕 Cadastro de Ativos")
        st.caption("Cadastre os ativos aqui para que fiquem disponíveis no seletor de operações.")

        with st.form("form_ativo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ticker = c1.text_input("Ticker (Ex: PETR4)").upper().strip()
            nome = c2.text_input("Nome da Empresa/Fundo")

            tipo = c1.selectbox("Classe de Ativo",
                                ["Ação", "FII", "ETF", "Tesouro", "Cripto", "BDR", "Exterior"])

            setor = c2.selectbox("Setor / Segmento",
                                 ["Bancos", "Energia", "Varejo", "Saúde", "Tecnologia",
                                  "Commodities", "Imobiliário", "Saneamento", "Educação", "Outros"])

            # Botão largo para facilitar no iPhone
            if st.form_submit_button("💾 Salvar Ativo", width='stretch', type="primary"):
                if ticker and nome:
                    try:
                        from database import supabase

                        # No Supabase, o 'upsert' resolve o problema de duplicidade
                        # Se o ticker já existir, ele atualiza as informações.
                        novo_ativo = {
                            "ticker": ticker,
                            "nome": nome,
                            "tipo": tipo,
                            "setor": setor
                        }

                        supabase.table("ativos").upsert(novo_ativo, on_conflict="ticker").execute()

                        st.success(f"✅ Ativo **{ticker}** sincronizado com sucesso!")
                        st.rerun()  # Atualiza a página para refletir no seletor de operações
                    except Exception as e:
                        st.error(f"Erro ao salvar no Supabase: {e}")
                else:
                    st.warning("⚠️ Por favor, preencha o Ticker e o Nome da Empresa.")

        # --- LISTA DE ATIVOS CADASTRADOS ---
        with st.expander("🔍 Ver Ativos Cadastrados"):
            from database import supabase
            res_ativos = supabase.table("ativos").select("*").order("ticker").execute()
            df_ativos = pd.DataFrame(res_ativos.data)
            if not df_ativos.empty:
                st.dataframe(df_ativos, width='stretch', hide_index=True)

    # --- ABA: REGISTRO DE TRANSAÇÕES (AJUSTADO SUPABASE) ---
    with tab_transacao:
        st.subheader("💸 Nova Operação Manual")

        # 1. BUSCA LISTA DE ATIVOS NO SUPABASE
        from database import supabase
        try:
            res_at = supabase.table("ativos").select("ticker").order("ticker").execute()
            # Transformamos em lista para o selectbox
            ativos_lista = [item['ticker'] for item in res_at.data]
        except Exception as e:
            st.error(f"Erro ao carregar lista de ativos: {e}")
            ativos_lista = []

        if ativos_lista:
            with st.form("form_op", clear_on_submit=True):
                c1, c2 = st.columns(2)
                data_op = c1.date_input("Data da Operação", datetime.now().date())
                ativo_sel = c1.selectbox("Selecione o Ativo", ativos_lista)

                tipo_op = c2.radio("Tipo de Movimentação", ["Compra", "Venda"], horizontal=True)
                # No iPhone, step=0.01 e format ajuda a não dar erro de arredondamento
                qtd = c2.number_input("Quantidade", min_value=0.0, step=0.01, format="%.4f")
                prc = c2.number_input("Preço Unitário (R$)", min_value=0.0, step=0.01, format="%.2f")

                corretora = st.text_input("Corretora / Instituição", value="Manual")

                if st.form_submit_button("🚀 Registrar na Carteira", width='stretch', type="primary"):
                    # Captura o usuário logado
                    usuario_atual = st.session_state.get('username')

                    if not usuario_atual:
                        st.error("Erro: Usuário não identificado. Faça login novamente.")
                    elif qtd <= 0 or prc <= 0:
                        st.warning("A quantidade e o preço devem ser maiores que zero.")
                    else:
                        try:
                            # PREPARAÇÃO DO DICIONÁRIO PARA O SUPABASE
                            nova_transacao = {
                                "data": str(data_op),
                                "ativo": ativo_sel,
                                "quantidade": float(qtd),
                                "preco_unitario": float(prc),
                                "tipo_operacao": tipo_op,
                                "corretora": corretora,
                                "usuario_id": usuario_atual
                            }

                            # INSERÇÃO NO SUPABASE
                            supabase.table("transacoes_invest").insert(nova_transacao).execute()

                            st.success(f"✅ {tipo_op} de {qtd} {ativo_sel} registrada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar no banco: {e}")
        else:
            st.warning("⚠️ Nenhum ativo cadastrado. Vá na aba 'Ativos' e cadastre pelo menos um ticker primeiro.")

        # --- ABA: IMPORTAR B3 (AJUSTADO SUPABASE) ---
        with tab_import:
            st.subheader("📥 Importar Planilha da B3")
            st.caption("Suba o arquivo .xlsx exportado diretamente do portal do investidor B3.")

            up = st.file_uploader("Selecione o arquivo B3 (.xlsx)", type=['xlsx'])

            if up:
                try:
                    # Leitura inicial
                    df_i = pd.read_excel(up)

                    # Limpeza de nomes de colunas
                    df_i.columns = [str(c).strip() for c in df_i.columns]

                    # Padronização de valores numéricos
                    colunas_num = ['Quantidade', 'Preço unitário', 'Valor da Operação', 'Preço Unitário']
                    for c in colunas_num:
                        if c in df_i.columns:
                            df_i[c] = pd.to_numeric(
                                df_i[c].astype(str).replace('-', '0').str.replace(',', '.'),
                                errors='coerce'
                            ).fillna(0.0)

                    # Identificação da coluna de Data
                    c_data = next(c for c in ['Data', 'Data do Pregão', 'Data do pregão'] if c in df_i.columns)
                    df_i[c_data] = pd.to_datetime(df_i[c_data], dayfirst=True)

                    if st.button("🚀 Confirmar Importação para Nuvem", width='stretch', type="primary"):
                        from database import supabase
                        usuario_atual = st.session_state.get('username')

                        if not usuario_atual:
                            st.error("Usuário não identificado. Faça login.")
                        else:
                            # Identifica colunas de Tipo e Produto
                            c_tipo = next(c for c in ['Tipo de Movimentação', 'Movimentação'] if c in df_i.columns)
                            c_prod = next(c for c in ['Produto', 'Ativo'] if c in df_i.columns)

                            sucesso_count = 0

                            with st.status("Processando registros...", expanded=True) as status:
                                for _, row in df_i.iterrows():
                                    tipo_str = str(row[c_tipo])
                                    if "Compra" in tipo_str or "Venda" in tipo_str:
                                        # Extrai o Ticker (ex: PETR4 - PETROLEO BRASILEIRO)
                                        tk = str(row[c_prod]).split(' - ')[0].strip().upper()
                                        tp = "Compra" if "Compra" in tipo_str else "Venda"

                                        # 1. Garante que o ATIVO existe (ou atualiza nome)
                                        ativo_data = {
                                            "ticker": tk,
                                            "nome": str(row[c_prod]),
                                            "tipo": "Ação",  # Valor padrão na importação
                                            "setor": "Outros"
                                        }
                                        supabase.table("ativos").upsert(ativo_data, on_conflict="ticker").execute()

                                        # 2. Insere a TRANSAÇÃO vinculada ao usuário
                                        nova_trans = {
                                            "data": str(row[c_data].date()),
                                            "ativo": tk,
                                            "quantidade": float(row['Quantidade']),
                                            "preco_unitario": float(
                                                row.get('Preço unitário', row.get('Preço Unitário', 0))),
                                            "tipo_operacao": tp,
                                            "corretora": "B3 (Importado)",
                                            "usuario_id": usuario_atual
                                        }
                                        supabase.table("transacoes_invest").insert(nova_trans).execute()
                                        sucesso_count += 1
                                        st.write(f"✅ {tk} importado...")

                                status.update(label=f"Importação de {sucesso_count} itens concluída!", state="complete")

                            st.success(f"Foram importados {sucesso_count} registros com sucesso!")
                            st.rerun()

                except Exception as e:
                    st.error(f"❌ Erro na importação: {e}")

    # Execução principal do módulo
    if __name__ == "__main__":
        render_investimentos()