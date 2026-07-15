import streamlit as st
import duckdb
import os
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- AJUSTE DE CAMINHO PARA PASTA SERVICES ---
caminho_projeto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if caminho_projeto not in sys.path:
    sys.path.append(caminho_projeto)

try:
    from services.web_tools import obter_preco_atual
    import yfinance as yf
except ModuleNotFoundError:
    st.error("Erro: Verifique as dependências (yfinance) e a pasta 'services'.")


# --- CONFIGURAÇÃO DO BANCO ---
def inicializar_banco_investimentos():
    caminho_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_db = os.path.join(caminho_base, 'financas.db')
    con = duckdb.connect(caminho_db)
    con.execute("CREATE SEQUENCE IF NOT EXISTS seq_transacao_id START 1;")
    con.execute("""
        CREATE TABLE IF NOT EXISTS ativos (
            ticker TEXT PRIMARY KEY,
            nome TEXT,
            tipo TEXT, 
            setor TEXT
        );
        CREATE TABLE IF NOT EXISTS transacoes_invest (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_transacao_id'),
            data DATE,
            ticker TEXT,
            quantidade DOUBLE,
            preco_unitario DOUBLE,
            tipo_operacao TEXT, 
            corretora TEXT,
            FOREIGN KEY (ticker) REFERENCES ativos(ticker)
        );
    """)
    con.close()


def conectar_banco():
    caminho_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_db = os.path.join(caminho_base, 'financas.db')
    return duckdb.connect(caminho_db)


def render_investimentos():
    inicializar_banco_investimentos()
    st.title("🏦 Finanças Pro - Investimentos")

    tab_dash, tab_evolucao, tab_cadastro, tab_transacao, tab_import = st.tabs([
        "📊 Dashboard", "📈 Evolução por Ativo", "🆕 Ativos", "💸 Operações", "📥 Importar B3"
    ])

    # --- ABA: EVOLUÇÃO PATRIMONIAL COM FILTRO DE ATIVOS ---
    with tab_evolucao:
        st.subheader("Análise Comparativa de Ativos")

        con = conectar_banco()
        df_trans = con.execute("SELECT * FROM transacoes_invest ORDER BY data").df()
        con.close()

        if df_trans.empty:
            st.info("Adicione transações para visualizar a evolução.")
        else:
            tickers_disponiveis = sorted(df_trans['ticker'].unique().tolist())

            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                ativos_selecionados = st.multiselect(
                    "Selecione os Ativos para análise:",
                    options=tickers_disponiveis,
                    default=tickers_disponiveis
                )
            with col_f2:
                # Período
                data_min_base = pd.to_datetime(df_trans['data']).min().date()
                inicio = st.date_input("Início", data_min_base, key="ev_ini")
                fim = st.date_input("Fim", datetime.now().date(), key="ev_fim")

            if st.button("🚀 Gerar Análise Detalhada"):
                if not ativos_selecionados:
                    st.warning("Selecione pelo menos um ativo.")
                else:
                    with st.spinner("Buscando dados históricos no Yahoo Finance..."):
                        date_range = pd.date_range(start=inicio, end=fim)
                        df_master = pd.DataFrame({'Data': date_range.date})

                        fig_evol = go.Figure()

                        # Lista para armazenar o total somado de todos os ativos selecionados
                        df_master['Total_Somado'] = 0.0

                        for t in ativos_selecionados:
                            t_yf = t.strip().upper()
                            if not t_yf.endswith(".SA") and len(t_yf) <= 6:
                                t_yf += ".SA"

                            try:
                                hist = yf.download(t_yf, start=inicio, end=fim + timedelta(days=1), progress=False)
                                if not hist.empty:
                                    hist = hist.reset_index()
                                    hist['Date'] = hist['Date'].dt.date
                                    hist = hist[['Date', 'Close']].copy()
                                    hist.columns = ['Data', 'Preco']

                                    # Merge e preenchimento de lacunas (fds/feriados)
                                    df_ticker = pd.merge(pd.DataFrame({'Data': date_range.date}), hist, on='Data',
                                                         how='left')
                                    df_ticker['Preco'] = df_ticker['Preco'].ffill().bfill()

                                    # Calcular evolução de valor para este ativo específico
                                    valores_ativo = []
                                    for idx, row in df_ticker.iterrows():
                                        data_ref = row['Data']
                                        trans_ate_data = df_trans[(df_trans['ticker'] == t) & (
                                                    pd.to_datetime(df_trans['data']).dt.date <= data_ref)]
                                        qtd_acum = trans_ate_data.apply(
                                            lambda x: x['quantidade'] if x['tipo_operacao'] == 'Compra' else -x[
                                                'quantidade'], axis=1).sum()

                                        valor_no_dia = (qtd_acum * float(row['Preco'])) if qtd_acum > 0 else 0
                                        valores_ativo.append(valor_no_dia)

                                    # Adiciona linha individual ao gráfico
                                    fig_evol.add_trace(go.Scatter(
                                        x=df_ticker['Data'],
                                        y=valores_ativo,
                                        mode='lines',
                                        name=f"Individual: {t}",
                                        visible='legendonly' if len(ativos_selecionados) > 1 else True
                                    ))

                                    # Soma ao total
                                    df_master['Total_Somado'] += valores_ativo
                            except:
                                continue

                        # Adiciona a linha de PATRIMÔNIO TOTAL (Somatório dos selecionados)
                        fig_evol.add_trace(go.Scatter(
                            x=df_master['Data'],
                            y=df_master['Total_Somado'],
                            fill='tozeroy',
                            line=dict(color='#00FFCC', width=4),
                            name="Patrimônio Total Selecionado"
                        ))

                        fig_evol.update_layout(
                            template="plotly_dark",
                            title="Evolução do Patrimônio (R$)",
                            xaxis_title="Tempo",
                            yaxis_title="Valor em Carteira",
                            hovermode="x unified",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(fig_evol, use_container_width=True)

    # --- ABA: DASHBOARD ---
    with tab_dash:
        con = conectar_banco()
        df_posicao = con.execute("""
            SELECT t.ticker, a.tipo, a.setor,
                   SUM(CASE WHEN t.tipo_operacao = 'Compra' THEN t.quantidade ELSE -t.quantidade END) as qtd_total,
                   SUM(CASE WHEN t.tipo_operacao = 'Compra' THEN t.quantidade * t.preco_unitario ELSE 0 END) / 
                   NULLIF(SUM(CASE WHEN t.tipo_operacao = 'Compra' THEN t.quantidade ELSE 0 END), 0) as preco_medio
            FROM transacoes_invest t
            JOIN ativos a ON t.ticker = a.ticker
            GROUP BY t.ticker, a.tipo, a.setor HAVING qtd_total > 0
        """).df()
        con.close()

        if not df_posicao.empty:
            with st.spinner('Atualizando cotações...'):
                df_posicao['Preço Atual'] = df_posicao['ticker'].apply(obter_preco_atual)

            df_posicao['Total Atual (R$)'] = df_posicao['qtd_total'] * df_posicao['Preço Atual']
            total_carteira = df_posicao['Total Atual (R$)'].sum()

            st.metric("Patrimônio Atualizado", f"R$ {total_carteira:,.2f}")

            col1, col2 = st.columns(2)
            with col1:
                fig_tipo = px.pie(df_posicao, values='Total Atual (R$)', names='tipo', hole=0.4,
                                  title="Alocação por Classe", template="plotly_dark")
                st.plotly_chart(fig_tipo, use_container_width=True)
            with col2:
                fig_setor = px.pie(df_posicao, values='Total Atual (R$)', names='setor', hole=0.4,
                                   title="Alocação por Setor", template="plotly_dark")
                st.plotly_chart(fig_setor, use_container_width=True)

            st.write("### Detalhes da Carteira")
            st.dataframe(df_posicao, width='stretch')
        else:
            st.info("Nenhum dado para exibir no Dashboard.")

    # --- ABA: CADASTRO DE ATIVOS ---
    with tab_cadastro:
        st.subheader("Novo Ativo")
        with st.form("form_ativo"):
            c1, c2 = st.columns(2)
            ticker = c1.text_input("Ticker (Ex: PETR4)").upper().strip()
            nome = c2.text_input("Nome da Empresa")
            tipo = c1.selectbox("Tipo", ["Ação", "FII", "ETF", "Tesouro", "Cripto"])
            setor = c2.selectbox("Setor",
                                 ["Bancos", "Energia", "Varejo", "Saúde", "Tecnologia", "Commodities", "Imobiliário",
                                  "Outros"])
            if st.form_submit_button("Salvar Ativo"):
                if ticker and nome:
                    con = conectar_banco()
                    con.execute("INSERT OR IGNORE INTO ativos VALUES (?,?,?,?)", [ticker, nome, tipo, setor])
                    con.close()
                    st.success(f"Ativo {ticker} cadastrado!")

    # --- ABA: REGISTRO DE TRANSAÇÕES ---
    with tab_transacao:
        st.subheader("Nova Operação")
        con = conectar_banco()
        ativos_lista = con.execute("SELECT ticker FROM ativos").df()['ticker'].tolist()
        con.close()

        if ativos_lista:
            with st.form("form_op"):
                c1, c2 = st.columns(2)
                data_op = c1.date_input("Data", datetime.now())
                ativo_sel = c1.selectbox("Ativo", ativos_lista)
                tipo_op = c2.radio("Tipo", ["Compra", "Venda"])
                qtd = c2.number_input("Quantidade", min_value=0.0)
                prc = c2.number_input("Preço Unitário", min_value=0.0)
                if st.form_submit_button("Registrar Operação"):
                    con = conectar_banco()
                    con.execute(
                        "INSERT INTO transacoes_invest (data, ticker, quantidade, preco_unitario, tipo_operacao, corretora) VALUES (?,?,?,?,?,?)",
                        [data_op, ativo_sel, qtd, prc, tipo_op, "Manual"])
                    con.close()
                    st.success("Operação registrada!")
                    st.rerun()

    # --- ABA: IMPORTAR B3 ---
    with tab_import:
        st.subheader("Importar Excel B3")
        up = st.file_uploader("Arquivo B3 (.xlsx)", type=['xlsx'])
        if up:
            try:
                df_i = pd.read_excel(up)
                df_i.columns = [str(c).strip() for c in df_i.columns]
                for c in ['Quantidade', 'Preço unitário', 'Valor da Operação', 'Preço Unitário']:
                    if c in df_i.columns:
                        df_i[c] = pd.to_numeric(df_i[c].astype(str).str.replace('-', '0').str.replace(',', '.'),
                                                errors='coerce').fillna(0.0)
                c_data = next(c for c in ['Data', 'Data do Pregão'] if c in df_i.columns)
                df_i[c_data] = pd.to_datetime(df_i[c_data], dayfirst=True)

                if st.button("Confirmar Importação de Dados"):
                    con = conectar_banco()
                    c_tipo = next(c for c in ['Tipo de Movimentação', 'Movimentação'] if c in df_i.columns)
                    c_prod = next(c for c in ['Produto', 'Ativo'] if c in df_i.columns)
                    for _, row in df_i.iterrows():
                        if "Compra" in str(row[c_tipo]) or "Venda" in str(row[c_tipo]):
                            tk = str(row[c_prod]).split(' - ')[0].strip().upper()
                            tp = "Compra" if "Compra" in str(row[c_tipo]) else "Venda"
                            con.execute("INSERT OR IGNORE INTO ativos VALUES (?,?,?,?)",
                                        [tk, str(row[c_prod]), "Ação", "Outros"])
                            con.execute(
                                "INSERT INTO transacoes_invest (data, ticker, quantidade, preco_unitario, tipo_operacao, corretora) VALUES (?,?,?,?,?,?)",
                                [row[c_data].date(), tk, row['Quantidade'], row['Preço unitário'], tp, 'B3'])
                    con.close()
                    st.success("Importação concluída!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro na importação: {e}")


if __name__ == "__main__":
    render_investimentos()