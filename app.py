import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import urllib.parse
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="centered")

def conectar_planilha():
    escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    cred_dict = json.loads(st.secrets["google_credentials"])
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(cred_dict, escopo)
    cliente = gspread.authorize(credenciais)
    return cliente.open_by_url("https://docs.google.com/spreadsheets/d/1yHThW-nbcwxCcNTnb66PP1YHbHpCE9_ep3DC33-OZs4/edit?usp=sharing")

# Função inteligente que lê todas as planilhas de uma vez para não travar o sistema
def obter_dados_gerais():
    planilha = conectar_planilha()
    dados = []
    transportadoras = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]
    
    for transp in transportadoras:
        try:
            aba = planilha.worksheet(transp)
            linhas = aba.get_all_values()
            for l in linhas[1:]: # Pula o cabeçalho
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

# Cria as 6 Abas do Sistema
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
    "📝 Lançar", "✅ Baixar", "📊 Pendências", "📈 Dash", "🔍 Buscar", "📋 Resumo"
])

# --- ABA 1: LANÇAR ---
with aba1:
    st.markdown("Registre a nota separada para coleta.")
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
                    
                    # Mensagem WPP ou Teams
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

# --- ABA 2: BAIXAR ---
with aba2:
    st.markdown("Confirme que a mercadoria foi levada.")
    with st.form("form_baixa", clear_on_submit=True):
        transp_baixa = st.selectbox("Transportadora", transportadoras, key="t2")
        col3, col4 = st.columns(2)
        with col3:
            nota_baixa = st.text_input("Nota (Nº)")
        with col4:
            data_coleta = st.date_input("Data da Coleta", format="DD/MM/YYYY")
            
        enviar_baixa = st.form_submit_button("Confirmar Coleta", use_container_width=True)
        
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
                    st.success(f"✅ Coleta {nota_baixa} confirmada!")
                except gspread.CellNotFound:
                    st.error(f"❌ Nota {nota_baixa} não encontrada na {transp_baixa}.")
                except Exception as e:
                    st.error(f"Erro: {e}")

# --- ABA 3: PENDÊNCIAS ---
with aba3:
    st.markdown("### 📊 Notas Aguardando Coleta")
    if st.button("🔄 Buscar Pendências", use_container_width=True):
        with st.spinner("Lendo planilhas..."):
            dados = obter_dados_gerais()
            pendentes = [d for d in dados if d["Data_Coleta"] == ""]
            
            if pendentes:
                st.warning(f"🚚 Existem **{len(pendentes)}** notas paradas na doca.")
                st.dataframe(pendentes, use_container_width=True, hide_index=True)
            else:
                st.success("🎉 Nenhuma pendência! A doca está limpa.")

# --- ABA 4: DASHBOARD MINIMALISTA ---
with aba4:
    st.markdown("### 📈 Painel de Operação de Hoje")
    if st.button("🔄 Atualizar Números", use_container_width=True):
        with st.spinner("Calculando..."):
            dados = obter_dados_gerais()
            hoje = datetime.now().strftime("%d/%m/%Y")
            
            lancadas_hoje = [d for d in dados if d["Data_Emissao"] == hoje]
            coletadas_hoje = [d for d in dados if d["Data_Coleta"] == hoje]
            pendentes_total = [d for d in dados if d["Data_Coleta"] == ""]
            
            # Blocos Visuais Grandes
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Lançadas Hoje", len(lancadas_hoje))
            c2.metric("✅ Coletadas Hoje", len(coletadas_hoje))
            c3.metric("⏳ Pendentes (Total)", len(pendentes_total))
            
            st.markdown("---")
            st.write("**Top Coletas de Hoje (Por Transportadora):**")
            transp_hoje = {}
            for d in coletadas_hoje:
                t = d["Transportadora"]
                transp_hoje[t] = transp_hoje.get(t, 0) + 1
            
            if transp_hoje:
                st.dataframe([{"Transportadora": k, "Notas Coletadas Hoje": v} for k, v in transp_hoje.items()], hide_index=True, use_container_width=True)
            else:
                st.info("Nenhuma coleta finalizada no dia de hoje ainda.")

# --- ABA 5: RASTREADOR (BUSCAR NOTA) ---
with aba5:
    st.markdown("### 🔍 Pesquisa Rápida")
    st.markdown("Alguém perguntou de uma nota? Digite abaixo para achar na hora.")
    nota_busca = st.text_input("Número da Nota:")
    
    if st.button("Buscar", use_container_width=True):
        if nota_busca:
            with st.spinner("Procurando em todas as planilhas..."):
                dados = obter_dados_gerais()
                encontradas = [d for d in dados if d["Nota"] == nota_busca.strip()]
                
                if encontradas:
                    for nota in encontradas:
                        # Define visual dependendo se está pendente ou não
                        status = "✅ Já Coletada" if nota["Data_Coleta"] != "" else "⏳ Aguardando Coleta na Doca"
                        cor_status = "#d4edda" if nota["Data_Coleta"] != "" else "#fff3cd"
                        cor_texto = "#155724" if nota["Data_Coleta"] != "" else "#856404"
                        
                        st.markdown(f"""
                        <div style="background-color: {cor_status}; color: {cor_texto}; padding: 15px; border-radius: 10px; margin-top: 10px;">
                            <h4 style="margin-top:0;">Nota: {nota['Nota']}</h4>
                            <b>Status:</b> {status}<br>
                            <b>Transportadora:</b> {nota['Transportadora']}<br>
                            <b>QTD Volumes:</b> {nota['QTD']}<br>
                            <b>Solicitada em:</b> {nota['Data_Emissao']}<br>
                            <b>Coletada em:</b> {nota['Data_Coleta'] if nota['Data_Coleta'] != "" else "Ainda não coletada"}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.error("❌ Esta nota não foi encontrada em nenhuma transportadora.")

# --- ABA 6: FECHAMENTO DO DIA ---
with aba6:
    st.markdown("### 📋 Resumo para o Gestor")
    st.markdown("Aperte o botão para gerar o texto do fim de turno automático.")
    
    if st.button("Gerar Relatório de Hoje", use_container_width=True):
        with st.spinner("Montando relatório..."):
            dados = obter_dados_gerais()
            hoje = datetime.now().strftime("%d/%m/%Y")
            
            coletadas_hoje = [d for d in dados if d["Data_Coleta"] == hoje]
            pendentes_total = len([d for d in dados if d["Data_Coleta"] == ""])
            
            transp_hoje = {}
            for d in coletadas_hoje:
                t = d["Transportadora"]
                transp_hoje[t] = transp_hoje.get(t, 0) + 1
            
            texto_relatorio = f"*FECHAMENTO DE COLETAS - {hoje}*\n\n"
            texto_relatorio += f"📦 *Total de Expedições Finalizadas:* {len(coletadas_hoje)} notas coletadas hoje.\n\n"
            
            if transp_hoje:
                texto_relatorio += "*Divisão por Transportadora:*\n"
                for transp, qtd in transp_hoje.items():
                    texto_relatorio += f" - {transp}: {qtd} nota(s)\n"
            else:
                texto_relatorio += "Nenhuma transportadora realizou coleta hoje.\n"
                
            texto_relatorio += f"\n⏳ *Ficam pendentes na doca:* {pendentes_total} notas no total.\n"
            
            st.success("Relatório gerado! Clique dentro da caixa abaixo, copie e cole no WhatsApp/Teams.")
            st.text_area("Texto Copiável:", value=texto_relatorio, height=250)
