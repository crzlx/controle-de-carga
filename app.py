import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import urllib.parse

st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="centered")

def conectar_planilha():
    escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    cred_dict = json.loads(st.secrets["google_credentials"])
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(cred_dict, escopo)
    cliente = gspread.authorize(credenciais)
    
    return cliente.open_by_url("https://docs.google.com/spreadsheets/d/1yHThW-nbcwxCcNTnb66PP1YHbHpCE9_ep3DC33-OZs4/edit?usp=sharing")

st.title("🚚 Gestão de Coletas")

aba1, aba2 = st.tabs(["📝 Lançar Nova Nota", "✅ Confirmar Coleta"])

transportadoras = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]

# --- PRIMEIRA ABA: Lançar a solicitação ---
with aba1:
    st.markdown("Registre a nota separada. A data de coleta ficará em branco na planilha.")
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
                    
                    nova_linha = [qtd, nota_nova, data_formatada, ""]
                    aba_sel.append_row(nova_linha)
                    st.success(f"✅ Nota {nota_nova} registrada na aba {transp_nova}!")
                    
                    # --- LÓGICA DO AVISO (WHATSAPP E TEAMS) ---
                    if transp_nova == "FL":
                        st.info("💻 A transportadora FL foi selecionada. Lembre-se de enviar o aviso manualmente pelo **Microsoft Teams**!")
                    else:
                        # Telefones oficiais atualizados
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
                        
                except gspread.WorksheetNotFound:
                    st.error(f"❌ A aba '{transp_nova}' não foi encontrada na planilha.")
                except Exception as e:
                    st.error(f"Erro ao salvar os dados: {e}")

# --- SEGUNDA ABA: Dar baixa quando o caminhão chega ---
with aba2:
    st.markdown("Use apenas quando a transportadora vier buscar a mercadoria.")
    with st.form("form_baixa", clear_on_submit=True):
        transp_baixa = st.selectbox("Transportadora", transportadoras, key="t2")
        
        col3, col4 = st.columns(2)
        with col3:
            nota_baixa = st.text_input("Nota (Nº) a ser baixada")
        with col4:
            data_coleta = st.date_input("Data da Coleta Real", format="DD/MM/YYYY")
            
        enviar_baixa = st.form_submit_button("Confirmar Coleta", use_container_width=True)
        
        if enviar_baixa:
            if nota_baixa == "":
                st.warning("⚠️ Preencha o número da Nota.")
            else:
                try:
                    planilha = conectar_planilha()
                    aba_sel = planilha.worksheet(transp_baixa)
                    celula = aba_sel.find(nota_baixa)
                    coleta_formatada = data_coleta.strftime("%d/%m/%Y")
                    aba_sel.update_cell(celula.row, 4, coleta_formatada)
                    st.success(f"✅ Coleta da nota {nota_baixa} confirmada para {coleta_formatada}!")
                except gspread.CellNotFound:
                    st.error(f"❌ A Nota {nota_baixa} não foi encontrada na aba {transp_baixa}.")
                except gspread.WorksheetNotFound:
                    st.error(f"❌ A aba '{transp_baixa}' não foi encontrada.")
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")
