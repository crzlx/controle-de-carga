import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import urllib.parse
from datetime import datetime
import google.generativeai as genai
import smtplib
from email.message import EmailMessage
import csv
import io
import pandas as pd

# Configuração da Página
st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="wide")

# ==========================================
# FUNÇÃO DO ROBÔ DE E-MAILS
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
            
            # Formatação baseada na prioridade
            alerta_urgencia = "[URGENTE] " if "URGENTE" in prioridade else ""
            
            if lembrete:
                msg['Subject'] = f"{alerta_urgencia}LEMBRETE URGENTE: Coleta Pendente - Speedmax (Nota: {nota})"
                corpo_email = f"""
Olá, equipe da {transportadora}!

Este é um LEMBRETE de que temos mercadoria separada aguardando coleta na filial Speedmax.
{'ATENÇÃO: ESTA É UMA CARGA COM PRIORIDADE URGENTE!' if 'URGENTE' in prioridade else ''}

DETALHES DA COLETA PENDENTE:
- Nota Fiscal: {nota}
- Quantidade de Volumes: {qtd}

Por favor, priorizem a programação desta coleta o mais rápido possível.

Atenciosamente,
Logística Speedmax.
                """
            else:
                msg['Subject'] = f"{alerta_urgencia}Nova Coleta Liberada - Speedmax (Nota: {nota})"
                corpo_email = f"""
Olá, equipe da {transportadora}!

Temos uma nova mercadoria separada e liberada para coleta na filial Speedmax.
{'ATENÇÃO: ESTA É UMA CARGA COM PRIORIDADE URGENTE!' if 'URGENTE' in prioridade else ''}

DETALHES DA COLETA:
- Nota Fiscal: {nota}
- Quantidade de Volumes: {qtd}

Por favor, programem a coleta assim que possível.

Atenciosamente,
Logística Speedmax.
                """
                
            msg['From'] = remetente
            msg['To'] = destinatario 
            msg.set_content(corpo_email)
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(remetente, senha)
                smtp.send_message(msg)
                
            return True
        return False
    except Exception as e:
        return str(e)

# ==========================================
# FUNÇÕES DE BANCO DE DADOS E SUPORTE
# ==========================================
def conectar_planilha():
    escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    cred_dict = json.loads(st.secrets["google_credentials"])
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(cred_dict, escopo)
    cliente = gspread.authorize(credenciais)
    return cliente.open_by_url("https://docs.google.com/spreadsheets/d/1yHThW-nbcwxCcNTnb66PP1YHbHpCE9_ep3DC33-OZs4/edit?usp=sharing")

def parse_data(data_str):
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").date()
    except:
        return None

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
                        "Data_Emissao_Nota": l[4].strip() if len(l) > 4 else "-",
                        "Usuario_Lancamento": l[5].strip() if len(l) > 5 else "-",
                        "Prioridade": l[6].strip() if len(l) > 6 else "Normal",
                        "Usuario_Baixa": l[7].strip() if len(l) > 7 else "-"
                    })
        except:
            pass
    return dados

# ==========================================
# MENU LATERAL - IDENTIFICAÇÃO E IA
# ==========================================
with st.sidebar:
    st.header("👤 Operador do Sistema")
    usuario_atual = st.selectbox("Quem está utilizando o aplicativo?", ["Almoxarife", "Pedro (Gestão)", "Outro"])
    
    st.markdown("---")
    st.header("🤖 Alessandro IA")
    st.markdown("Estou aqui para te ajudar com a logística.")
    
    pergunta_usuario = st.text_area("O que você precisa?", placeholder="Ex: Quantas notas urgentes temos?")
    
    if st.button("Perguntar ao Alessandro", use_container_width=True):
        if pergunta_usuario:
            with st.spinner("Pensando..."):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    modelo = genai.GenerativeModel('gemini-3.6-flash')
                    dados_estoque = obter_dados_gerais()
                    hoje = datetime.now().strftime("%d/%m/%Y")
                    dados_filtrados = [d for d in dados_estoque if d["Data_Coleta"] == "" or d["Data_Coleta"] == hoje or d["Data_Solicitacao"] == hoje]
                    
                    prompt = f"""
                    O seu nome é Alessandro IA. Você é um assistente logístico que ajuda o administrador de um galpão.
                    Hoje é dia {hoje}. Seja direto e polido.
                    Aqui estão os dados resumidos das notas pendentes na filial e das operações de hoje:
                    {json.dumps(dados_filtrados, ensure_ascii=False)}
                    Use EXCLUSIVAMENTE esses dados para responder. 
                    Pergunta: "{pergunta_usuario}"
                    """
                    resposta = modelo.generate_content(prompt)
                    st.success("✅ Resposta:")
                    st.markdown(f"> {resposta.text}")
                except Exception as e:
                    st.error(f"❌ Erro na IA: {e}")
        else:
            st.warning("⚠️ Digite uma pergunta primeiro.")

# ==========================================
# CORPO PRINCIPAL DO APLICATIVO
# ==========================================
st.title("🚚 Expedição Campos Dos Goytacazes")

transportadoras = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]

aba1, aba2, aba3, aba4 = st.tabs([
    "📦 Movimentação", "📊 Painel & Relatórios", "🔍 Consulta Rápida", "⚙️ Gerenciar & Cobrar"
])

# ==========================================
# ABA 1: MOVIMENTAÇÃO
# ==========================================
with aba1:
    st.header("📝 Lançar Nova Solicitação")
    st.markdown("Registre a nota separada. O sistema já gravará que o lançamento foi feito por: **" + usuario_atual + "**.")
    
    with st.form("form_nova", clear_on_submit=True):
        col_t, col_p = st.columns([2, 1])
        with col_t:
            transp_nova = st.selectbox("Transportadora", transportadoras, key="t1")
        with col_p:
            prioridade = st.selectbox("Prioridade", ["Normal", "🚨 URGENTE"])
            
        col1, col2 = st.columns(2)
        with col1:
            qtd = st.number_input("QTD (Volumes)", min_value=1, step=1)
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
                    
                    # Salva: QTD, NOTA, D.SOL, D.COL(vazio), D.EMI, USUARIO_LANC, PRIORIDADE
                    aba_sel.append_row([qtd, nota_nova, formatada_solicitacao, "", formatada_emissao, usuario_atual, prioridade])
                    st.success(f"✅ Nota {nota_nova} registrada com sucesso!")
                    
                    if transp_nova == "FL":
                        st.info("💻 **ATENÇÃO:** O aviso para a FL deve ser enviado manualmente pelo Teams!")
                    else:
                        resultado_email = disparar_email_silencioso(transp_nova, nota_nova, qtd, prioridade=prioridade)
                        if resultado_email is True:
                            st.info(f"📧 E-mail enviado automaticamente para {transp_nova}!")
                        elif resultado_email is False:
                            st.warning("⚠️ E-mail oficial não configurado.")
                        else:
                            st.error(f"❌ Erro ao enviar e-mail: {resultado_email}")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    st.markdown("---")
    
    st.header("✅ Confirmar Coleta em Lote")
    transp_baixa = st.selectbox("Transportadora (Baixa)", transportadoras, key="t2")
    
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
            enviar_baixa = st.form_submit_button("Confirmar Baixa (Registrar como " + usuario_atual + ")", use_container_width=True)
            
            if enviar_baixa:
                notas_selecionadas = [nota for nota, marcada in checkboxes_notas.items() if marcada]
                if not notas_selecionadas:
                    st.warning("⚠️ Marque pelo menos uma nota.")
                else:
                    with st.spinner("Dando baixa..."):
                        try:
                            planilha = conectar_planilha()
                            aba_sel = planilha.worksheet(transp_baixa)
                            coleta_formatada = data_coleta.strftime("%d/%m/%Y")
                            
                            for nota in notas_selecionadas:
                                celula = aba_sel.find(nota)
                                aba_sel.update_cell(celula.row, 4, coleta_formatada) # Atualiza Data_Coleta
                                aba_sel.update_cell(celula.row, 8, usuario_atual)    # Grava Usuario_Baixa na coluna H
                                
                            st.success(f"✅ Baixa confirmada!")
                            try:
                                st.rerun()
                            except AttributeError:
                                st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Erro ao dar baixa: {e}")
    else:
        st.success(f"🎉 Galpão limpo! Nenhuma nota para {transp_baixa}.")

# ==========================================
# ABA 2: PAINEL DA FILIAL (COM FILTROS)
# ==========================================
with aba2:
    st.markdown("### 📊 Dashboard Analítico")
    
    with st.expander("📅 Filtrar Dados por Período", expanded=True):
        c_ini, c_fim = st.columns(2)
        filtro_inicio = c_ini.date_input("Data Inicial", value=datetime.today(), format="DD/MM/YYYY")
        filtro_fim = c_fim.date_input("Data Final", value=datetime.today(), format="DD/MM/YYYY")
    
    if st.button("🔄 Gerar Análises do Período", use_container_width=True):
        with st.spinner("Processando Inteligência de Dados..."):
            dados = obter_dados_gerais()
            hoje_dt = datetime.now()
            
            # Arrays para alimentar o painel baseado no filtro
            lancadas_periodo = []
            coletadas_periodo = []
            pendentes_gerais = []
            
            # Ranking SLA Base data
            tempos_coleta = {t: [] for t in transportadoras}
            
            for d in dados:
                dt_sol = parse_data(d["Data_Solicitacao"])
                dt_col = parse_data(d["Data_Coleta"])
                
                # Regra de Lançadas no Período
                if dt_sol and filtro_inicio <= dt_sol <= filtro_fim:
                    lancadas_periodo.append(d)
                
                # Regra de Coletadas no Período
                if d["Data_Coleta"] != "" and dt_col and filtro_inicio <= dt_col <= filtro_fim:
                    coletadas_periodo.append(d)
                    
                # Regra de Pendentes (Não tem baixa, ignora filtro de data final para mostrar o que tá agarrado)
                if d["Data_Coleta"] == "":
                    pendentes_gerais.append(d)
                    
                # Acumulador para Ranking de SLA de todas as notas que já foram coletadas
                if d["Data_Coleta"] != "" and dt_sol and dt_col:
                    dias_demora = (dt_col - dt_sol).days
                    if dias_demora >= 0:
                        tempos_coleta[d["Transportadora"]].append(dias_demora)
            
            # Ordena a lista de pendentes colocando "URGENTE" no topo
            pendentes_gerais = sorted(pendentes_gerais, key=lambda x: 0 if "URGENTE" in x["Prioridade"] else 1)

            # --- MÉTRICAS ---
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Separadas no Período", len(lancadas_periodo))
            c2.metric("✅ Coletadas no Período", len(coletadas_periodo))
            c3.metric("⏳ Pendentes Hoje (Fila)", len(pendentes_gerais))
            
            # --- RANKING SLA ---
            st.markdown("---")
            st.subheader("🏆 Ranking de Agilidade (Média Histórica)")
            ranking_dados = []
            for transp, tempos in tempos_coleta.items():
                if tempos:
                    media = sum(tempos) / len(tempos)
                    ranking_dados.append({"Transportadora": transp, "Dias para Coleta": round(media, 1)})
                else:
                    ranking_dados.append({"Transportadora": transp, "Dias para Coleta": "Sem dados"})
            
            # Ordena do mais rápido para o mais lento (ignorando quem não tem dados)
            ranking_dados.sort(key=lambda x: x["Dias para Coleta"] if isinstance(x["Dias para Coleta"], float) else 999)
            cols_rank = st.columns(4)
            for idx, r in enumerate(ranking_dados):
                with cols_rank[idx]:
                    st.info(f"**{r['Transportadora']}**\n\nTempo Médio: {r['Dias para Coleta']} {'dias' if isinstance(r['Dias para Coleta'], float) else ''}")

            # --- PENDÊNCIAS COM URGÊNCIA ---
            st.markdown("---")
            st.subheader("🚛 Fila de Aguardo (Prioridade Organizada)")
            if pendentes_gerais:
                st.warning(f"Temos **{len(pendentes_gerais)}** notas no galpão aguardando as transportadoras.")
                
                lista_sla = []
                for p in pendentes_gerais:
                    item = {"Transportadora": p["Transportadora"], "Nota": p["Nota"], "QTD": p["QTD"], "Prioridade": "🚨 URGENTE" if "URGENTE" in p["Prioridade"] else "Normal"}
                    try:
                        data_sol = datetime.strptime(p["Data_Solicitacao"], "%d/%m/%Y")
                        dias_parado = (hoje_dt - data_sol).days
                        if dias_parado == 0: item["Atraso"] = "🟢 Hoje"
                        elif dias_parado == 1: item["Atraso"] = "🟡 1 dia"
                        else: item["Atraso"] = f"🔴 {dias_parado} dias"
                    except:
                        item["Atraso"] = "⚪ N/A"
                    lista_sla.append(item)
                    
                st.dataframe(lista_sla, use_container_width=True, hide_index=True)
            else:
                st.success("🎉 Nenhuma pendência! O estoque está 100% limpo.")

            # --- RELATÓRIO DO PERÍODO ---
            st.markdown("---")
            st.subheader("📋 Resumo do Período (Copiar e Colar)")
            hoje_str = hoje_dt.strftime("%d/%m/%Y")
            texto_relatorio = f"📊 *RELATÓRIO DE COLETAS ({filtro_inicio.strftime('%d/%m')} até {filtro_fim.strftime('%d/%m')})*\n\n"
            
            texto_relatorio += f"✅ *COLETAS FINALIZADAS:* {len(coletadas_periodo)} nota(s)\n"
            if coletadas_periodo:
                agrupado_coletadas = {}
                for d in coletadas_periodo:
                    t = d["Transportadora"]
                    agrupado_coletadas.setdefault(t, []).append(f"Nº {d['Nota']} ({d['QTD']} vol)")
                for transp, notas in agrupado_coletadas.items():
                    texto_relatorio += f"\n🚛 *{transp}* ({len(notas)}):\n   ↳ {', '.join(notas)}\n"
            else:
                texto_relatorio += "Nenhuma coleta no período.\n"
                
            texto_relatorio += "\n" + "-"*30 + "\n\n"
            
            texto_relatorio += f"⏳ *PENDÊNCIAS NA FILIAL AGORA:* {len(pendentes_gerais)} nota(s) aguardando\n"
            if pendentes_gerais:
                agrupado_pendentes = {}
                for d in pendentes_gerais:
                    t = d["Transportadora"]
                    urg = "[URGENTE] " if "URGENTE" in d["Prioridade"] else ""
                    agrupado_pendentes.setdefault(t, []).append(f"{urg}Nº {d['Nota']} ({d['QTD']} vol - emissão: {d['Data_Emissao_Nota']} - req: {d['Data_Solicitacao']})")
                for transp, notas in agrupado_pendentes.items():
                    texto_relatorio += f"\n⚠️ *{transp}* ({len(notas)}):\n"
                    for n in notas:
                        texto_relatorio += f"   ↳ {n}\n"
            
            st.text_area("Texto Copiável:", value=texto_relatorio, height=300)
            
            # --- EXPORTAR ---
            st.markdown("---")
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["Transportadora", "QTD", "Nota", "Data_Solicitacao", "Data_Coleta", "Data_Emissao_Nota", "Usuario_Lancamento", "Prioridade", "Usuario_Baixa"])
            writer.writeheader()
            writer.writerows(dados)
            csv_bytes = output.getvalue().encode('utf-8')
            st.download_button(
                label="📥 Baixar Histórico Completo em Excel (CSV)",
                data=csv_bytes,
                file_name=f"auditoria_coletas_{hoje_str.replace('/','-')}.csv",
                mime="text/csv",
                use_container_width=True
            )

# ==========================================
# ABA 3: CONSULTA RÁPIDA
# ==========================================
with aba3:
    st.markdown("### 🔍 Pesquisa & Rastreabilidade")
    nota_busca = st.text_input("Digite o Número da Nota:")
    
    if st.button("Procurar Nota", use_container_width=True):
        if nota_busca:
            with st.spinner("Buscando rastros..."):
                dados = obter_dados_gerais()
                encontradas = [d for d in dados if d["Nota"] == nota_busca.strip()]
                
                if encontradas:
                    for nota in encontradas:
                        status = "✅ Já Coletada" if nota["Data_Coleta"] != "" else "⏳ Aguardando"
                        cor_status = "#d4edda" if nota["Data_Coleta"] != "" else "#fff3cd"
                        cor_texto = "#155724" if nota["Data_Coleta"] != "" else "#856404"
                        
                        st.markdown(f"""
                        <div style="background-color: {cor_status}; color: {cor_texto}; padding: 15px; border-radius: 10px; margin-top: 10px;">
                            <h4 style="margin-top:0;">{ '🚨 ' if 'URGENTE' in nota['Prioridade'] else ''}Nota: {nota['Nota']}</h4>
                            <b>Status:</b> {status}<br>
                            <b>Transportadora:</b> {nota['Transportadora']}<br>
                            <b>QTD Volumes:</b> {nota['QTD']}<br>
                            <b>Emissão (NFe):</b> {nota['Data_Emissao_Nota']}<br>
                            <hr style="border-top: 1px solid {cor_texto}; opacity: 0.3;">
                            <b>Lançado em:</b> {nota['Data_Solicitacao']} <i>(Por: {nota['Usuario_Lancamento']})</i><br>
                            <b>Baixado em:</b> {nota['Data_Coleta'] if nota['Data_Coleta'] != "" else "-"} <i>(Por: {nota['Usuario_Baixa']})</i>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.error("❌ Nota não encontrada no banco de dados.")

# ==========================================
# ABA 4: GERENCIAR E COBRAR
# ==========================================
with aba4:
    st.markdown("### ⚙️ Corrigir, Excluir ou Re-cobrar")
    nota_alvo = st.text_input("Digite a Nota Fiscal para gerenciar:")
    
    if st.button("Buscar Registro", use_container_width=True):
        if nota_alvo:
            dados = obter_dados_gerais()
            encontradas = [d for d in dados if d["Nota"] == nota_alvo.strip()]
            if encontradas:
                st.session_state['nota_gerenciar'] = encontradas[0]
            else:
                st.error("❌ Nota não encontrada.")
                if 'nota_gerenciar' in st.session_state: del st.session_state['nota_gerenciar']
                        
    if 'nota_gerenciar' in st.session_state:
        n = st.session_state['nota_gerenciar']
        st.info(f"Gerenciando Nota: **{n['Nota']}** ({n['Transportadora']})")
        
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔔 Enviar Lembrete (Re-cobrar)", use_container_width=True):
                if n["Transportadora"] == "FL":
                    st.warning("⚠️ Cobre a FL via Teams!")
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
                except Exception as e:
                    st.error(f"Erro: {e}")
