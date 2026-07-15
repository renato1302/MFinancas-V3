import streamlit as st
import duckdb
import os
import pandas as pd
from datetime import datetime


def inicializar_banco_investimentos():
    caminho_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_db = os.path.join(caminho_base, 'financas.db')
    con = duckdb.connect(caminho_db)

    # Criamos as tabelas com usuario_id como TEXT e ID autoincrement simples
    con.execute("""
        CREATE TABLE IF NOT EXISTS ativos (
            ticker TEXT PRIMARY KEY,
            nome TEXT,
            tipo TEXT, 
            setor TEXT
        );
        CREATE TABLE IF NOT EXISTS transacoes_invest (
            id INTEGER PRIMARY KEY, 
            usuario_id TEXT, 
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


# Funções que o Dashboard e as Configurações vão "chamar"
def carregar_posicao_investimentos(username):
    con = conectar_banco()
    df = con.execute("""
        SELECT t.ticker, a.tipo,
               SUM(CASE WHEN t.tipo_operacao = 'Compra' THEN t.quantidade ELSE -t.quantidade END) as qtd_total,
               AVG(t.preco_unitario) as preco_medio
        FROM transacoes_invest t
        JOIN ativos a ON t.ticker = a.ticker
        WHERE t.usuario_id = ?
        GROUP BY t.ticker, a.tipo HAVING qtd_total > 0
    """, [username]).df()
    con.close()
    return df


def render_investimentos():
    # Esta função será usada apenas temporariamente até movermos tudo
    # para Dashboard e Configurações
    inicializar_banco_investimentos()
    usuario_atual = st.session_state.get('username')

    if not usuario_atual:
        st.error("Por favor, faça login.")
        return

    st.info(f"Módulo de Investimentos ativo para: {usuario_atual}")
    # (Resto do seu código de dashboard de investimentos aqui...)