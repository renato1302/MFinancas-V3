import yfinance as yf
import pandas as pd


def processar_excel_b3(caminho_arquivo):
    """Lê o Excel da B3 e retorna um DataFrame formatado para o banco."""
    df = pd.read_excel(caminho_arquivo)

    # A B3 costuma usar nomes de colunas específicos. Ajustamos aqui:
    # Nota: Você deve conferir se os nomes batem com o seu Excel baixado
    colunas_map = {
        'Data': 'data',
        'Produto': 'ticker',
        'Quantidade': 'quantidade',
        'Preço Unitário': 'preco_unitario',
        'Tipo de Movimentação': 'tipo_operacao'
    }

    df = df.rename(columns=colunas_map)

    # Filtrar apenas o que nos interessa (Compra e Venda)
    df = df[df['tipo_operacao'].isin(['Compra', 'Venda'])]

    # Limpeza de Ticker (remover o CNPJ ou descrições que a B3 coloca junto)
    # Ex: "AMER3 - AMERICANAS S.A." vira apenas "AMER3"
    df['ticker'] = df['ticker'].str.split(' - ').str[0].str.strip()

    return df[['data', 'ticker', 'quantidade', 'preco_unitario', 'tipo_operacao']]


def obter_preco_atual(ticker):
    """
    Busca o preço atual de um ativo na B3 usando yfinance.
    Exemplo: obter_preco_atual("AMER3")
    """
    try:
        # Formata o ticker para o padrão do Yahoo Finance (ex: AMER3.SA)
        ticker_formatado = ticker.strip().upper()
        if not ticker_formatado.endswith(".SA"):
            ticker_formatado += ".SA"

        # Busca os dados do ativo
        ativo = yf.Ticker(ticker_formatado)

        # Pega o histórico do último dia (1d)
        dados = ativo.history(period="1d")

        if not dados.empty:
            # Pega o último preço de fechamento
            preco = dados['Close'].iloc[-1]
            return round(float(preco), 2)
        else:
            print(f"Aviso: Ticker {ticker_formatado} não encontrado.")
            return None

    except Exception as e:
        print(f"Erro ao buscar cotação de {ticker}: {e}")
        return None


# Teste rápido (apenas se rodar este arquivo diretamente)
if __name__ == "__main__":
    teste = "AMER3"
    valor = obter_preco_atual(teste)
    print(f"O preço atual de {teste} é: R$ {valor}")