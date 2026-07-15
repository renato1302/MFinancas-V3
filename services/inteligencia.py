import re
from database import supabase  # Certifique-se de que a importação do seu Supabase está correta


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
    try:
        resposta = supabase.table("inteligencia_categorias").select("*").eq("usuario_id", usuario_id).execute()
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
        termo_aprendido = registro['termo_extrato']

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
    for transacao in transacoes_revisadas:
        desc_limpa = limpar_descricao(transacao.get('descricao', ''))
        grupo = transacao.get('grupo')
        subgrupo = transacao.get('subgrupo')
        subcategoria = transacao.get('subcategoria')

        # Não vamos ensinar o sistema a categorizar algo como "A Categorizar"!
        if not desc_limpa or grupo == "A Categorizar" or not grupo:
            continue

        dados_aprendizado = {
            "usuario_id": usuario_id,
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