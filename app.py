import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Configuração visual da página
st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="centered")

def conectar_planilha():
    escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Puxa as credenciais de forma segura do cofre do Streamlit
    cred_dict = json.loads(st.secrets["google_credentials"])
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(cred_dict, escopo)
    cliente = gspread.authorize(credenciais)
    
    # Abre a planilha pelo nome exato que você deu
    planilha = cliente.open("Coletas")
    return planilha

st.title("🚚 Registro de Coletas")

with st.form("form_coleta", clear_on_submit=True):
    # 1. Seleção da transportadora (Isso vai definir em qual aba o dado será salvo)
    transportadoras = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]
    transportadora_escolhida = st.selectbox("Transportadora", transportadoras)
    
    st.markdown("---")
    
    # Organizando os campos em duas colunas para a tela ficar mais limpa
    col1, col2 = st.columns(2)
    
    with col1:
        # Coluna A: QTD
        qtd = st.number_input("QTD", min_value=1, step=1)
        # Coluna C: Data
        data_emissao = st.date_input("Data", format="DD/MM/YYYY")
        
    with col2:
        # Coluna B: Nota
        nota = st.text_input("Nota (Nº)")
        # Coluna D: DT. COLETA
        dt_coleta = st.date_input("DT. COLETA", format="DD/MM/YYYY")
    
    st.markdown("---")
    enviado = st.form_submit_button("Registrar Coleta", use_container_width=True)
    
    if enviado:
        if nota == "":
            st.warning("⚠️ Por favor, preencha o número da Nota.")
        else:
            try:
                planilha = conectar_planilha()
                
                # 2. Direciona o sistema para abrir a aba específica escolhida no menu
                aba_selecionada = planilha.worksheet(transportadora_escolhida)
                
                # Converte as datas selecionadas no calendário para o formato brasileiro (Texto)
                data_formatada = data_emissao.strftime("%d/%m/%Y")
                coleta_formatada = dt_coleta.strftime("%d/%m/%Y")
                
                # 3. Monta a linha seguindo exatamente a ordem das suas colunas: QTD | Nota | Data | DT. COLETA
                nova_linha = [qtd, nota, data_formatada, coleta_formatada]
                
                # Insere a linha na aba correspondente
                aba_selecionada.append_row(nova_linha)
                
                st.success(f"✅ Nota {nota} salva com sucesso na aba {transportadora_escolhida}!")
            except Exception as e:
                st.error("Erro ao salvar os dados. Verifique a conexão ou as credenciais.")
