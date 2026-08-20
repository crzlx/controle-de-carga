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
        {"role": "assistant", "content": "Olá! Sou o Alessandro IA. Como posso ajudar com a expedição, dúvidas com clientes ou rotina do galpão hoje?"}
    ]

# ==========================================
# 🎨 CSS SEGURO (Apenas Animações e Cores)
# ==========================================
css_seguro = """
<style>
@keyframes fadeSlideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.main .block-container { animation: fadeSlideUp 0.5s cubic-bezier(0.25, 1, 0.5, 1); }
div.stButton > button { transition: all 0.2s ease !important; border-radius: 6px !important; }
div.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 4px 8px rgba(0,0,0,0.08) !important; }
div[data-testid="stMetric"] { transition: all 0.2s ease !important; padding: 12px !important; border-radius: 8px !important; }
div[data-testid="stMetric"]:hover { background-color: rgba(128,128,128,0.05) !important; transform: translateY(-2px) !important; }
</style>
"""
st.markdown(css_seguro, unsafe_allow_html=True)

# ==========================================
# LÓGICA DE E-MAILS OTIMIZADA
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
            urgencia_tag = "[URGENTE] " if "URGENTE" in prioridade else ""
            tipo_aviso = "LEMBRETE URGENTE: Coleta Pendente" if lembrete else "Nova Coleta Liberada"
            msg['Subject'] = f"{urgencia_tag}{tipo_aviso} - Speedmax (Nota: {nota})"
            msg['From'] = remetente
            msg['To'] = destinatario 
            corpo_email = f"Olá, equipe da {transportadora}!\n\n{'Este é um LEMBRETE de que temos' if lembrete else 'Temos uma nova'} mercadoria separada aguardando coleta na filial Speedmax.\n\nDETALHES:\n- Nota Fiscal: {nota}\n- Volumes: {qtd}\n\nPor favor, programem a retirada o mais rápido possível.\n\nLogística Speedmax."
            msg.set_content(corpo_email)
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(remetente, senha)
                smtp.send_message(msg)
            return True
        return False
    except Exception:
        return False

# ==========================================
# ACESSO AO BANCO DE DADOS
# ==========================================
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
                        "Transportadora": transp, "QTD": l[0].strip(), "Nota": str(l[1]).strip(),
                        "Data_Solicitacao": l[2].strip(), "Data_Coleta": l[3].strip(),
                        "Data_Emissao_Nota": l[4].strip(), "Usuario_Lancamento": l[5].strip() if len(l)>5 else "-",
                        "Prioridade": l[6].strip() if len(l)>6 else "Normal", "Usuario_Baixa": l[7].strip() if len(l)>7 else "-"
                    })
        except: pass
    return dados

# ==========================================
# 🤖 CHATBOT OTIMIZADO PARA PLANO GRATUITO
# ==========================================
@st.dialog("🤖 Chat com Alessandro IA")
def abrir_chat_ia():
    box_chat = st.container(height=400)
    with box_chat:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
    if nova_msg := st.chat_input("Pergunte sobre logística, vendas, transportadoras..."):
        st.session_state.chat_history.append({"role": "user", "content": nova_msg})
        with box_chat:
            with st.chat_message("user"):
                st.markdown(nova_msg)
            with st.chat_message("assistant"):
                with st.spinner("Analisando..."):
                    try:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        
                        # ALTERAÇÃO EXATA: Voltando ao modelo 3.6-flash que funciona no seu projeto
                        modelo = genai.GenerativeModel('gemini-3.6-flash')
                        
                        dados_estoque = obter_dados_gerais()
                        hoje = datetime.now().strftime("%d/%m/%Y")
                        
                        pendentes = [d for d in dados_estoque if d["Data_Coleta"] == ""]
                        
                        historico = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history[-4:]])
                        
                        prompt = f"""
                        Você é o Alessandro IA, assistente logístico avançado e versátil da Speedmax (Campos dos Goytacazes). Hoje é {hoje}.
                        Você ajuda com o galpão, vendas, clientes e redação profissional.
                        DADOS DE CARGAS PENDENTES HOJE: {json.dumps(pendentes, ensure_ascii=False)}
                        HISTÓRICO RECENTE: {historico}
                        Responda à pergunta do usuário de forma útil e direta: "{nova_msg}"
                        """
                        resposta = modelo.generate_content(prompt)
                        st.markdown(resposta.text)
                        st.session_state.chat_history.append({"role": "assistant", "content": resposta.text})
                        
                    except Exception as e:
                        erro_str = str(e).lower()
                        if "429" in erro_str or "quota" in erro_str or "exhausted" in erro_str:
                            erro_msg = "⏳ **Muitas mensagens rápidas da equipe!** O limite do plano gratuito ativou o modo de segurança. Por favor, espere **1 minutinho** e mande a mensagem de novo!"
                        else:
                            erro_msg = f"❌ Ocorreu um erro na IA: {e}"
                        
                        st.error(erro_msg)
                        st.session_state.chat_history.append({"role": "assistant", "content": erro_msg})

# ==========================================
# SIDEBAR - MENU DE USUÁRIO E BOTÃO DO CHAT
# ==========================================
with st.sidebar:
    st.header("👤 Operador")
    usuario_atual = st.selectbox("Identificação:", ["Pedro", "Alessandro", "Outro"])
    st.markdown("---")
    if st.button("💬 Falar com Alessandro IA", use_container_width=True):
        abrir_chat_ia()

# ==========================================
# CORPO PRINCIPAL DAS ABAS
# ==========================================
st.title("🚚 Expedição Campos Dos Goytacazes")

aba1, aba2, aba3, aba4 = st.tabs([
    "📦 Movimentação", "📊 Painel & Relatórios", "🔍 Consulta Rápida", "⚙️ Gerenciar & Cobrar"
])

# ==========================================
# ABA 1: MOVIMENTAÇÃO
# ==========================================
with aba1:
    st.header("📝 Lançar Nova Solicitação")
    st.markdown(f"Lançamento registrado por: **{usuario_atual}**.")
    with st.form("form_nova", clear_on_submit=True):
        col_t, col_p = st.columns([2, 1])
        with col_t: transp_nova = st.selectbox("Transportadora", TRANSPORTADORAS, key="t1")
        with col_p: prioridade = st.selectbox("Prioridade", ["Normal", "🚨 URGENTE"])
        col1, col2 = st.columns(2)
        with col1:
            qtd = st.number_input("QTD (Volumes)", min_value=1, step=1)
            data_solicitacao = st.date_input("Data da Solicitação", format="DD/MM/YYYY")
        with col2:
            nota_nova = st.text_input("Nota (Nº)", autocomplete="off")
            data_emissao = st.date_input("Data de Emissão da Nota", format="DD/MM/YYYY")
        enviar_nova = st.form_submit_button("Registrar Nota", use_container_width=True)
        
        if enviar_nova:
            if nota_nova == "": st.warning("⚠️ Preencha o número da Nota.")
            else:
                try:
                    planilha = conectar_planilha()
                    aba_sel = planilha.worksheet(transp_nova)
                    formatada_solicitacao = data_solicitacao.strftime("%d/%m/%Y")
                    formatada_emissao = data_emissao.strftime("%d/%m/%Y")
                    aba_sel.append_row([qtd, nota_nova, formatada_solicitacao, "", formatada_emissao, usuario_atual, prioridade])
                    st.success(f"✅ Nota {nota_nova} registrada!")
                    if transp_nova == "FL": st.info("💻 **ATENÇÃO:** O aviso para a FL deve ser enviado via Teams!")
                    else:
                        resultado_email = disparar_email_silencioso(transp_nova, nota_nova, qtd, prioridade=prioridade)
                        if resultado_email is True: st.info(f"📧 E-mail disparado para {transp_nova}.")
                        else: st.warning("⚠️ E-mail não configurado.")
                except Exception as e: st.error(f"Erro no banco de dados: {e}")

    st.markdown("---")
    st.header("✅ Confirmar Coleta em Lote")
    transp_baixa = st.selectbox("Transportadora (Baixa)", TRANSPORTADORAS, key="t2")
    dados_totais = obter_dados_gerais()
    pendentes_transp = [d for d in dados_totais if d["Transportadora"] == transp_baixa and d["Data_Coleta"] == ""]
    
    if pendentes_transp:
        with st.form("form_baixa"):
            st.markdown(f"📦 **Notas pendentes na doca ({transp_baixa}):**")
            checkboxes_notas = {}
            for p in pendentes_transp:
                prefixo_urg = "🚨 " if "URGENTE" in p['Prioridade'] else ""
                label = f"{prefixo_urg}Nº {p['Nota']} — {p['QTD']} volumes (Sol: {p['Data_Solicitacao']})"
                checkboxes_notas[p['Nota']] = st.checkbox(label)
            st.markdown("---")
            data_coleta = st.date_input("Data da Coleta Real", format="DD/MM/YYYY")
            enviar_baixa = st.form_submit_button(f"Confirmar Baixa (Registrar como {usuario_atual})", use_container_width=True)
            
            if enviar_baixa:
                notas_selecionadas = [nota for nota, marcada in checkboxes_notas.items() if marcada]
                if not notas_selecionadas: st.warning("⚠️ Marque pelo menos uma nota.")
                else:
                    with st.spinner("Sincronizando..."):
                        try:
                            planilha = conectar_planilha()
                            aba_sel = planilha.worksheet(transp_baixa)
                            coleta_formatada = data_coleta.strftime("%d/%m/%Y")
                            for nota in notas_selecionadas:
                                celula = aba_sel.find(nota)
                                aba_sel.update_cell(celula.row, 4, coleta_formatada)
                                aba_sel.update_cell(celula.row, 8, usuario_atual)
                            st.success("✅ Baixa confirmada perfeitamente!")
                            try: st.rerun()
                            except: st.experimental_rerun()
                        except Exception as e: st.error(f"Erro na sincronização: {e}")
    else: st.success(f"🎉 Doca limpa para a {transp_baixa}.")

# ==========================================
# ABA 2: PAINEL DA FILIAL (COM FILTROS)
# ==========================================
with aba2:
    st.markdown("### 📊 Dashboard Analítico")
    with st.expander("📅 Filtrar Dados por Período", expanded=True):
        c_ini, c_fim = st.columns(2)
        filtro_inicio = c_ini.date_input("Data Inicial", value=None, format="DD/MM/YYYY")
        filtro_fim = c_fim.date_input("Data Final", value=None, format="DD/MM/YYYY")
    
    if st.button("🔄 Gerar Análises do Período", use_container_width=True):
        if not filtro_inicio or not filtro_fim: st.warning("⚠️ Selecione as datas Inicial e Final.")
        else:
            with st.spinner("Processando..."):
                dados = obter_dados_gerais()
                hoje_dt = datetime.now()
                lancadas_periodo, coletadas_periodo, pendentes_gerais = [], [], []
                tempos_coleta = {t: [] for t in TRANSPORTADORAS}
                
                for d in dados:
                    dt_sol = parse_data(d["Data_Solicitacao"])
                    dt_col = parse_data(d["Data_Coleta"])
                    if dt_sol and filtro_inicio <= dt_sol <= filtro_fim: lancadas_periodo.append(d)
                    if d["Data_Coleta"] != "" and dt_col and filtro_inicio <= dt_col <= filtro_fim: coletadas_periodo.append(d)
                    if d["Data_Coleta"] == "": pendentes_gerais.append(d)
                    if d["Data_Coleta"] != "" and dt_sol and dt_col:
                        dias_demora = (dt_col - dt_sol).days
                        if dias_demora >= 0: tempos_coleta[d["Transportadora"]].append(dias_demora)
                
                pendentes_gerais = sorted(pendentes_gerais, key=lambda x: 0 if "URGENTE" in x["Prioridade"] else 1)

                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.metric("📦 Separadas no Período", len(lancadas_periodo))
                c2.metric("✅ Coletadas no Período", len(coletadas_periodo))
                c3.metric("⏳ Pendentes Hoje", len(pendentes_gerais))
                
                st.markdown("---")
                st.subheader("🏆 Ranking de Agilidade (Média Histórica)")
                ranking_dados = []
                for transp, tempos in tempos_coleta.items():
                    media = sum(tempos) / len(tempos) if tempos else "Sem dados"
                    ranking_dados.append({"Transportadora": transp, "Dias para Coleta": round(media, 1) if tempos else media})
                
                ranking_dados.sort(key=lambda x: x["Dias para Coleta"] if isinstance(x["Dias para Coleta"], float) else 999)
                cols_rank = st.columns(4)
                for idx, r in enumerate(ranking_dados):
                    with cols_rank[idx]:
                        st.info(f"**{r['Transportadora']}**\n\nTempo: {r['Dias para Coleta']} {'dias' if isinstance(r['Dias para Coleta'], float) else ''}")

                st.markdown("---")
                st.subheader("🚛 Fila de Aguardo")
                if pendentes_gerais:
                    lista_sla = []
                    for p in pendentes_gerais:
                        item = {"Transportadora": p["Transportadora"], "Nota": p["Nota"], "QTD": p["QTD"], "Prioridade": "🚨 URGENTE" if "URGENTE" in p["Prioridade"] else "Normal"}
                        try:
                            dias_parado = (hoje_dt - datetime.strptime(p["Data_Solicitacao"], "%d/%m/%Y")).days
                            if dias_parado == 0: item["Atraso"] = "🟢 Hoje"
                            elif dias_parado == 1: item["Atraso"] = "🟡 1 dia"
                            else: item["Atraso"] = f"🔴 {dias_parado} dias"
                        except: item["Atraso"] = "⚪ N/A"
                        lista_sla.append(item)
                    st.dataframe(lista_sla, use_container_width=True, hide_index=True)
                else: st.success("🎉 Nenhuma pendência!")

                st.markdown("---")
                st.subheader("📋 Resumo do Período (Copiar e Colar)")
                texto_relatorio = f"📊 *RELATÓRIO DE COLETAS ({filtro_inicio.strftime('%d/%m')} até {filtro_fim.strftime('%d/%m')})*\n\n✅ *COLETAS FINALIZADAS:* {len(coletadas_periodo)} nota(s)\n"
                if coletadas_periodo:
                    agrupado_coletadas = {}
                    for d in coletadas_periodo: agrupado_coletadas.setdefault(d["Transportadora"], []).append(f"Nº {d['Nota']} ({d['QTD']} vol)")
                    for transp, notas in agrupado_coletadas.items(): texto_relatorio += f"\n🚛 *{transp}* ({len(notas)}):\n   ↳ {', '.join(notas)}\n"
                else: texto_relatorio += "Nenhuma coleta.\n"
                texto_relatorio += "\n" + "-"*30 + f"\n\n⏳ *PENDÊNCIAS AGORA:* {len(pendentes_gerais)} nota(s)\n"
                if pendentes_gerais:
                    agrupado_pendentes = {}
                    for d in pendentes_gerais: agrupado_pendentes.setdefault(d["Transportadora"], []).append(f"{'[URGENTE] ' if 'URGENTE' in d['Prioridade'] else ''}Nº {d['Nota']} ({d['QTD']} vol - emissão: {d['Data_Emissao_Nota']} - req: {d['Data_Solicitacao']})")
                    for transp, notas in agrupado_pendentes.items():
                        texto_relatorio += f"\n⚠️ *{transp}* ({len(notas)}):\n"
                        for n in notas: texto_relatorio += f"   ↳ {n}\n"
                
                st.text_area("Texto Copiável:", value=texto_relatorio, height=300)
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=["Transportadora", "QTD", "Nota", "Data_Solicitacao", "Data_Coleta", "Data_Emissao_Nota", "Usuario_Lancamento", "Prioridade", "Usuario_Baixa"])
                writer.writeheader()
                writer.writerows(dados)
                st.download_button("📥 Baixar Histórico em CSV", data=output.getvalue().encode('utf-8'), file_name=f"relatorio.csv", mime="text/csv", use_container_width=True)

# ==========================================
# ABA 3: CONSULTA RÁPIDA
# ==========================================
with aba3:
    st.markdown("### 🔍 Pesquisa & Rastreabilidade")
    nota_busca = st.text_input("Digite o Número da Nota:", autocomplete="off")
    if st.button("Procurar Nota", use_container_width=True):
        if nota_busca:
            with st.spinner("Buscando rastros..."):
                dados = obter_dados_gerais()
                encontradas = [d for d in dados if d["Nota"] == nota_busca.strip()]
                if encontradas:
                    for nota in encontradas:
                        status = "✅ Já Coletada" if nota["Data_Coleta"] != "" else "⏳ Aguardando"
                        cor_status, cor_texto = ("#d4edda", "#155724") if nota["Data_Coleta"] != "" else ("#fff3cd", "#856404")
                        st.markdown(f"""
                        <div style="background-color: {cor_status}; color: {cor_texto}; padding: 15px; border-radius: 10px; margin-top: 10px;">
                            <h4 style="margin-top:0;">{ '🚨 ' if 'URGENTE' in nota['Prioridade'] else ''}Nota: {nota['Nota']}</h4>
                            <b>Status:</b> {status}<br><b>Transportadora:</b> {nota['Transportadora']}<br><b>Volumes:</b> {nota['QTD']}<br>
                            <hr style="border-top: 1px solid {cor_texto}; opacity: 0.3;">
                            <b>Lançado em:</b> {nota['Data_Solicitacao']} <i>({nota['Usuario_Lancamento']})</i><br>
                            <b>Baixado em:</b> {nota['Data_Coleta'] if nota['Data_Coleta'] != "" else "-"} <i>({nota['Usuario_Baixa']})</i>
                        </div>
                        """, unsafe_allow_html=True)
                else: st.error("❌ Nota não encontrada.")

# ==========================================
# ABA 4: GERENCIAR E COBRAR
# ==========================================
with aba4:
    st.markdown("### ⚙️ Corrigir, Excluir ou Re-cobrar")
    nota_alvo = st.text_input("Digite a Nota Fiscal para gerenciar:", autocomplete="off")
    if st.button("Buscar Registro", use_container_width=True):
        if nota_alvo:
            dados = obter_dados_gerais()
            encontradas = [d for d in dados if d["Nota"] == nota_alvo.strip()]
            if encontradas: st.session_state['nota_gerenciar'] = encontradas[0]
            else:
                st.error("❌ Nota não encontrada.")
                if 'nota_gerenciar' in st.session_state: del st.session_state['nota_gerenciar']
                        
    if 'nota_gerenciar' in st.session_state:
        n = st.session_state['nota_gerenciar']
        st.info(f"Gerenciando Nota: **{n['Nota']}** ({n['Transportadora']})")
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔔 Enviar Lembrete", use_container_width=True):
                if n["Transportadora"] == "FL": st.warning("⚠️ Cobre a FL via Teams!")
                else:
                    res = disparar_email_silencioso(n["Transportadora"], n["Nota"], n["QTD"], lembrete=True, prioridade=n["Prioridade"])
                    if res is True: st.success("✅ Cobrança disparada com urgência!")
                    else: st.error("❌ Erro ao enviar.")
        with c_btn2:
            if st.button("🗑️ Excluir Registro", type="primary", use_container_width=True):
                try:
                    planilha = conectar_planilha()
                    aba = planilha.worksheet(n["Transportadora"])
                    cel = aba.find(n["Nota"])
                    aba.delete_rows(cel.row)
                    st.success("✅ Apagado com sucesso!")
                    del st.session_state['nota_gerenciar']
                    try: st.rerun()
                    except: st.experimental_rerun()
                except Exception as e: st.error(f"Erro ao excluir: {e}")
