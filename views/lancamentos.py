import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
# Importamos as funções que conversam com o Supabase
from database import buscar_contas, buscar_categorias, carregar_dados, inserir_transacao
# IMPORTAÇÃO DO MÓDULO DE INTELIGÊNCIA ARTIFICIAL / APRENDIZADO
from services.inteligencia import treinar_sistema, buscar_base_aprendizado, sugerir_categoria


def render_lancamentos():
    st.header("📝 Gestão de Lançamentos")

    # 🔍 LINHA DE DIAGNÓSTICO (mostra na tela quais chaves existem na sessão):
    st.sidebar.write("Chaves na sessão:", list(st.session_state.keys()))

    # 1. Recupera o usuário logado na sessão (Essencial para o Supabase)
    usuario_atual = st.session_state.get('username')

    from services.inteligencia import obter_uuid_usuario
    usuario_uuid = obter_uuid_usuario()

    # 2. BUSCA MULTI-USUÁRIO: Traz tanto a estrutura padrão (admin) quanto a do próprio usuário
    df_contas_admin = buscar_contas("admin")  # Garanta que seu usuário admin principal se chama exatamente "admin"
    df_contas_user = buscar_contas(usuario_atual) if usuario_atual != "admin" else pd.DataFrame()
    df_contas = pd.concat([df_contas_admin, df_contas_user]).drop_duplicates(subset=['nome'])

    df_cats_admin = buscar_categorias("admin")
    df_cats_user = buscar_categorias(usuario_atual) if usuario_atual != "admin" else pd.DataFrame()
    df_cats = pd.concat([df_cats_admin, df_cats_user]).drop_duplicates(subset=['grupo', 'subgrupo', 'subcategoria'])

    # Padroniza nulos para evitar dores de cabeça com filtros na regra de 2 níveis
    df_cats['subcategoria'] = df_cats['subcategoria'].fillna("Padrão").astype(str).str.strip()

    # 3. Validação de segurança
    if df_contas.empty or df_cats.empty:
        st.warning("⚠️ O Administrador precisa cadastrar Contas e Hierarquia de Categorias nas Configurações primeiro.")

        if st.button("Ir para Configurações"):
            st.session_state.menu_option = "Configurações"
            st.rerun()
        return

    # 4. Controle de Permissões
    pode_editar = st.session_state.get('role') in ["Administrador", "Consegue Ler e Lançamentos"]

    # Criamos abas para organizar a tela do celular sem que fique muito longa
    aba_manual, aba_importacao = st.tabs(["➕ Lançamento Manual", "📥 Importar Extrato (CSV)"])

    # --- ABA 1: CADASTRO DE NOVO LANÇAMENTO MANUAL ---
    with aba_manual:
        if pode_editar:
            st.markdown("### 1. Tipo de Operação")
            tipo = st.radio("Tipo de movimentação:", ["Gasto", "Ganho", "Transferência"], horizontal=True,
                            key="new_tipo")

            st.markdown("### 2. Classificação e Detalhes")
            c1, c2, c3 = st.columns([1, 1, 1])
            usar_split = False

            if tipo != "Transferência":
                # Aplica filtro por tipo se a coluna existir para refinar a árvore de seleção
                if 'tipo' in df_cats.columns:
                    df_cats_filtrado = df_cats[df_cats['tipo'] == tipo]
                else:
                    df_cats_filtrado = df_cats

                with c1:
                    lista_grupos = sorted(df_cats_filtrado['grupo'].unique())
                    grupo_sel = st.selectbox("Grupo", lista_grupos, key="new_grupo")

                with c2:
                    # FILTRAGEM DINÂMICA: Subgrupos dependem exclusivamente do Grupo selecionado
                    sub_opts = df_cats_filtrado[df_cats_filtrado['grupo'] == grupo_sel]['subgrupo'].unique()
                    sub_opts_sorted = sorted(sub_opts) if len(sub_opts) > 0 else ["Padrão"]
                    subgrupo_sel = st.selectbox("Subgrupo", sub_opts_sorted, key="new_subgrupo")

                with c3:
                    # FILTRAGEM DINÂMICA: Subcategorias dependem do Grupo AND Subgrupo selecionados
                    filtro_subcat = (df_cats_filtrado['grupo'] == grupo_sel) & (
                                df_cats_filtrado['subgrupo'] == subgrupo_sel)
                    subcat_opts = df_cats_filtrado[filtro_subcat]['subcategoria'].unique()
                    subcat_opts_sorted = sorted(subcat_opts) if len(subcat_opts) > 0 else ["Padrão"]

                    # REGRA DE 2 NÍVEIS: Se for Ganho, não obriga o usuário a selecionar subcategoria
                    if tipo == "Ganho" and (len(subcat_opts_sorted) == 0 or subcat_opts_sorted == ["Padrão"]):
                        subcat_sel = "Padrão"
                        st.text_input("Subcategoria", value="Padrão", disabled=True, key="new_subcat_disabled")
                    else:
                        permitir_split = False
                        if 'permite_split' in df_cats_filtrado.columns:
                            permitir_split = df_cats_filtrado[filtro_subcat]['permite_split'].any()

                        if permitir_split:
                            usar_split = st.toggle("🧩 Desmembrar?",
                                                   help="Ative para distribuir o valor por subcategorias")

                        if not usar_split:
                            subcat_sel = st.selectbox("Subcategoria", subcat_opts_sorted, key="new_subcat")
            else:
                subcat_sel = "Transferência"
                grupo_sel = "Transferência"
                subgrupo_sel = "Transferência"
                st.info("💡 Movimentação entre contas, cofrinho ou aplicações.")

            st.divider()

            d1, d2, d3 = st.columns(3)
            with d1:
                valor_input = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f", key="new_valor")
            with d2:
                data_lanc = st.date_input("Data", value=datetime.now().date(), key="new_data")
            with d3:
                contas_disponiveis = sorted(df_contas['nome'].unique())
                conta_sel = st.selectbox("Conta Origem", contas_disponiveis, key="new_conta")

            desc = st.text_input("Descrição (Ex: Mercado, Combustível...)", key="new_desc")

            if tipo == "Transferência":
                conta_dest = st.selectbox("Conta Destino", contas_disponiveis, key="new_conta_dest")

            # --- PROCESSAMENTO DO BOTÃO SALVAR ---
            if usar_split:
                st.info("Distribua o valor total abaixo:")
                df_split_data = pd.DataFrame({'Subcategoria': sorted(subcat_opts), 'Valor (R$)': 0.0})
                res_editor = st.data_editor(df_split_data, width='stretch', hide_index=True,
                                            key="editor_split")

                soma_atual = res_editor['Valor (R$)'].sum()
                diferenca = valor_input - soma_atual

                st.write(f"Soma: **R$ {soma_atual:.2f}** | Restante: **R$ {diferenca:.2f}**")

                if st.button("🚀 Confirmar Lançamento Desmembrado", type="primary", width='stretch'):
                    if abs(diferenca) > 0.01:
                        st.error("A soma das subcategorias não bate com o valor total.")
                    elif valor_input <= 0:
                        st.error("O valor deve ser maior que zero.")
                    else:
                        try:
                            id_agrupador = str(uuid.uuid4())[:8]
                            sucesso_geral = True
                            transacoes_salvas = []

                            for _, row in res_editor.iterrows():
                                if row['Valor (R$)'] > 0:
                                    v_f = -row['Valor (R$)'] if tipo == "Gasto" else row['Valor (R$)']

                                    dados_lanc = {
                                        "valor": v_f,
                                        "tipo": tipo,
                                        "grupo": grupo_sel,
                                        "subgrupo": subgrupo_sel,
                                        "subcategoria": row['Subcategoria'],
                                        "conta": conta_sel,
                                        "data": str(data_lanc),
                                        "descricao": f"{desc} [{row['Subcategoria']}]",
                                        "id_agrupador": id_agrupador,
                                        "username": usuario_atual
                                    }
                                    if inserir_transacao(dados_lanc):
                                        transacoes_salvas.append(dados_lanc)
                                    else:
                                        sucesso_geral = False

                            if sucesso_geral:
                                treinar_sistema(transacoes_salvas, None)
                                st.success("✅ Nota desmembrada com sucesso no Supabase!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar split: {e}")

            else:
                if st.button("🚀 Confirmar Lançamento", type="primary", width='stretch'):
                    if valor_input > 0:
                        try:
                            if tipo == "Transferência":
                                id_transf = str(uuid.uuid4())[:8]

                                dados_saida = {
                                    "valor": -valor_input,
                                    "tipo": "Transferência",
                                    "grupo": "Transferência",
                                    "subgrupo": "Transferência",
                                    "subcategoria": "Saída",
                                    "conta": conta_sel,
                                    "data": str(data_lanc),
                                    "descricao": f"TR (Saída): {desc}",
                                    "id_agrupador": id_transf,
                                    "username": usuario_atual
                                }

                                dados_entrada = {
                                    "valor": valor_input,
                                    "tipo": "Transferência",
                                    "grupo": "Transferência",
                                    "subgrupo": "Transferência",
                                    "subcategoria": "Entrada",
                                    "conta": conta_dest,
                                    "data": str(data_lanc),
                                    "descricao": f"TR (Entrada): {desc}",
                                    "id_agrupador": id_transf,
                                    "username": usuario_atual
                                }

                                if inserir_transacao(dados_saida) and inserir_transacao(dados_entrada):
                                    st.success("✅ Transferência realizada com sucesso!")
                                    st.rerun()

                            else:
                                valor_final = -valor_input if tipo == "Gasto" else valor_input

                                dados_simples = {
                                    "valor": valor_final,
                                    "tipo": tipo,
                                    "grupo": grupo_sel,
                                    "subgrupo": subgrupo_sel,
                                    "subcategoria": subcat_sel if tipo == "Gasto" else "Padrão",
                                    "conta": conta_sel,
                                    "data": str(data_lanc),
                                    "descricao": desc,
                                    "username": usuario_atual
                                }

                                if inserir_transacao(dados_simples):
                                    user_uuid = st.session_state.get('user_id') or st.session_state.get('usuario_id')
                                    treinar_sistema([dados_simples], user_uuid)
                                    st.success("✅ Lançamento registrado no Supabase!")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar no Supabase: {e}")
                    else:
                        st.error("O valor deve ser maior que zero.")
        else:
            st.info("Você não tem permissões de edição.")

    # --- ABA 2: IMPORTAÇÃO DE ARQUIVO CSV (COM INTELIGÊNCIA ARTIFICIAL E DUPLICADOS) ---
    with aba_importacao:
        if pode_editar:
            st.markdown("### 📂 Importar Extrato Bancário")
            st.write("Faça upload de qualquer extrato em formato `.csv` para ser analisado pela IA.")

            contas_disponiveis = sorted(df_contas['nome'].unique())
            import_conta_sel = st.selectbox("Conta de Origem dos Lançamentos:", contas_disponiveis, key="import_conta")

            arquivo_csv = st.file_uploader("Selecione o arquivo CSV", type=["csv"], key="import_csv_uploader")

            if arquivo_csv is not None:
                try:
                    # Lê para prever as colunas existentes no CSV
                    df_preview = pd.read_csv(arquivo_csv, nrows=5)
                    colunas = list(df_preview.columns)

                    st.info("ℹ️ Mapeie as colunas do seu arquivo abaixo:")
                    col_data, col_desc, col_val = st.columns(3)

                    idx_data = next((i for i, c in enumerate(colunas) if 'data' in c.lower() or 'date' in c.lower()), 0)
                    idx_desc = next((i for i, c in enumerate(colunas) if
                                     'desc' in c.lower() or 'title' in c.lower() or 'historico' in c.lower() or 'hist' in c.lower()),
                                    0)
                    idx_val = next((i for i, c in enumerate(colunas) if
                                    'val' in c.lower() or 'quant' in c.lower() or 'amount' in c.lower() or 'valor' in c.lower()),
                                   0)

                    sel_col_data = col_data.selectbox("Coluna da Data", colunas, index=idx_data)
                    sel_col_desc = col_desc.selectbox("Coluna da Descrição", colunas, index=idx_desc)
                    sel_col_val = col_val.selectbox("Coluna do Valor", colunas, index=idx_val)

                    # Evento do Botão de Processamento
                    if st.button("🧠 Ler Arquivo e Aplicar IA", width='stretch'):
                        arquivo_csv.seek(0)
                        df_completo = pd.read_csv(arquivo_csv)

                        # Validação de limpeza básica
                        df_completo = df_completo[[sel_col_data, sel_col_desc, sel_col_val]].dropna()

                        # Tratamento inteligente de datas (Garante que lerá dia primeiro, evitando inverter dia/mês)
                        df_completo[sel_col_data] = pd.to_datetime(df_completo[sel_col_data],
                                                                   dayfirst=True,
                                                                   errors='coerce').dt.strftime('%Y-%m-%d')

                        # Conversão robusta de valores monetários (Trata R$, espaços e formatação brasileira/americana)
                        df_completo[sel_col_val] = df_completo[sel_col_val].astype(str).str.replace(r'[R$\s]', '',
                                                                                                    regex=True)

                        def formatar_valor_pt_br(x):
                            if ',' in x:
                                x = x.replace('.', '').replace(',', '.')
                            return x

                        df_completo[sel_col_val] = df_completo[sel_col_val].apply(formatar_valor_pt_br)
                        df_completo[sel_col_val] = pd.to_numeric(df_completo[sel_col_val], errors='coerce')

                        # Descarta linhas onde o valor de conversão falhou ou é zero
                        df_completo = df_completo.dropna(subset=[sel_col_val])
                        df_completo = df_completo[df_completo[sel_col_val] != 0]

                        base_aprendizado = buscar_base_aprendizado(st.session_state.get('user_id'))

                        # Baixa os dados existentes do banco para checar duplicidade em memória de forma ultra veloz
                        df_existente = carregar_dados(usuario_atual)
                        if not df_existente.empty:
                            df_existente['data_str'] = pd.to_datetime(df_existente['data']).dt.strftime('%Y-%m-%d')
                            # Criamos um set de chaves únicas: (data, valor, descricao_limpa) para verificação rápida
                            chaves_existentes = set(
                                zip(
                                    df_existente['data_str'],
                                    df_existente['valor'].round(2),
                                    df_existente['descricao'].astype(str).str.strip().str.lower()
                                )
                            )
                        else:
                            chaves_existentes = set()

                        transacoes_pre_analisadas = []

                        for _, row in df_completo.iterrows():
                            descricao_original = str(row[sel_col_desc]).strip()
                            valor_original = float(row[sel_col_val])
                            data_original = str(row[sel_col_data])

                            # Ignora se data for inválida
                            if pd.isna(data_original) or data_original == 'NaT':
                                continue

                            tipo_calculado = "Ganho" if valor_original > 0 else "Gasto"

                            # Verificação de duplicados baseada em Data, Valor e Descrição exata
                            chave_atual = (data_original, round(valor_original, 2), descricao_original.lower())
                            duplicado = chave_atual in chaves_existentes

                            sugestao = sugerir_categoria(descricao_original, base_aprendizado)

                            # Força a subcategoria para "Padrão" se a inteligência sugerir vazio para um Ganho
                            subcat_sugerida = sugestao["subcategoria"] if tipo_calculado == "Gasto" else "Padrão"

                            transacoes_pre_analisadas.append({
                                "Importar": not duplicado,  # Pré-desmarca os duplicados da importação automática
                                "Status": "⚠️ Já Existe (Duplicado)" if duplicado else "✨ Novo",
                                "Data": data_original,
                                "Descrição": descricao_original,
                                "Valor (R$)": valor_original,
                                "Tipo": tipo_calculado,
                                "Grupo": sugestao["grupo"],
                                "Subgrupo": sugestao["subgrupo"],
                                "Subcategoria": subcat_sugerida
                            })

                        # Salva permanentemente no state para não sumir no Rerun do data_editor
                        st.session_state.df_importacao_previa = pd.DataFrame(transacoes_pre_analisadas)
                        st.session_state.import_concluida = True
                        st.rerun()

                except Exception as e:
                    st.error(f"Erro ao analisar arquivo CSV: {e}")

            # RENDERIZAÇÃO DA TABELA DE REVISÃO PERSISTIDA NA SESSÃO
            if st.session_state.get("import_concluida") and "df_importacao_previa" in st.session_state:
                df_atual = st.session_state.df_importacao_previa.copy()

                # BLINDAGEM ANTI-KEYERROR: Garante que as colunas críticas existam no DataFrame antes do processamento
                if 'Status' not in df_atual.columns:
                    df_atual['Status'] = "✨ Novo"
                if 'Importar' not in df_atual.columns:
                    df_atual['Importar'] = True

                # KPI de Resumo visual usando as colunas blindadas
                total_registros = len(df_atual)
                total_novos = len(df_atual[df_atual['Status'] == "✨ Novo"])
                total_duplicados = len(df_atual[df_atual['Status'] != "✨ Novo"])

                st.markdown("---")
                st.subheader("📝 Revise e Ajuste as Categorizações Sugeridas")

                m1, m2, m3 = st.columns(3)
                m1.metric("Total no Extrato", f"{total_registros} itens")
                m2.metric("Lançamentos Novos", f"{total_novos} novos", delta="Prontos", delta_color="normal")
                m3.metric("Possíveis Duplicados", f"{total_duplicados} detectados", delta="Pré-desmarcados",
                          delta_color="inverse")

                st.info(
                    "💡 Linhas marcadas como 'Já Existe (Duplicado)' vêm desmarcadas por padrão. Ative a caixa se quiser forçar o lançamento.")

                # Listas de opções globais para preencher o grid interativo
                grupos_cadastrados = sorted(list(df_cats['grupo'].unique()))
                subgrupos_cadastrados = sorted(list(df_cats['subgrupo'].unique()))
                subcat_cadastradas = sorted(list(df_cats['subcategoria'].unique()))
                if "Padrão" not in subcat_cadastradas: subcat_cadastradas.append("Padrão")

                # Data Editor interativo
                df_ajustado = st.data_editor(
                    df_atual,
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "Importar": st.column_config.CheckboxColumn("Importar?", help="Selecione as que deseja salvar"),
                        "Status": st.column_config.TextColumn("Status", disabled=True),
                        "Data": st.column_config.TextColumn("Data", disabled=True),
                        "Descrição": st.column_config.TextColumn("Descrição", disabled=True),
                        "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", disabled=True, format="%.2f"),
                        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Ganho"], width="small"),
                        "Grupo": st.column_config.SelectboxColumn("Grupo", options=grupos_cadastrados, required=False),
                        "Subgrupo": st.column_config.SelectboxColumn("Subgrupo", options=subgrupos_cadastrados,
                                                                     required=False),
                        "Subcategoria": st.column_config.SelectboxColumn("Subcategoria", options=subcat_cadastradas,
                                                                         required=False)
                    },
                    key="editor_importacao_final"
                )

                # Mantém o dataframe editado sincronizado na sessão
                st.session_state.df_importacao_previa = df_ajustado

                col_b1, col_b2 = st.columns(2)

                if col_b1.button("💾 Confirmar Lançamentos no Banco", type="primary", width='stretch'):
                    # Filtra apenas o que o usuário escolheu importar na coluna "Importar"
                    if "Importar" in df_ajustado.columns:
                        df_para_salvar = df_ajustado[df_ajustado["Importar"] == True]
                    else:
                        df_para_salvar = df_ajustado.copy()

                    if df_para_salvar.empty:
                        st.warning("Nenhuma transação marcada para importação.")
                    else:
                        sucesso_importacao = True
                        transacoes_para_salvar = []
                        validacao_ok = True

                        # VALIDAÇÃO DE INTEGRIDADE FLEXÍVEL (SUPORTA CAMPOS EM BRANCO E "A CATEGORIZAR")
                        for idx, row in df_para_salvar.iterrows():
                            # Limpa os textos para checar se estão vazios ou com "A Categorizar"
                            g_str = "" if pd.isna(row["Grupo"]) else str(row["Grupo"]).strip()
                            sg_str = "" if pd.isna(row["Subgrupo"]) else str(row["Subgrupo"]).strip()
                            cat_str = "" if pd.isna(row["Subcategoria"]) else str(row["Subcategoria"]).strip()

                            # Pula a validação se estiver em branco OU se for "A Categorizar"
                            ignorar_grupo = g_str in ["", "A Categorizar", "None"]
                            ignorar_subgrupo = sg_str in ["", "A Categorizar", "None"]
                            ignorar_subcat = cat_str in ["", "A Categorizar", "None"]

                            if ignorar_grupo or ignorar_subgrupo or (row["Tipo"] == "Gasto" and ignorar_subcat):
                                continue

                            if row["Tipo"] == "Ganho":
                                # Se for Ganho, valida se a hierarquia Pai (Grupo e Subgrupo) existe junta
                                relacao_valida = df_cats[
                                    (df_cats['grupo'] == row["Grupo"]) &
                                    (df_cats['subgrupo'] == row["Subgrupo"])
                                    ]
                                msg_erro = f"A combinação Grupo '{row['Grupo']}' ➔ Subgrupo '{row['Subgrupo']}' não existe!"
                            else:
                                # Se for Gasto, exige correspondência rígida de 3 níveis
                                relacao_valida = df_cats[
                                    (df_cats['grupo'] == row["Grupo"]) &
                                    (df_cats['subgrupo'] == row["Subgrupo"]) &
                                    (df_cats['subcategoria'] == row["Subcategoria"])
                                    ]
                                msg_erro = f"A combinação Grupo '{row['Grupo']}' ➔ Subgrupo '{row['Subgrupo']}' ➔ Subcategoria '{row['Subcategoria']}' não existe!"

                            if relacao_valida.empty:
                                st.error(
                                    f"❌ Erro na linha de Descrição '{row['Descrição']}': {msg_erro} Verifique suas configurações.")
                                validacao_ok = False
                                break

                        if validacao_ok:
                            with st.spinner("Inserindo transações no banco..."):
                                for _, row in df_para_salvar.iterrows():
                                    valor_real = -abs(row["Valor (R$)"]) if row["Tipo"] == "Gasto" else abs(
                                        row["Valor (R$)"])

                                    # --- TRATAMENTO DOS CAMPOS ANTES DE MANDAR PRO BANCO ---
                                    # Se for vazio ou "A Categorizar", envia None (NULL no Supabase)
                                    g_envio = None if (pd.isna(row["Grupo"]) or str(row["Grupo"]).strip() in ["",
                                                                                                              "A Categorizar"]) else \
                                    row["Grupo"]
                                    sg_envio = None if (pd.isna(row["Subgrupo"]) or str(row["Subgrupo"]).strip() in ["",
                                                                                                                     "A Categorizar"]) else \
                                    row["Subgrupo"]

                                    if row["Tipo"] == "Gasto":
                                        subcat_envio = None if (pd.isna(row["Subcategoria"]) or str(
                                            row["Subcategoria"]).strip() in ["", "A Categorizar"]) else row[
                                            "Subcategoria"]
                                    else:
                                        subcat_envio = "Padrão"

                                    # Monta o dicionário usando os valores já limpos/tratados acima
                                    dados_lanc = {
                                        "valor": valor_real,
                                        "tipo": row["Tipo"],
                                        "grupo": g_envio,
                                        "subgrupo": sg_envio,
                                        "subcategoria": subcat_envio,
                                        "conta": import_conta_sel,
                                        "data": row["Data"],
                                        "descricao": row["Descrição"],
                                        "username": usuario_atual
                                    }

                                    if not inserir_transacao(dados_lanc):
                                        sucesso_importacao = False
                                    else:
                                        transacoes_para_salvar.append(dados_lanc)

                            if sucesso_importacao:
                                # Ensina a IA com os dados revisados e inseridos com sucesso
                                treinar_sistema(transacoes_para_salvar, None)

                                st.success(
                                    f"✅ Sucesso! {len(transacoes_para_salvar)} lançamentos importados e a inteligência foi treinada.")

                                # Limpa os estados da sessão para voltar ao layout inicial limpo de forma segura
                                st.session_state.pop("df_importacao_previa", None)
                                st.session_state.pop("import_concluida", None)
                                st.rerun()
                            else:
                                st.error("Houve um erro ao processar alguns registros no Supabase.")

                if col_b2.button("❌ Cancelar Importação", width='stretch'):
                    st.session_state.pop("df_importacao_previa", None)
                    st.session_state.pop("import_concluida", None)
                    st.rerun()
        else:
            st.info("Você não tem permissões de edição para importar arquivos.")

    # --- SEÇÃO 2: VISUALIZAÇÃO E EDIÇÃO ---
    st.divider()
    st.subheader("🔍 Lançamentos Recentes")

    df_lista = carregar_dados(usuario_atual)

    if not df_lista.empty:
        df_display = df_lista.copy()
        df_display['data'] = pd.to_datetime(df_display['data'])

        df_display['mes_ano'] = df_display['data'].dt.strftime('%m/%Y')
        meses_disp = sorted(df_display['mes_ano'].unique(), reverse=True)
        mes_filtro = st.selectbox("📅 Filtrar por Mês/Ano", ["Todos"] + meses_disp, key="filtro_mes_extrato")

        if mes_filtro != "Todos":
            df_display = df_display[df_display['mes_ano'] == mes_filtro]

        df_display = df_display.sort_values(by='data', ascending=False)

        # ----------------------------------------------------
        # TABELA EDITÁVEL COM APRENDIZADO DA IA INTEGRADO
        # ----------------------------------------------------
        st.write("💡 Ajuste a classificação diretamente na tabela para re-treinar a IA automaticamente ao salvar:")

        # Coleta as opções de classificação disponíveis para carregar nos selects da tabela
        grupos_cadastrados = sorted(list(df_cats['grupo'].unique()))
        subgrupos_cadastrados = sorted(list(df_cats['subgrupo'].unique()))
        subcat_cadastradas = sorted(list(df_cats['subcategoria'].unique()))
        if "Padrão" not in subcat_cadastradas: subcat_cadastradas.append("Padrão")

        # Mantemos apenas as colunas que nos interessam na edição
        colunas_vistas = ['id', 'data', 'tipo', 'grupo', 'subgrupo', 'subcategoria', 'conta', 'valor', 'descricao']
        df_editavel = df_display[colunas_vistas].copy()

        # Garante a formatação de data para string amigável
        df_editavel['data'] = df_editavel['data'].dt.strftime('%Y-%m-%d')
        df_editavel['subcategoria'] = df_editavel['subcategoria'].fillna("Padrão")

        # Exibe o data editor
        df_ajustado_recentes = st.data_editor(
            df_editavel,
            width='stretch',
            hide_index=True,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "data": st.column_config.TextColumn("Data", disabled=True),
                "tipo": st.column_config.TextColumn("Tipo", disabled=True),
                "conta": st.column_config.TextColumn("Conta", disabled=True),
                "valor": st.column_config.NumberColumn("Valor (R$)", disabled=True, format="%.2f"),
                "descricao": st.column_config.TextColumn("Descrição", disabled=True),
                "grupo": st.column_config.SelectboxColumn("Grupo", options=grupos_cadastrados, required=True),
                "subgrupo": st.column_config.SelectboxColumn("Subgrupo", options=subgrupos_cadastrados, required=True),
                "subcategoria": st.column_config.SelectboxColumn("Subcategoria", options=subcat_cadastradas,
                                                                 required=True),
            },
            key="editor_recentes_automatico"
        )

        # ==========================================
        # SALVAMENTO PARCIAL DA IA E 2 NÍVEIS ADAPTADO
        # ==========================================
        if st.button("💾 Salvar Alterações e Treinar IA", type="primary", width='stretch'):
            # 1. Identifica apenas as linhas que foram de fato alteradas usando busca por ID exclusivo
            linhas_alteradas = []

            for _, row_ajustada in df_ajustado_recentes.iterrows():
                # Busca a linha original correspondente pelo 'id' único da transação
                id_transacao = row_ajustada['id']
                row_original_list = df_editavel[df_editavel['id'] == id_transacao]

                if row_original_list.empty:
                    continue

                row_original = row_original_list.iloc[0]

                # Se houve mudança no Grupo, Subgrupo ou Subcategoria
                if (row_ajustada['grupo'] != row_original['grupo'] or
                        row_ajustada['subgrupo'] != row_original['subgrupo'] or
                        row_ajustada['subcategoria'] != row_original['subcategoria']):

                    # Ignoramos se o usuário "limpou" ou deixou como "A Categorizar" / em branco nas alteradas
                    if (pd.isna(row_ajustada['grupo']) or str(row_ajustada['grupo']).strip() in ["", "A Categorizar"]):
                        continue

                    linhas_alteradas.append(row_ajustada)

            if len(linhas_alteradas) == 0:
                st.info("Nenhuma classificação alterada foi detectada para salvamento.")
            else:
                sucesso_update = True
                dados_para_treino = []
                validacao_ok = True

                # 2. VALIDAÇÃO ADAPTATIVA DE COERÊNCIA APENAS PARA AS LINHAS ALTERADAS
                for row in linhas_alteradas:
                    # Se for transferência, não validamos contra a tabela de categorias comuns
                    if row.get("tipo") == "Transferência":
                        continue

                    if row["tipo"] == "Ganho":
                        # Validação flexível para receitas (2 níveis)
                        relacao_valida = df_cats[
                            (df_cats['grupo'] == row["grupo"]) &
                            (df_cats['subgrupo'] == row["subgrupo"])
                            ]
                        msg_erro = f"A combinação Grupo: {row['grupo']} ➔ Subgrupo: {row['subgrupo']} não existe."
                    else:
                        # Validação rígida para despesas (3 níveis)
                        relacao_valida = df_cats[
                            (df_cats['grupo'] == row["grupo"]) &
                            (df_cats['subgrupo'] == row["subgrupo"]) &
                            (df_cats['subcategoria'] == row["subcategoria"])
                            ]
                        msg_erro = f"A combinação Grupo: {row['grupo']} ➔ Subgrupo: {row['subgrupo']} ➔ Subcategoria: {row['subcategoria']} não é válida."

                    if relacao_valida.empty:
                        st.error(f"❌ Erro em '{row['descricao']}': {msg_erro} Corrija antes de prosseguir.")
                        validacao_ok = False
                        break

                # 3. EFETUA O SALVAMENTO PARCIAL NO BANCO E TREINA A IA
                if validacao_ok:
                    with st.spinner(f"Atualizando {len(linhas_alteradas)} registros e alimentando o cérebro da IA..."):
                        from database import supabase

                        for row in linhas_alteradas:
                            # Atualiza no Supabase usando o ID único da transação
                            res = supabase.table("transacoes").update({
                                "grupo": row["grupo"],
                                "subgrupo": row["subgrupo"],
                                "subcategoria": row["subcategoria"] if row["tipo"] == "Gasto" else "Padrão"
                            }).eq("id", row["id"]).eq("username", usuario_atual).execute()

                            if res.data:
                                # Prepara dado estruturado para re-treinar o modelo
                                dados_para_treino.append({
                                    "descricao": row["descricao"],
                                    "grupo": row["grupo"],
                                    "subgrupo": row["subgrupo"],
                                    "subcategoria": row["subcategoria"] if row["tipo"] == "Gasto" else "Padrão"
                                })
                            else:
                                sucesso_update = False

                    if sucesso_update:
                        # Alimenta a Inteligência Artificial com o lote que foi salvo
                        # ✅ CORREÇÃO: Tenta pegar o UUID do usuário de várias chaves comuns da sessão
                        treinar_sistema(dados_para_treino, None)
                        st.success(
                            f"✅ {len(dados_para_treino)} lançamentos atualizados e Inteligência Artificial re-treinada com sucesso!")
                        st.rerun()
                    else:
                        st.error("Ocorreu um problema ao salvar algumas atualizações no Supabase.")
        # ==========================================

        # --- SEÇÃO EXPANDER DE EDIÇÃO/EXCLUSÃO AVANÇADA COM HIERARQUIA INTELIGENTE ---
        with st.expander("🛠️ Outras Opções (Alterar Valor/Data/Hierarquia ou Excluir Lançamento)"):
            st.write("Copie o ID da tabela acima para fazer alterações estruturais ou deletar o registro.")
            id_para_editar = st.text_input("Cole o ID do lançamento:", key="input_id_edit")

            if id_para_editar:
                row_sel = df_lista[df_lista['id'].astype(str) == str(id_para_editar)]

                if not row_sel.empty:
                    row = row_sel.iloc[0]
                    st.info(f"📍 Selecionado: {row['descricao']} | R$ {abs(row['valor']):,.2f}")

                    with st.form("form_edicao_supabase"):
                        c_ed1, c_ed2, c_ed3 = st.columns([1, 1, 1])

                        nova_data_ed = c_ed1.date_input("Nova Data", value=pd.to_datetime(row['data']))

                        contas_lista = sorted(list(df_contas['nome'].unique()))
                        idx_conta = contas_lista.index(row['conta']) if row['conta'] in contas_lista else 0
                        nova_conta_ed = c_ed2.selectbox("Nova Conta", contas_lista, index=idx_conta)

                        novo_valor_ed = c_ed3.number_input("Novo Valor (R$)", value=abs(float(row['valor'])), step=0.01)

                        nova_desc_ed = st.text_input("Nova Descrição", value=str(row['descricao'] or ""))

                        # HIERARQUIA INTEGRALMENTE FILTRADA NA EDICÃO INDIVIDUAL
                        st.markdown("##### 📌 Atualizar Classificação da Categoria")
                        c_cat1, c_cat2, c_cat3 = st.columns(3)

                        with c_cat1:
                            lista_g = sorted(df_cats['grupo'].unique())
                            idx_g = list(lista_g).index(row['grupo']) if row['grupo'] in lista_g else 0
                            novo_grupo = st.selectbox("Grupo", lista_g, index=idx_g, key="edit_grupo_form")

                        with c_cat2:
                            # FILTRO DINÂMICO 1: Subgrupos disponíveis apenas para o Grupo selecionado acima
                            opts_sub = df_cats[df_cats['grupo'] == novo_grupo]['subgrupo'].unique()
                            opts_sub_sorted = sorted(opts_sub) if len(opts_sub) > 0 else ["Padrão"]
                            idx_sub = list(opts_sub_sorted).index(row['subgrupo']) if row[
                                                                                          'subgrupo'] in opts_sub_sorted else 0
                            novo_subgrupo = st.selectbox("Subgrupo", opts_sub_sorted, index=idx_sub,
                                                         key="edit_subgrupo_form")

                        with c_cat3:
                            # FILTRO DINÂMICO 2: Subcategorias operando sob a regra condicional de tipo
                            if row['tipo'] == "Ganho":
                                nova_subcategoria = "Padrão"
                                st.text_input("Subcategoria", value="Padrão", disabled=True,
                                              key="edit_subcat_disabled_form")
                            else:
                                filtro_sub_edit = (df_cats['grupo'] == novo_grupo) & (
                                            df_cats['subgrupo'] == novo_subgrupo)
                                opts_subcat = df_cats[filtro_sub_edit]['subcategoria'].unique()
                                opts_subcat_sorted = sorted(opts_subcat) if len(opts_subcat) > 0 else ["Padrão"]
                                idx_subcat = list(opts_subcat_sorted).index(row['subcategoria']) if row[
                                                                                                        'subcategoria'] in opts_subcat_sorted else 0
                                nova_subcategoria = st.selectbox("Subcategoria", opts_subcat_sorted, index=idx_subcat,
                                                                 key="edit_subcat_form")

                        btn_save, btn_del = st.columns(2)

                        if btn_save.form_submit_button("💾 Salvar Alterações Estruturais", type="primary",
                                                       width="stretch"):
                            if row['tipo'] == "Transferência":
                                valor_final_ed = -novo_valor_ed if row['valor'] < 0 else novo_valor_ed
                            else:
                                valor_final_ed = -novo_valor_ed if row['tipo'] == "Gasto" else novo_valor_ed

                            from database import supabase
                            res = supabase.table("transacoes").update({
                                "valor": valor_final_ed,
                                "data": str(nova_data_ed),
                                "conta": nova_conta_ed,
                                "descricao": nova_desc_ed,
                                "grupo": novo_grupo,
                                "subgrupo": novo_subgrupo,
                                "subcategoria": nova_subcategoria if row['tipo'] == "Gasto" else "Padrão"
                            }).eq("id", id_para_editar).eq("username", usuario_atual).execute()

                            if res.data:
                                dados_treino_update = {
                                    "descricao": nova_desc_ed,
                                    "grupo": novo_grupo,
                                    "subgrupo": novo_subgrupo,
                                    "subcategoria": nova_subcategoria if row['tipo'] == "Gasto" else "Padrão"
                                }
                                treinar_sistema([dados_treino_update], None)

                                st.success("✅ Atualizado com sucesso!")
                                st.rerun()

                        if btn_del.form_submit_button("🗑️ Excluir Registro", width="stretch"):
                            from database import supabase

                            if row.get('id_agrupador'):
                                res = supabase.table("transacoes").delete().eq("id_agrupador", row['id_agrupador']).eq(
                                    "username", usuario_atual).execute()
                                st.warning("⚠️ Grupo de lançamentos removido!")
                            else:
                                res = supabase.table("transacoes").delete().eq("id", id_para_editar).eq("username",
                                                                                                        usuario_atual).execute()
                                m = st.warning("⚠️ Lançamento removido!")

                            st.rerun()
                else:
                    st.error("❌ ID não encontrado ou acesso negado.")
    else:
        st.info(f"💡 {usuario_atual}, ainda não há lançamentos. Use o formulário acima para começar!")