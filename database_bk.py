import streamlit as st
from supabase import create_client, Client
import pandas as pd
import hashlib

# 1. Conexão com o Supabase usando os Secrets
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def get_supabase():
    """Retorna a instância do cliente Supabase."""
    return supabase

# --- FUNÇÕES DE USUÁRIOS ---

def buscar_usuario(username):
    """Busca um usuário no banco de dados do Supabase."""
    try:
        response = supabase.table("usuarios").select("*").eq("username", username).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Erro ao buscar usuário: {e}")
        return None

def criar_usuario(username, senha, email, nivel="Usuário"):
    """Cria um novo usuário na nuvem."""
    dados = {
        "username": username,
        "senha": senha,
        "email": email,
        "nivel": nivel,
        "aprovado": False
    }
    return supabase.table("usuarios").insert(dados).execute()

def hash_password(password):
    """Gera hash seguro para senhas."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- FUNÇÕES DE TRANSAÇÕES E LANÇAMENTOS ---

def carregar_dados(username=None):
    """Lê as transações do Supabase filtrando por username."""
    try:
        query = supabase.table("transacoes").select("*")

        if username:
            query = query.eq("username", username)

        response = query.order("data", desc=True).execute()
        df = pd.DataFrame(response.data)

        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])

        return df
    except Exception as e:
        print(f"Erro ao carregar transações: {e}")
        return pd.DataFrame()

def inserir_transacao(dados):
    """Salva uma nova transação no Supabase garantindo mapeamento de chaves."""
    try:
        # Se o dicionário enviado contiver 'usuario_id', mapeia e altera para 'username'
        if 'usuario_id' in dados:
            dados['username'] = dados.pop('usuario_id')

        response = supabase.table("transacoes").insert(dados).execute()
        return response
    except Exception as e:
        st.error(f"Erro ao salvar transação no Supabase: {e}")
        return None

def salvar_transacao(dados):
    """Alias compatível para inserir_transacao."""
    return inserir_transacao(dados)

# --- FUNÇÕES DE CONFIGURAÇÕES (CONTAS E CATEGORIAS) ---

def carregar_dados_config(tabela, username):
    """
    Busca dados de tabelas de configuração (cad_contas, cad_categorias)
    filtrando pelo proprietário logado OU pela estrutura herdada do 'admin'.
    """
    try:
        # Busca o que pertence ao usuário ou à estrutura global do admin
        response = supabase.table(tabela) \
            .select("*") \
            .or_(f"username.eq.{username},username.eq.admin") \
            .execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao carregar {tabela}: {e}")
        return pd.DataFrame()

def buscar_categorias(username):
    """Busca as categorias cadastradas na nuvem filtrando pelo usuário logado ou pelo admin (global)."""
    try:
        response = supabase.table("cad_categorias") \
            .select("*") \
            .or_(f"username.eq.{username},username.eq.admin") \
            .execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return pd.DataFrame()

def buscar_contas(username):
    """Busca as contas cadastradas na nuvem filtrando pelo usuário logado ou pelo admin (global)."""
    try:
        response = supabase.table("cad_contas") \
            .select("*") \
            .or_(f"username.eq.{username},username.eq.admin") \
            .execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao buscar contas: {e}")
        return pd.DataFrame()

# --- FUNÇÕES DE SALDO E DASHBOARD ---

def get_saldo_por_conta(nome_conta, username):
    """Retorna o saldo acumulado de uma conta específica para o usuário."""
    try:
        response = supabase.table("transacoes") \
            .select("valor") \
            .eq("conta", nome_conta) \
            .eq("username", username) \
            .execute()

        lista_valores = [float(item['valor']) for item in response.data if item.get('valor') is not None]
        return sum(lista_valores) if lista_valores else 0.0
    except Exception as e:
        print(f"Erro ao obter saldo da conta {nome_conta}: {e}")
        return 0.0

def get_saldo_por_tipo(tipo_conta, username):
    """Soma o saldo de tipos de conta (ex: Investimento) para o usuário logado."""
    try:
        # 1. Descobre as contas pertencentes a este tipo (busca tanto do usuário quanto do admin)
        res_contas = supabase.table("cad_contas") \
            .select("nome") \
            .eq("tipo", tipo_conta) \
            .or_(f"username.eq.{username},username.eq.admin") \
            .execute()

        # Remove duplicatas de nomes de contas se houver
        nomes_contas = list(set([c['nome'] for c in res_contas.data]))

        # 2. Sem contas cadastradas para este tipo, o saldo é zero
        if not nomes_contas:
            return 0.0

        # 3. Busca e soma os valores de transações ocorridas nessas contas pertencentes ao usuário logado
        response = supabase.table("transacoes") \
            .select("valor") \
            .eq("username", username) \
            .in_("conta", nomes_contas) \
            .execute()

        valores = [float(item['valor']) for item in response.data if item.get('valor') is not None]
        return sum(valores) if valores else 0.0
    except Exception as e:
        print(f"Erro ao obter saldo por tipo {tipo_conta}: {e}")
        return 0.0

def get_resumo_patrimonio(username):
    """Retorna o dicionário de resumo patrimonial formatado para cartões e KPIs."""
    try:
        # Busca saldos de liquidez e conta corrente
        saldo_liquidez = get_saldo_por_tipo('Investimento (Liquidez)', username)
        saldo_contas = get_saldo_por_tipo('Conta Corrente', username)

        # Carrega dados do usuário na memória para somatórios
        df = carregar_dados(username)

        if not df.empty:
            # Filtra valores positivos e negativos ignorando valores vazios
            ganhos = df[df['valor'] > 0]['valor'].sum()
            gastos = df[df['valor'] < 0]['valor'].sum()
        else:
            ganhos = 0.0
            gastos = 0.0

        return {
            "Disponível": float(saldo_liquidez + saldo_contas),
            "Ganhos": float(ganhos),
            "Gastos": float(abs(gastos)),
            "Investido": float(saldo_liquidez)
        }
    except Exception as e:
        print(f"Erro ao gerar resumo de patrimônio: {e}")
        return {
            "Disponível": 0.0,
            "Ganhos": 0.0,
            "Gastos": 0.0,
            "Investido": 0.0
        }

# --- FUNÇÕES DE INVESTIMENTOS ---

def carregar_transacoes_invest(username):
    """Busca as transações de investimento registradas no Supabase."""
    try:
        response = supabase.table("transacoes_invest") \
            .select("*") \
            .eq("usuario_id", username) \
            .order("data", desc=True) \
            .execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao carregar transações de investimentos: {e}")
        return pd.DataFrame()