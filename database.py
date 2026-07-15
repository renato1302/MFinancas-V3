import streamlit as st
from supabase import create_client, Client
import pandas as pd
import hashlib  # <--- ESSENCIAL PARA O HASH_PASSWORD FUNCIONAR


# 1. Conexão com o Supabase usando os Secrets que você criou
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def get_supabase():
    """Retorna a instância do cliente Supabase."""
    return supabase

# --- FUNÇÕES DE USUÁRIOS ---

def buscar_usuario(username):
    """Busca um usuário no banco de dados do Supabase."""
    response = supabase.table("usuarios").select("*").eq("username", username).execute()
    return response.data[0] if response.data else None

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
    return hashlib.sha256(password.encode()).hexdigest()


def carregar_dados(username=None):
    """Lê as transações do Supabase filtrando por usuario_id."""
    query = supabase.table("transacoes").select("*")

    if username:
        # TROQUE 'username' por 'usuario_id' aqui:
        query = query.eq("username", username)

    response = query.order("data", desc=True).execute()
    df = pd.DataFrame(response.data)

    if not df.empty:
        df['data'] = pd.to_datetime(df['data'])

    return df


def inserir_transacao(dados):
    """Salva uma nova transação no Supabase."""
    try:
        # Se o dicionário que vem da View usa 'usuario_id',
        # vamos garantir que ele vire 'username' antes de enviar
        if 'usuario_id' in dados:
            dados['username'] = dados.pop('usuario_id')

        response = supabase.table("transacoes").insert(dados).execute()
        return response
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")
        return None

def carregar_dados_config(tabela, username):
    """
    Busca dados de tabelas de configuração (cad_contas, cad_categorias)
    filtrando pelo dono da conta.
    """
    try:
        response = supabase.table(tabela).select("*").eq("username", username).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao carregar {tabela}: {e}")
        return pd.DataFrame()

def get_saldo_por_conta(nome_conta, username):
    """Retorna o saldo de uma conta específica para um usuário no Supabase."""
    # 1. Buscamos na tabela 'transacoes'
    # 2. Selecionamos apenas a coluna 'valor' (para ser mais rápido)
    # 3. Filtramos pela conta E pelo username
    response = supabase.table("transacoes") \
        .select("valor") \
        .eq("conta", nome_conta) \
        .eq("username", username) \
        .execute()

    # 4. Somamos os valores que voltaram na lista
    lista_valores = [item['valor'] for item in response.data]
    return float(sum(lista_valores)) if lista_valores else 0.0


def get_saldo_por_tipo(tipo_conta, username):
    """Soma o saldo de tipos de conta (ex: Investimento) para o usuário logado no Supabase."""
    # 1. Primeiro, descobrimos quais contas pertencem a esse 'tipo' (ex: 'Investimento')
    # Buscamos na tabela 'cad_contas' (que você deve ter criado no SQL Editor)
    res_contas = supabase.table("cad_contas") \
        .select("nome") \
        .eq("tipo", tipo_conta) \
        .execute()

    nomes_contas = [c['nome'] for c in res_contas.data]

    # 2. Se não houver nenhuma conta desse tipo cadastrada, o saldo é zero
    if not nomes_contas:
        return 0.0

    # 3. Agora buscamos a soma dos valores na tabela 'transacoes'
    # O filtro '.in_("coluna", lista)' substitui aquele 'IN (?, ?, ?)' do SQL
    response = supabase.table("transacoes") \
        .select("valor") \
        .eq("username", username) \
        .in_("conta", nomes_contas) \
        .execute()

    # 4. Somamos os valores retornados
    valores = [item['valor'] for item in response.data]
    return float(sum(valores)) if valores else 0.0


def get_resumo_patrimonio(username):
    """Retorna o resumo financeiro do Supabase filtrado pelo usuário logado."""

    # 1. Busca os saldos específicos usando as funções que já adaptamos
    saldo_liquidez = get_saldo_por_tipo('Investimento (Liquidez)', username)
    saldo_contas = get_saldo_por_tipo('Conta Corrente', username)

    # 2. Carrega todas as transações do usuário (da nuvem) para calcular totais
    df = carregar_dados(username)

    # 3. Cálculos matemáticos (isso o Pandas faz na memória, não depende do banco)
    if not df.empty:
        ganhos = df[df['valor'] > 0]['valor'].sum()
        gastos = df[df['valor'] < 0]['valor'].sum()
    else:
        ganhos = 0.0
        gastos = 0.0

    # 4. Retorna o dicionário que alimenta os cartões do seu Dashboard
    return {
        "Disponível": float(saldo_liquidez + saldo_contas),
        "Ganhos": float(ganhos),
        "Gastos": float(abs(gastos)),
        "Investido": float(saldo_liquidez)
    }

def salvar_transacao(dados):
    """
    Envia uma nova transação (dicionário) para a tabela no Supabase.
    """
    # No Supabase, basta passar o dicionário diretamente para o .insert()
    # Ele deve conter as chaves: valor, tipo, grupo, subgrupo, conta, data, username, etc.
    try:
        response = supabase.table("transacoes").insert(dados).execute()
        return response
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")
        return None

def buscar_categorias(username):
    """Busca as categorias cadastradas na nuvem filtrando pelo usuário."""
    try:
        response = supabase.table("cad_categorias") \
            .select("*") \
            .eq("username", username) \
            .execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return pd.DataFrame()

def buscar_contas(username):
    """Busca as contas cadastradas na nuvem filtrando pelo usuário."""
    try:
        response = supabase.table("cad_contas") \
            .select("*") \
            .eq("username", username) \
            .execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao buscar contas: {e}")
        return pd.DataFrame()

def carregar_transacoes_invest(username):
    """Busca as transações de investimento do Supabase"""
    try:
        # Tabela real: transacoes_invest
        # Coluna real: data
        response = supabase.table("transacoes_invest") \
            .select("*") \
            .eq("usuario_id", username) \
            .order("data", desc=True) \
            .execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Erro ao carregar transações de invest: {e}")
        return pd.DataFrame()