import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import urllib.parse
from datetime import datetime
import google.generativeai as genai
import smtplib
from email.message import EmailMessage

# Configuração da Página
st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="centered")

# ==========================================
# FUNÇÃO DO ROBÔ DE E-MAILS
# ==========================================
def disparar_email_silencioso(transportadora, nota, qtd):
    try:
        remetente = st.secrets["EMAIL_REMETENTE"]
        senha = st.secrets["SENHA_EMAIL"]
        
        # LISTA OFICIAL DE E-MAILS (FL removida, pois usa o Teams)
        emails_destino = {
            "JARBAS": "adm.campos@italogrj.com.br",
            "TRANSCHERRER": "filial.campos@transcherrer.com.br, cidy.neves@transcherrer.com.br, filial.campos02@transcherrer.com.br",
            "GENEROSO": "Encarregado.cgo@generoso.com.br"
        }
        
        destinatario = emails_destino.get(transportadora)
        
        # O código só dispara se tiver um e-mail válido configurado
        if destinatario and "teste.com" not in destinatario.lower():
            msg = EmailMessage()
            msg['Subject'] = f"Nova Coleta Liberada - Speedmax (Nota: {nota})"
            msg['From'] = remetente
            msg['To'] = destinatario 
            
            corpo_email = f"""
Olá, equipe da {transportadora}!

Temos uma nova mercadoria separada e liberada para coleta na filial Speedmax.

DETALHES DA COLETA:
- Nota Fiscal: {nota}
- Quantidade de Volumes: {qtd}

Por favor, programem a coleta assim que possível.

Atenciosamente,
Logística Speedmax.
            """
            msg.set_content(corpo_email)
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(remetente, senha)
                smtp.send_message(msg)
                
            return True
        return False
    except Exception as e:
        return str(e)

# ==========================================
# FUNÇÕES DE BANCO DE DADOS
# ==========================================
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
                        "Data_Solicitacao": l[2].strip() if len(l) > 2 else "-",
                        "Data_Coleta": l[3].strip() if len(l) > 3 else "",
                        "Data_Emissao_Nota": l[4].strip() if len(l) > 4 else "-"
                    })
        except:
            pass
    return dados

# ==========================================
# MENU LATERAL (SIDEBAR) - ALESSANDRO IA
# ==========================================
with st.sidebar:
    st.header("🤖 Alessandro IA")
    st.markdown("Pergunte sobre as mercadorias ou peça para eu redigir avisos especiais.")
    
    pergunta_usuario = st.text_area("O que você precisa?", placeholder="Ex: Quantas notas o Jarbas tem pendente?")
    
    if st.button("Perguntar ao Alessandro", use_container_width=True):
        if pergunta_usuario:
            with st.spinner("O Alessandro está analisando o estoque..."):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    modelo = genai.GenerativeModel('gemini-3.6-flash')
                    
                    dados_estoque = obter_dados_gerais()
                    hoje = datetime.now().strftime("%d/%m/%Y")
                    
                    dados_filtrados = [d for d in dados_estoque if d["Data_Coleta"] == "" or d["Data_Coleta"] == hoje or d["Data_Solicitacao"] == hoje]
                    
                    prompt = f"""
                    O seu nome é Alessandro IA.
                    Você é um assistente logístico altamente eficiente que ajuda o administrador de um galpão.
                    Hoje é dia {hoje}. Seja direto, polido e profissional. Pode se apresentar ou agir de acordo com o seu nome quando for pertinente.
                    
                    Aqui estão os dados resumidos das notas pendentes na filial e das operações de hoje:
                    {json.dumps(dados_filtrados, ensure_ascii=False)}
                    
                    Use EXCLUSIVAMENTE esses dados para responder. Se a resposta exigir uma nota antiga que não está aqui, avise que você só tem acesso às notas pendentes e do dia de hoje para economizar processamento.
                    
                    Responda ao pedido do usuário de forma clara:
                    "{pergunta_usuario}"
                    """
                    
                    resposta = modelo.generate_content(prompt)
                    st.success("✅ Resposta do Alessandro:")
                    st.markdown(f"> {resposta.text}")
                    
                except Exception as e:
                    st.error(f"❌ Erro na conexão do Alessandro. Detalhe: {e}")
        else:
            st.warning("⚠️ Digite uma pergunta primeiro.")

# ==========================================
# CORPO PRINCIPAL DO APLICATIVO
# ==========================================
st.title("🚚 Gestão de Coletas")

transportadoras = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]

aba1, aba2, aba3 = st.tabs([
    "📦 Movimentação", "📊 Painel da Filial", "🔍 Consulta Rápida"
])

# ==========================================
# ABA 1: MOVIMENTAÇÃO
# ==========================================
with aba1:
    st.header("📝 Lançar Nova Solicitação")
    st.markdown("Registre a nota que acabou de ser separada no estoque.")
    
    with st.form("form_nova", clear_on_submit=True):
        transp_nova = st.selectbox("Transportadora", transportadoras, key="t1")
        col1, col2 = st.columns(2)
        with col1:
            qtd = st.number_input("QTD", min_value=1, step=1)
            data_solicitacao = st.date_input("Data da Solicitação", format="DD/MM/YYYY")
        with col2:
            nota_nova = st.text_input("Nota (Nº)")
            data_emissao = st.date_input("Data de Emissão da Nota", format="DD/MM/YYYY")
            
        enviar_nova = st.form_submit_button("Registrar Nota", use_container_width=True)
        
        if enviar_nova:
            if nota_nova == "":
                st.warning("⚠️ Preencha o número da Nota.")
            else:
                try:
                    planilha = conectar_planilha()
                    aba_sel = planilha.worksheet(transp_nova)
                    
                    formatada_solicitacao = data_solicitacao.strftime("%d/%m/%Y")
                    formatada_emissao = data_emissao.strftime("%d/%m/%Y")
                    
                    aba_sel.append_row([qtd, nota_nova, formatada_solicitacao, "", formatada_emissao])
                    st.success(f"✅ Nota {nota_nova} registrada com sucesso na aba {transp_nova}!")
                    
                    # LOGICA NOVA: Bloqueia e-mail para a FL e avisa sobre o Teams
                    if transp_nova == "FL":
                        st.info("💻 **ATENÇÃO:** O aviso para a transportadora FL deve ser enviado manualmente pelo **Microsoft Teams**!")
                    else:
                        resultado_email = disparar_email_silencioso(transp_nova, nota_nova, qtd)
                        if resultado_email is True:
                            st.info(f"📧 E-mail enviado automaticamente para a equipe da {transp_nova}!")
                        elif resultado_email is False:
                            st.warning(f"⚠️ Nota registrada, mas o e-mail não foi enviado porque o endereço oficial da {transp_nova} ainda não foi configurado.")
                        else:
                            st.error(f"❌ Erro ao enviar o e-mail: {resultado_email}")
                        
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    st.markdown("---")
    
    # ==========================================
    # SISTEMA DE BAIXA INTELIGENTE
    # ==========================================
    st.header("✅ Confirmar Coleta em Lote")
    st.markdown("Selecione o caminhão e marque as notas que ele está levando hoje.")
    
    transp_baixa = st.selectbox("Transportadora (Baixa)", transportadoras, key="t2")
    
    dados_totais = obter_dados_gerais()
    pendentes_transp = [d for d in dados_totais if d["Transportadora"] == transp_baixa and d["Data_Coleta"] == ""]
    
    if pendentes_transp:
        with st.form("form_baixa"):
            st.markdown(f"📦 **Notas pendentes na filial ({transp_baixa}):**")
            
            checkboxes_notas = {}
            for p in pendentes_transp:
                label = f"Nº {p['Nota']} — {p['QTD']} volumes (Solicitada em: {p['Data_Solicitacao']})"
                checkboxes_notas[p['Nota']] = st.checkbox(label)
                
            st.markdown("---")
            data_coleta = st.date_input("Data da Coleta Real (para as selecionadas acima)", format="DD/MM/YYYY")
            
            enviar_baixa = st.form_submit_button("Confirmar Baixa nas Selecionadas", use_container_width=True)
            
            if enviar_baixa:
                notas_selecionadas = [nota for nota, marcada in checkboxes_notas.items() if marcada]
                
                if not notas_selecionadas:
                    st.warning("⚠️ Você precisa marcar pelo menos uma caixinha para dar baixa.")
                else:
                    with st.spinner(f"Dando baixa em {len(notas_selecionadas)} nota(s)..."):
                        try:
                            planilha = conectar_planilha()
                            aba_sel = planilha.worksheet(transp_baixa)
                            coleta_formatada = data_coleta.strftime("%d/%m/%Y")
                            
                            for nota in notas_selecionadas:
                                celula = aba_sel.find(nota)
                                aba_sel.update_cell(celula.row, 4, coleta_formatada)
                                
                            st.success(f"✅ Baixa confirmada para as notas: {', '.join(notas_selecionadas)}!")
                            
                            try:
                                st.rerun()
                            except AttributeError:
                                st.experimental_rerun()
                                
                        except Exception as e:
                            st.error(f"Erro ao dar baixa: {e}")
    else:
        st.success(f"🎉 O galpão está limpo! Nenhuma nota pendente para a {transp_baixa}.")

# ==========================================
# ABA 2: PAINEL DA FILIAL
# ==========================================
with aba2:
    st.markdown("### 📊 Visão Geral do Estoque")
    
    if st.button("🔄 Atualizar Painel e Gerar Relatório", use_container_width=True):
        with st.spinner("Analisando as planilhas..."):
            dados = obter_dados_gerais()
            hoje = datetime.now().strftime("%d/%m/%Y")
            
            lancadas_hoje = [d for d in dados if d["Data_Solicitacao"] == hoje]
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
                    agrupado_pendentes.setdefault(t, []).append(f"Nº {d['Nota']} ({d['QTD']} vol - req: {d['Data_Solicitacao']})")
                
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
                            <b>Emissão da NFe:</b> {nota['Data_Emissao_Nota']}<br>
                            <b>Solicitada Coleta em:</b> {nota['Data_Solicitacao']}<br>
                            <b>Coletada em:</b> {nota['Data_Coleta'] if nota['Data_Coleta'] != "" else "Ainda na filial"}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.error("❌ Esta nota não foi encontrada em nenhuma das planilhas.")
