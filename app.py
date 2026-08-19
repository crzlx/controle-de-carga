import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import urllib.parse
from datetime import datetime
import google.generativeai as genai

# Configuração da Página
st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="centered")

def conectar_planilha():
    escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    cred_dict = json.loads(st.secrets["google_credentials"])
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(cred_dict, escopo)
    cliente = gspread.authorize(credenciais)
    return cliente.open_by_url("https://docs.google.com/spreadsheets/d/1yHThW-nbcwxCcNTnb66PP1YHbHpCE9_ep3DC33-OZs4/edit?usp=sharing")

def obter_dados_gerais():
    planilha = conectar_planilha()
    dados = []
    transportadoras = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]
    
    for transp in transportadoras:
        try:
            aba = planilha.worksheet(transp)
            linhas = aba.get_all_values()
            for l in linhas[1:]:
                if len(l) >= 2 and str(l[1]).strip() != "":
                    dados.append({
                        "Transportadora": transp,
                        "QTD": l[0].strip() if len(l) > 0 else "-",
                        "Nota": str(l[1]).strip(),
                        "Data_Emissao": l[2].strip() if len(l) > 2 else "-",
                        "Data_Coleta": l[3].strip() if len(l) > 3 else ""
                    })
        except:
            pass
    return dados

st.title("🚚 Gestão de Coletas")

transportadoras = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]

# Adicionamos a 4ª Aba para a Inteligência Artificial
aba1, aba2, aba3, aba4 = st.tabs([
    "📦 Movimentação", "📊 Painel da Filial", "🔍 Consulta Rápida", "🤖 Assistente IA"
])

# ==========================================
# ABA 1: MOVIMENTAÇÃO (Lançar e Baixar)
# ==========================================
with aba1:
    st.header("📝 Lançar Nova Solicitação")
    st.markdown("Registre a nota que acabou de ser separada no estoque.")
    
    with st.form("form_nova", clear_on_submit=True):
        transp_nova = st.selectbox("Transportadora", transportadoras, key="t1")
        col1, col2 = st.columns(2)
        with col1:
            qtd = st.number_input("QTD", min_value=1, step=1)
            data_emissao = st.date_input("Data da Solicitação", format="DD/MM/YYYY")
        with col2:
            nota_nova = st.text_input("Nota (Nº)")
            
        enviar_nova = st.form_submit_button("Registrar Nota", use_container_width=True)
        
        if enviar_nova:
            if nota_nova == "":
                st.warning("⚠️ Preencha o número da Nota.")
            else:
                try:
                    planilha = conectar_planilha()
                    aba_sel = planilha.worksheet(transp_nova)
                    data_formatada = data_emissao.strftime("%d/%m/%Y")
                    
                    aba_sel.append_row([qtd, nota_nova, data_formatada, ""])
                    st.success(f"✅ Nota {nota_nova} registrada na aba {transp_nova}!")
                    
                    if transp_nova == "FL":
                        st.info("💻 Transportadora FL selecionada. Envie o aviso manualmente pelo **Microsoft Teams**!")
                    else:
                        telefones = {
                            "JARBAS": "5522999445773",
                            "TRANSCHERRER": "5527992527567",
                            "GENEROSO": "5522992092727"
                        }
                        numero_destino = telefones.get(transp_nova, "")
                        texto_msg = f"Olá, equipe {transp_nova}! Temos uma mercadoria separada para coleta na Speedmax. 📦\n\n*Nota:* {nota_nova}\n*Volumes:* {qtd}\n\nFicamos no aguardo!"
                        texto_codificado = urllib.parse.quote(texto_msg)
                        link_wpp = f"https://wa.me/{numero_destino}?text={texto_codificado}"
                        st.link_button(f"📱 Enviar aviso no WhatsApp ({transp_nova})", link_wpp, use_container_width=True)
                        
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    st.markdown("---")
    
    st.header("✅ Confirmar Coleta")
    st.markdown("Dê a baixa quando o caminhão vier levar a mercadoria.")
    
    with st.form("form_baixa", clear_on_submit=True):
        transp_baixa = st.selectbox("Transportadora (Baixa)", transportadoras, key="t2")
        col3, col4 = st.columns(2)
        with col3:
            nota_baixa = st.text_input("Nota (Nº) para baixar")
        with col4:
            data_coleta = st.date_input("Data da Coleta Real", format="DD/MM/YYYY")
            
        enviar_baixa = st.form_submit_button("Confirmar Baixa", use_container_width=True)
        
        if enviar_baixa:
            if nota_baixa == "":
                st.warning("⚠️ Preencha a Nota.")
            else:
                try:
                    planilha = conectar_planilha()
                    aba_sel = planilha.worksheet(transp_baixa)
                    celula = aba_sel.find(nota_baixa)
                    coleta_formatada = data_coleta.strftime("%d/%m/%Y")
                    aba_sel.update_cell(celula.row, 4, coleta_formatada)
                    st.success(f"✅ Baixa da nota {nota_baixa} confirmada para {coleta_formatada}!")
                except gspread.CellNotFound:
                    st.error(f"❌ Nota {nota_baixa} não encontrada na {transp_baixa}.")
                except Exception as e:
                    st.error(f"Erro: {e}")

# ==========================================
# ABA 2: PAINEL DA FILIAL
# ==========================================
with aba2:
    st.markdown("### 📊 Visão Geral do Estoque")
    
    if st.button("🔄 Atualizar Painel e Gerar Relatório", use_container_width=True):
        with st.spinner("Analisando as planilhas..."):
            dados = obter_dados_gerais()
            hoje = datetime.now().strftime("%d/%m/%Y")
            
            lancadas_hoje = [d for d in dados if d["Data_Emissao"] == hoje]
            coletadas_hoje = [d for d in dados if d["Data_Coleta"] == hoje]
            pendentes_lista = [d for d in dados if d["Data_Coleta"] == ""]
            
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Separadas Hoje", len(lancadas_hoje))
            c2.metric("✅ Coletadas Hoje", len(coletadas_hoje))
            c3.metric("⏳ Paradas na Filial", len(pendentes_lista))
            
            st.markdown("---")
            st.subheader("🚛 Mercadorias Aguardando Coleta")
            if pendentes_lista:
                st.warning(f"Temos **{len(pendentes_lista)}** notas no galpão aguardando as transportadoras.")
                st.dataframe(pendentes_lista, use_container_width=True, hide_index=True)
            else:
                st.success("🎉 Nenhuma pendência! O estoque está 100% limpo.")

            st.markdown("---")
            st.subheader("📋 Resumo do Turno (Copiar e Colar)")
            
            texto_relatorio = f"📊 *FECHAMENTO DE COLETAS - {hoje}*\n\n"
            texto_relatorio += f"✅ *COLETAS FINALIZADAS HOJE:* {len(coletadas_hoje)} nota(s)\n"
            
            if coletadas_hoje:
                agrupado_coletadas = {}
                for d in coletadas_hoje:
                    t = d["Transportadora"]
                    agrupado_coletadas.setdefault(t, []).append(f"Nº {d['Nota']} ({d['QTD']} vol)")
                
                for transp, notas in agrupado_coletadas.items():
                    texto_relatorio += f"\n🚛 *{transp}* ({len(notas)}):\n"
                    texto_relatorio += f"   ↳ {', '.join(notas)}\n"
            else:
                texto_relatorio += "Nenhuma coleta registrada hoje.\n"
                
            texto_relatorio += "\n" + "-"*30 + "\n\n"
            
            texto_relatorio += f"⏳ *PENDÊNCIAS NA FILIAL:* {len(pendentes_lista)} nota(s) aguardando\n"
            if pendentes_lista:
                agrupado_pendentes = {}
                for d in pendentes_lista:
                    t = d["Transportadora"]
                    agrupado_pendentes.setdefault(t, []).append(f"Nº {d['Nota']} ({d['QTD']} vol - req: {d['Data_Emissao']})")
                
                for transp, notas in agrupado_pendentes.items():
                    texto_relatorio += f"\n⚠️ *{transp}* ({len(notas)}):\n"
                    for n in notas:
                        texto_relatorio += f"   ↳ {n}\n"
            else:
                texto_relatorio += "Nenhuma pendência! Galpão limpo. 🎉\n"
            
            st.text_area("Texto Copiável:", value=texto_relatorio, height=350)

# ==========================================
# ABA 3: CONSULTA RÁPIDA
# ==========================================
with aba3:
    st.markdown("### 🔍 Pesquisa de Status")
    nota_busca = st.text_input("Digite o Número da Nota:")
    
    if st.button("Procurar Nota", use_container_width=True):
        if nota_busca:
            with st.spinner("Buscando no histórico..."):
                dados = obter_dados_gerais()
                encontradas = [d for d in dados if d["Nota"] == nota_busca.strip()]
                
                if encontradas:
                    for nota in encontradas:
                        status = "✅ Já Coletada" if nota["Data_Coleta"] != "" else "⏳ Aguardando no Galpão"
                        cor_status = "#d4edda" if nota["Data_Coleta"] != "" else "#fff3cd"
                        cor_texto = "#155724" if nota["Data_Coleta"] != "" else "#856404"
                        
                        st.markdown(f"""
                        <div style="background-color: {cor_status}; color: {cor_texto}; padding: 15px; border-radius: 10px; margin-top: 10px;">
                            <h4 style="margin-top:0;">Nota: {nota['Nota']}</h4>
                            <b>Status:</b> {status}<br>
                            <b>Transportadora:</b> {nota['Transportadora']}<br>
                            <b>QTD Volumes:</b> {nota['QTD']}<br>
                            <b>Solicitada em:</b> {nota['Data_Emissao']}<br>
                            <b>Coletada em:</b> {nota['Data_Coleta'] if nota['Data_Coleta'] != "" else "Ainda na filial"}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.error("❌ Esta nota não foi encontrada em nenhuma das planilhas.")

# ==========================================
# ABA 4: ASSISTENTE IA (NOVIDADE)
# ==========================================
with aba4:
    st.markdown("### 🤖 Assistente Logístico (IA)")
    st.markdown("Faça perguntas sobre as mercadorias, volumes parados, ou peça para a IA redigir e-mails para as transportadoras.")
    
    pergunta_usuario = st.text_area("O que você deseja saber ou fazer?", placeholder="Ex: Quantas notas o Jarbas tem pendente? ou Crie uma mensagem cobrando a FL sobre as notas atrasadas.")
    
    if st.button("Perguntar à IA", use_container_width=True):
        if pergunta_usuario:
            with st.spinner("A IA está processando as planilhas..."):
                try:
                    # Configura a chave do Gemini que você salvou
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    modelo = genai.GenerativeModel('gemini-1.5-flash')
                    
                    # Pega os dados atuais do estoque para a IA "ler"
                    dados_estoque = obter_dados_gerais()
                    hoje = datetime.now().strftime("%d/%m/%Y")
                    
                    # Cria a instrução de fundo para a IA
                    prompt = f"""
                    Você é um assistente logístico altamente eficiente que ajuda o administrador de um galpão.
                    Hoje é dia {hoje}. Seja direto, polido e profissional.
                    Aqui estão os dados em tempo real das planilhas de coleta (notas lançadas, pendentes, transportadoras):
                    {json.dumps(dados_estoque, ensure_ascii=False)}
                    
                    Use EXCLUSIVAMENTE esses dados para responder. Se a resposta não estiver nos dados, avise.
                    
                    Responda ao pedido do usuário de forma clara:
                    "{pergunta_usuario}"
                    """
                    
                    # Envia para o Gemini e pega a resposta
                    resposta = modelo.generate_content(prompt)
                    
                    st.success("Resposta gerada!")
                    st.markdown(f"> {resposta.text}")
                    
                except Exception as e:
                    st.error(f"Erro ao conectar com a Inteligência Artificial: Verifique se a chave API está correta nos Secrets. Detalhe técnico: {e}")
        else:
            st.warning("⚠️ Digite uma pergunta na caixa de texto antes de enviar.")
