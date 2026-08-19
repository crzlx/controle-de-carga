import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime
import google.generativeai as genai
import smtplib
from email.message import EmailMessage
import csv
import io
import pandas as pd

# ==========================================
# CONFIGURAÇÃO GERAL E ESTADOS
# ==========================================
st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="wide")

TRANSPORTADORAS = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Olá! Sou o Alessandro IA. Estou aqui para ajudar com o status da expedição e resolver problemas logísticos. Como posso ser útil hoje?"}
    ]

# ==========================================
# 🎨 CSS MINIMALISTA
# ==========================================
css_seguro = """
<style>
.main .block-container { animation: fadeSlideUp 0.5s ease; }
div.stButton > button { transition: all 0.2s ease !important; border-radius: 6px !important; }
div.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.08) !important; }
</style>
"""
st.markdown(css_seguro, unsafe_allow_html=True)

# ==========================================
# LÓGICA E BANCO DE DADOS
# ==========================================
def disparar_email_silencioso(transportadora, nota, qtd, lembrete=False, prioridade="Normal"):
    try:
        remetente = st.secrets["EMAIL_REMETENTE"]
        senha = st.secrets["SENHA_EMAIL"]
        emails_destino = {
            "JARBAS": "adm.campos@italogrj.com.br",
            "TRANSCHERRER": "filial.campos@transcherrer.com.br, cidy.neves@transcherrer.com.br, filial.campos02@transcherrer.com.br",
            "GENEROSO": "Encarregado.cgo@generoso.com.br"
        }
        destinatario = emails_destino.get(transportadora)
        if destinatario and "teste.com" not in destinatario.lower():
            msg = EmailMessage()
            msg['Subject'] = f"{'[URGENTE] ' if 'URGENTE' in prioridade else ''}{'LEMBRETE URGENTE: ' if lembrete else 'Nova Coleta Liberada - '}Speedmax (Nota: {nota})"
            msg['From'] = remetente
            msg['To'] = destinatario 
            msg.set_content(f"Olá, equipe da {transportadora}!\n\nTemos uma carga {'(PRIORIDADE URGENTE)' if 'URGENTE' in prioridade else ''} para coleta.\nNota: {nota}\nVolumes: {qtd}\n\nLogística Speedmax.")
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(remetente, senha)
                smtp.send_message(msg)
            return True
        return False
    except: return False

def conectar_planilha():
    escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    cred_dict = json.loads(st.secrets["google_credentials"])
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(cred_dict, escopo)
    cliente = gspread.authorize(credenciais)
    return cliente.open_by_url("https://docs.google.com/spreadsheets/d/1yHThW-nbcwxCcNTnb66PP1YHbHpCE9_ep3DC33-OZs4/edit?usp=sharing")

def parse_data(data_str):
    try: return datetime.strptime(data_str, "%d/%m/%Y").date()
    except: return None

def obter_dados_gerais():
    planilha = conectar_planilha()
    dados = []
    for transp in TRANSPORTADORAS:
        try:
            aba = planilha.worksheet(transp)
            for l in aba.get_all_values()[1:]:
                if len(l) >= 2 and str(l[1]).strip() != "":
                    dados.append({
                        "Transportadora": transp,
                        "QTD": l[0].strip(), "Nota": str(l[1]).strip(),
                        "Data_Solicitacao": l[2].strip(), "Data_Coleta": l[3].strip(),
                        "Data_Emissao_Nota": l[4].strip(), "Usuario_Lancamento": l[5].strip(),
                        "Prioridade": l[6].strip() if len(l) > 6 else "Normal",
                        "Usuario_Baixa": l[7].strip() if len(l) > 7 else "-"
                    })
        except: pass
    return dados

# ==========================================
# CHATBOT FLUTUANTE (MODAL CENTRAL)
# ==========================================
@st.dialog("🤖 Chat com Alessandro IA")
def abrir_chat_ia():
    box_chat = st.container(height=400)
    with box_chat:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
    if nova_msg := st.chat_input("Pergunte algo..."):
        st.session_state.chat_history.append({"role": "user", "content": nova_msg})
        with box_chat:
            with st.chat_message("user"): st.markdown(nova_msg)
            with st.chat_message("assistant"):
                with st.spinner("Analisando..."):
                    try:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        # Retornando ao modelo que funcionava originalmente
                        modelo = genai.GenerativeModel('gemini-3.6-flash')
                        
                        dados_estoque = obter_dados_gerais()
                        hoje = datetime.now().strftime("%d/%m/%Y")
                        prompt = f"O seu nome é Alessandro IA. Hoje é {hoje}. Responda à pergunta: '{nova_msg}'. DADOS FILIAL: {json.dumps(dados_estoque[-10:], ensure_ascii=False)}"
                        resposta = modelo.generate_content(prompt)
                        st.markdown(resposta.text)
                        st.session_state.chat_history.append({"role": "assistant", "content": resposta.text})
                    except Exception as e:
                        st.error(f"Erro: {e}")

# ==========================================
# SIDEBAR E CORPO PRINCIPAL
# ==========================================
with st.sidebar:
    st.header("👤 Operador")
    usuario_atual = st.selectbox("Identificação:", ["Pedro", "Alessandro", "Outro"])
    if st.button("💬 Falar com Alessandro IA", use_container_width=True): abrir_chat_ia()

st.title("🚚 Expedição Campos Dos Goytacazes")
aba1, aba2, aba3, aba4 = st.tabs(["📦 Movimentação", "📊 Painel & Relatórios", "🔍 Consulta Rápida", "⚙️ Gerenciar & Cobrar"])

# (O resto da lógica das abas 1, 2, 3 e 4 permanece o mesmo do código anterior...)
# (Atenção: como o texto aqui no chat tem limite, cole a estrutura de abas que já tínhamos abaixo desta linha)
