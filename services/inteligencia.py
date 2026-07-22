import re
import uuid
import streamlit as st
from database import supabase  # Certifique-se de que a importação do seu Supabase está correta


def eh_uuid_valido(val):
    """Verifica se uma string é um UUID válido."""
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def obter_uuid_usuario(usuario_id_fornecido=None):
    """
    Garante o retorno de um UUID válido.
    Testa parâmetros passados e vasculha todas as estruturas comuns do Supabase no Streamlit.
    """
    # 1. Se foi passado um parâmetro válido
    if eh_uuid_valido(usuario_id_fornecido):
        return str(usuario_id_fornecido)

    if hasattr(usuario_id_fornecido, 'id') and eh_uuid_valido(usuario_id_fornecido.id):
        return str(usuario_id_fornecido.id)

    # 2. Busca direta por chaves comuns
    candidates = [
        st.session_state.get('user_id'),
        st.session_state.get('usuario_id'),
        st.session_state.get('uid'),
        st.session_state.get('user'),
        st.session_state.get('session')
    ]

    for c in candidates:
        if not c:
            continue
        if eh_uuid_valido(c):
            return str(c)
        if hasattr(c, 'id') and eh_uuid_valido(c.id):
            return str(c.id)
        if hasattr(c, 'user') and hasattr(c.user, 'id') and eh_uuid_valido(c.user.id):
            return str(c.user.id)

    # 3. Fallback: Procura em qualquer lugar do session_state
    for k, v in st.session_state.items():
        if eh_uuid_valido(v):
            return str(v)
        if hasattr(v, 'id') and eh_uuid_valido(v.id):
            return str(v.id)
        if hasattr(v, 'user') and hasattr(v.user, 'id') and eh_uuid_valido(v.user.id):
            return str(v.user.id)

    # Diagnóstico para aprendizado/debug no console
    print(f"⚠️ [obter_uuid_usuario]: Nenhum UUID encontrado. Chaves disponíveis na sessão: {list(st.session_state.keys())}")
    return None


def limpar_descricao(descricao):
    """
    Remove números, caracteres especiais e espaços extras para encontrar
    o padrão do estabelecimento (ex: 'IFOOD *123' vira 'ifood').
    """
    if not descricao or not isinstance(descricao, str):
        return ""
    desc = descricao.lower()
    # Remove números e caracteres especiais
    desc = re.sub(r'[^a-zA-Z\s]', '', desc)
    # Remove espaços extras nas pontas e duplos no meio
    desc = " ".join(desc.split())
    return desc


def buscar_base_aprendizado(usuario_id):
    """
    Busca todas as regras de inteligência que o usuário já alimentou no banco.
    """
    uid = obter_uuid_usuario(usuario_id)
    if not uid:
        print("Aviso [buscar_base_aprendizado]: Nenhum UUID de usuário válido foi fornecido.")
        return []

    try:
        resposta = supabase.table("inteligencia_categorias").select("*").eq("usuario_id", uid).execute()
        return resposta.data if resposta.data else []
    except Exception as e:
        print(f"Erro ao buscar base de aprendizado: {e}")
        return []


def sugerir_categoria(descricao_original, base_aprendizado):
    """
    Varre a base de aprendizado para sugerir Grupo e Subgrupo.
    """
    desc_limpa = limpar_descricao(descricao_original)

    sugestao_padrao = {
        "grupo": "A Categorizar",
        "subgrupo": "A Categorizar",
        "subcategoria": "A Categorizar"
    }

    if not desc_limpa:
        return sugestao_padrao

    for registro in base_aprendizado:
        termo_aprendido = registro.get('termo_extrato', '')

        # Se o termo que o sistema aprendeu estiver dentro da descrição do extrato
        # Ou se a descrição limpa atual for idêntica/contida no termo aprendido
        if termo_aprendido in desc_limpa or desc_limpa in termo_aprendido:
            return {
                "grupo": registro['grupo'],
                "subgrupo": registro['subgrupo'],
                "subcategoria": registro.get('subcategoria') or "A Categorizar"
            }

    return sugestao_padrao


def treinar_sistema(transacoes_revisadas, usuario_id):
    """
    Pega a lista de transações que o usuário acabou de salvar no banco,
    aprende com as categorias escolhidas e atualiza a tabela inteligencia_categorias.
    """
    uid = obter_uuid_usuario(usuario_id)
    if not uid:
        print("Erro [treinar_sistema]: Não foi possível obter um UUID válido para salvar a regra.")
        return

    for transacao in transacoes_revisadas:
        desc_limpa = limpar_descricao(transacao.get('descricao', ''))
        grupo = transacao.get('grupo')
        subgrupo = transacao.get('subgrupo')
        subcategoria = transacao.get('subcategoria')

        # Não vamos ensinar o sistema a categorizar algo como "A Categorizar"!
        if not desc_limpa or grupo == "A Categorizar" or not grupo:
            continue

        dados_aprendizado = {
            "usuario_id": uid,
            "termo_extrato": desc_limpa,
            "grupo": grupo,
            "subgrupo": subgrupo,
            "subcategoria": subcategoria if subcategoria != "A Categorizar" else None
        }

        try:
            # upsert: insere se não existir, ou atualiza se já existir para aquele usuario + termo
            supabase.table("inteligencia_categorias").upsert(
                dados_aprendizado,
                on_conflict="usuario_id,termo_extrato"
            ).execute()
        except Exception as e:
            print(f"Erro ao atualizar inteligência para '{desc_limpa}': {e}")