import csv
import io
import json
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import google.generativeai as genai
import gspread
import pandas as pd
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Coletas Speedmax", page_icon="🚚", layout="wide")

# Link Base da Planilha no Google Sheets
PLANILHA_URL = "https://docs.google.com/spreadsheets/d/1zjiGtrzY64rJQnU3DdxqivFtgUPxb_YsC-1PBFC2MsU/edit?usp=sharing"

TRANSPORTADORAS = ["JARBAS", "TRANSCHERRER", "FL", "GENEROSO"]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": (
                "Olá! Sou o Alessandro IA. Como posso ajudar com a expedição,"
                " dúvidas com clientes ou rotina do galpão hoje?"
            ),
        }
    ]

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


def disparar_email_silencioso(
    transportadora, nota, qtd, lembrete=False, prioridade="Normal"
):
    try:
        remetente = st.secrets["EMAIL_REMETENTE"]
        senha = st.secrets["SENHA_EMAIL"]
        emails_destino = {
            "TRANSCHERRER": (
                "filial.campos@transcherrer.com.br,"
                " cidy.neves@transcherrer.com.br,"
                " filial.campos02@transcherrer.com.br"
            ),
            "GENEROSO": "Encarregado.cgo@generoso.com.br",
        }
        destinatario = emails_destino.get(transportadora)
        if destinatario and "teste.com" not in destinatario.lower():
            msg = EmailMessage()
            urgencia_tag = "[URGENTE] " if "URGENTE" in prioridade else ""
            tipo_aviso = (
                "LEMBRETE URGENTE: Coleta Pendente"
                if lembrete
                else "Nova Coleta Liberada"
            )
            msg["Subject"] = (
                f"{urgencia_tag}{tipo_aviso} - Speedmax (Nota: {nota})"
            )
            msg["From"] = remetente
            msg["To"] = destinatario
            corpo_email = (
                f"Olá, equipe da {transportadora}!\n\n"
                f"{'Este é um LEMBRETE de que temos' if lembrete else 'Temos uma nova'}"
                " mercadoria separada aguardando coleta na filial Speedmax.\n\n"
                f"DETALHES:\n- Nota Fiscal: {nota}\n- Volumes: {qtd}\n\n"
                "Por favor, programem a retirada o mais rápido possível.\n\n"
                "Logística Speedmax."
            )
            msg.set_content(corpo_email)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(remetente, senha)
                smtp.send_message(msg)
            return True
        return False
    except Exception:
        return False


def conectar_planilha():
    escopo = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    cred_dict = json.loads(st.secrets["google_credentials"])
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(
        cred_dict, escopo
    )
    cliente = gspread.authorize(credenciais)
    return cliente.open_by_url(PLANILHA_URL)


def parse_data(data_str):
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").date()
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def obter_dados_gerais():
    planilha = conectar_planilha()
    dados = []
    for transp in TRANSPORTADORAS:
        try:
            aba = planilha.worksheet(transp)
            linhas = aba.get_all_values()[1:]

            for l in linhas:
                while len(l) < 11:
                    l.append("")

                nota = str(l[1]).strip()
                if nota != "":
                    dados.append({
                        "Transportadora": transp,
                        "QTD": l[0].strip(),
                        "Nota": nota,
                        "Data_Solicitacao": l[2].strip(),
                        "Data_Coleta": l[3].strip(),
                        "Data_Emissao_Nota": l[4].strip(),
                        "Usuario_Lancamento": (
                            l[5].strip() if l[5].strip() else "-"
                        ),
                        "Prioridade": (
                            l[6].strip() if l[6].strip() else "Normal"
                        ),
                        "Usuario_Baixa": (
                            l[7].strip() if l[7].strip() else "-"
                        ),
                        "Cidade_Destino": (
                            l[8].strip() if l[8].strip() else "-"
                        ),
                        "Hora_Solicitacao": (
                            l[9].strip() if l[9].strip() else "-"
                        ),
                        "Hora_Coleta": l[10].strip() if l[10].strip() else "-",
                    })
        except gspread.exceptions.WorksheetNotFound:
            st.error(
                f"❌ Aba não encontrada no Google Sheets: '{transp}'. Verifique"
                " se o nome tem espaços ocultos."
            )
        except Exception as e:
            st.error(f"❌ Erro ao ler dados da transportadora {transp}: {e}")

    return dados


try:
    dados_globais = obter_dados_gerais()
except Exception as e:
    st.error(f"Erro ao conectar com o Google Sheets: {e}")
    dados_globais = []


@st.dialog("🤖 Chat com Alessandro IA")
def abrir_chat_ia(dados_para_ia):
    box_chat = st.container(height=400)
    with box_chat:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if nova_msg := st.chat_input(
        "Pergunte sobre logística, vendas, transportadoras..."
    ):
        st.session_state.chat_history.append(
            {"role": "user", "content": nova_msg}
        )
        with box_chat:
            with st.chat_message("user"):
                st.markdown(nova_msg)
            with st.chat_message("assistant"):
                with st.spinner("Analisando..."):
                    try:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        modelo = genai.GenerativeModel("gemini-1.5-flash")

                        hoje = datetime.now().strftime("%d/%m/%Y")
                        pendentes = [
                            d for d in dados_para_ia if d["Data_Coleta"] == ""
                        ]
                        historico = "\n".join([
                            f"{m['role']}: {m['content']}"
                            for m in st.session_state.chat_history[-4:]
                        ])

                        prompt = f"""
                        Você é o Alessandro IA, assistente logístico avançado e versátil da Speedmax (Campos dos Goytacazes). Hoje é {hoje}.
                        Você ajuda com o galpão, vendas, clientes e redação profissional.
                        DADOS DE CARGAS PENDENTES HOJE: {json.dumps(pendentes, ensure_ascii=False)}
                        HISTÓRICO RECENTE: {historico}
                        Responda à pergunta do usuário de forma útil e direta: "{nova_msg}"
                        """
                        resposta = modelo.generate_content(prompt)
                        st.markdown(resposta.text)
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": resposta.text}
                        )

                    except Exception as e:
                        erro_str = str(e).lower()
                        if (
                            "429" in erro_str
                            or "quota" in erro_str
                            or "exhausted" in erro_str
                        ):
                            erro_msg = (
                                "⏳ **Muitas mensagens rápidas da equipe!** O"
                                " limite do plano gratuito ativou o modo de"
                                " segurança. Por favor, espere **1 minutinho**"
                                " e mande a mensagem de novo!"
                            )
                        else:
                            erro_msg = f"❌ Ocorreu um erro na IA: {e}"

                        st.error(erro_msg)
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": erro_msg}
                        )


with st.sidebar:
    st.header("👤 Operador")
    usuario_atual = st.selectbox(
        "Identificação:", ["Pedro", "Alessandro", "Outro"]
    )
    st.markdown("---")
    if st.button("💬 Falar com Alessandro IA", use_container_width=True):
        abrir_chat_ia(dados_globais)
    st.markdown("---")
    st.link_button(
        "📊 Abrir Planilha Base (Google Sheets)",
        PLANILHA_URL,
        use_container_width=True,
    )

st.title("🚚 Expedição Campos Dos Goytacazes")

opcoes_abas = [
    "📦 Movimentação",
    "📊 Painel & Relatórios",
    "🔍 Consulta Rápida",
    "⚙️ Editar/Excluir",
    "🔔 Cobrar Atrasos",
]


def limpar_memoria_aba():
    if "nota_gerenciar" in st.session_state:
        del st.session_state["nota_gerenciar"]


aba_selecionada = st.radio(
    "Navegação:",
    opcoes_abas,
    horizontal=True,
    label_visibility="collapsed",
    on_change=limpar_memoria_aba,
)

st.markdown("---")

id_animacao = abs(hash(aba_selecionada))
st.markdown(
    f"""
<div id="marcador-{id_animacao}"></div>
<style>
@keyframes slideInAba_{id_animacao} {{
    from {{ opacity: 0; transform: translateY(15px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
div.element-container:has(#marcador-{id_animacao}) ~ div.element-container {{
    animation: slideInAba_{id_animacao} 0.4s cubic-bezier(0.25, 1, 0.5, 1) forwards;
}}
</style>
""",
    unsafe_allow_html=True,
)

if aba_selecionada == "📦 Movimentação":
    st.header("📝 Lançar Nova Solicitação")
    st.markdown(f"Lançamento registrado por: **{usuario_atual}**.")
    with st.form("form_nova", clear_on_submit=True):
        col_t, col_p = st.columns([2, 1])
        with col_t:
            transp_nova = st.selectbox(
                "Transportadora", TRANSPORTADORAS, key="t1"
            )
        with col_p:
            prioridade = st.selectbox("Prioridade", ["Normal", "🚨 URGENTE"])
        col1, col2 = st.columns(2)
        with col1:
            qtd = st.number_input("QTD (Volumes)", min_value=1, step=1)
            data_solicitacao = st.date_input(
                "Data da Solicitação", format="DD/MM/YYYY"
            )
            cidade_destino = st.text_input("Cidade Destino", autocomplete="off")
        with col2:
            nota_nova = st.text_input("Nota (Nº)", autocomplete="off")
            data_emissao = st.date_input(
                "Data de Emissão da Nota", format="DD/MM/YYYY"
            )
        enviar_nova = st.form_submit_button(
            "Registrar Nota", use_container_width=True
        )

        if enviar_nova:
            if nota_nova.strip() == "" or cidade_destino.strip() == "":
                st.warning(
                    "⚠️ Preencha obrigatoriamente o número da Nota e a Cidade"
                    " Destino."
                )
            else:
                try:
                    fuso_br = timezone(timedelta(hours=-3))
                    hora_atual = datetime.now(fuso_br).strftime("%H:%M")

                    planilha = conectar_planilha()
                    aba_sel = planilha.worksheet(transp_nova)
                    formatada_solicitacao = data_solicitacao.strftime(
                        "%d/%m/%Y"
                    )
                    formatada_emissao = data_emissao.strftime("%d/%m/%Y")

                    aba_sel.append_row([
                        qtd,
                        nota_nova,
                        formatada_solicitacao,
                        "",
                        formatada_emissao,
                        usuario_atual,
                        prioridade,
                        "",
                        cidade_destino,
                        hora_atual,
                        "",
                    ])
                    st.success(f"✅ Nota {nota_nova} registrada!")

                    obter_dados_gerais.clear()

                    if transp_nova == "FL":
                        st.info(
                            "💻 **ATENÇÃO:** O aviso para a FL deve ser enviado"
                            " via Teams!"
                        )
                    elif transp_nova == "JARBAS":
                        st.info(
                            "🚛 **ATENÇÃO:** A Jarbas já acompanha essa nova"
                            " coleta em tempo real pelo Painel Espelho!"
                        )
                    else:
                        resultado_email = disparar_email_silencioso(
                            transp_nova,
                            nota_nova,
                            qtd,
                            prioridade=prioridade,
                        )
                        if resultado_email is True:
                            st.info(f"📧 E-mail disparado para {transp_nova}.")
                        else:
                            st.warning("⚠️ E-mail não configurado.")

                    time.sleep(4)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro no banco de dados: {e}")

    st.markdown("---")
    st.header("✅ Confirmar Coleta em Lote")

    opcoes_baixa = ["Todos"] + TRANSPORTADORAS
    transp_baixa = st.selectbox(
        "Transportadora (Baixa)", opcoes_baixa, key="t2"
    )

    if transp_baixa == "Todos":
        pendentes_transp = [
            d for d in dados_globais if d["Data_Coleta"] == ""
        ]
    else:
        pendentes_transp = [
            d
            for d in dados_globais
            if d["Transportadora"] == transp_baixa and d["Data_Coleta"] == ""
        ]

    if pendentes_transp:
        with st.form("form_baixa"):
            st.markdown(
                f"📦 **Notas pendentes na expedição ({transp_baixa}):**"
            )
            checkboxes_notas = {}
            for p in pendentes_transp:
                prefixo_urg = "🚨 " if "URGENTE" in p["Prioridade"] else ""
                label = (
                    f"[{p['Transportadora']}] {prefixo_urg}Nº {p['Nota']} —"
                    f" {p['QTD']} volumes (Sol: {p['Data_Solicitacao']})"
                )
                checkboxes_notas[p["Nota"]] = st.checkbox(label)
            st.markdown("---")
            data_coleta = st.date_input(
                "Data da Coleta Real", format="DD/MM/YYYY"
            )
            enviar_baixa = st.form_submit_button(
                f"Confirmar Baixa (Registrar como {usuario_atual})",
                use_container_width=True,
            )

            if enviar_baixa:
                notas_selecionadas = [
                    nota
                    for nota, marcada in checkboxes_notas.items()
                    if marcada
                ]
                if not notas_selecionadas:
                    st.warning("⚠️ Marque pelo menos uma nota.")
                else:
                    with st.spinner("Sincronizando..."):
                        try:
                            fuso_br = timezone(timedelta(hours=-3))
                            hora_baixa_atual = datetime.now(fuso_br).strftime(
                                "%H:%M"
                            )

                            planilha = conectar_planilha()
                            coleta_formatada = data_coleta.strftime("%d/%m/%Y")
                            for nota in notas_selecionadas:
                                info_nota = next(
                                    item
                                    for item in pendentes_transp
                                    if item["Nota"] == nota
                                )
                                transp_nota = info_nota["Transportadora"]
                                aba_sel = planilha.worksheet(transp_nota)
                                celula = aba_sel.find(nota)

                                aba_sel.update_cell(
                                    celula.row, 4, coleta_formatada
                                )
                                aba_sel.update_cell(
                                    celula.row, 8, usuario_atual
                                )
                                aba_sel.update_cell(
                                    celula.row, 11, hora_baixa_atual
                                )

                            st.success(
                                "✅ Baixa confirmada perfeitamente às"
                                f" {hora_baixa_atual}!"
                            )

                            obter_dados_gerais.clear()
                            time.sleep(4)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro na sincronização: {e}")
    else:
        st.success(f"🎉 Expedição limpa para a {transp_baixa}.")

elif aba_selecionada == "📊 Painel & Relatórios":
    st.markdown("### 📊 Dashboard Analítico")
    with st.expander("📅 Filtrar Dados por Período", expanded=True):
        c_ini, c_fim = st.columns(2)
        filtro_inicio = c_ini.date_input(
            "Data Inicial", value=None, format="DD/MM/YYYY"
        )
        filtro_fim = c_fim.date_input(
            "Data Final", value=None, format="DD/MM/YYYY"
        )

    if st.button("🔄 Gerar Análises do Período", use_container_width=True):
        if not filtro_inicio or not filtro_fim:
            st.warning("⚠️ Selecione as datas Inicial e Final.")
        else:
            with st.spinner("Processando..."):
                hoje_dt = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                lancadas_periodo, coletadas_periodo, pendentes_gerais = (
                    [],
                    [],
                    [],
                )
                tempos_coleta = {t: [] for t in TRANSPORTADORAS}

                for d in dados_globais:
                    dt_sol = parse_data(d["Data_Solicitacao"])
                    dt_col = parse_data(d["Data_Coleta"])
                    if dt_sol and filtro_inicio <= dt_sol <= filtro_fim:
                        lancadas_periodo.append(d)
                    if (
                        d["Data_Coleta"] != ""
                        and dt_col
                        and filtro_inicio <= dt_col <= filtro_fim
                    ):
                        coletadas_periodo.append(d)
                    if d["Data_Coleta"] == "":
                        pendentes_gerais.append(d)
                    if d["Data_Coleta"] != "" and dt_sol and dt_col:
                        dias_demora = (dt_col - dt_sol).days
                        if dias_demora >= 0:
                            tempos_coleta[d["Transportadora"]].append(
                                dias_demora
                            )

                pendentes_gerais = sorted(
                    pendentes_gerais,
                    key=lambda x: 0 if "URGENTE" in x["Prioridade"] else 1,
                )

                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.metric("📦 Separadas no Período", len(lancadas_periodo))
                c2.metric("✅ Coletadas no Período", len(coletadas_periodo))
                c3.metric("⏳ Pendentes Hoje", len(pendentes_gerais))

                st.markdown("---")
                st.subheader("🏆 Ranking de Agilidade (Média Histórica)")
                ranking_dados = []
                for transp, tempos in tempos_coleta.items():
                    media = (
                        sum(tempos) / len(tempos) if tempos else "Sem dados"
                    )
                    ranking_dados.append({
                        "Transportadora": transp,
                        "Dias para Coleta": (
                            round(media, 1)
                            if isinstance(media, (int, float))
                            else media
                        ),
                    })

                ranking_dados.sort(
                    key=lambda x: (
                        x["Dias para Coleta"]
                        if isinstance(x["Dias para Coleta"], float)
                        else 999
                    )
                )
                cols_rank = st.columns(4)
                for idx, r in enumerate(ranking_dados):
                    with cols_rank[idx]:
                        st.info(
                            f"**{r['Transportadora']}**\n\nTempo:"
                            f" {r['Dias para Coleta']}"
                            f" {'dias' if isinstance(r['Dias para Coleta'], float) else ''}"
                        )

                st.markdown("---")
                st.subheader("🚛 Fila de Aguardo")
                if pendentes_gerais:
                    lista_sla = []
                    for p in pendentes_gerais:
                        item = {
                            "Transportadora": p["Transportadora"],
                            "Nota": p["Nota"],
                            "QTD": p["QTD"],
                            "Prioridade": (
                                "🚨 URGENTE"
                                if "URGENTE" in p["Prioridade"]
                                else "Normal"
                            ),
                        }
                        try:
                            data_sol_dt = datetime.strptime(
                                p["Data_Solicitacao"], "%d/%m/%Y"
                            )
                            dias_parado = (hoje_dt - data_sol_dt).days
                            if dias_parado == 0:
                                item["Atraso"] = "🟢 Hoje"
                            elif dias_parado == 1:
                                item["Atraso"] = "🟡 1 dia"
                            elif dias_parado > 1:
                                item["Atraso"] = f"🔴 {dias_parado} dias"
                            else:
                                item["Atraso"] = "🟢 Hoje"
                        except Exception:
                            item["Atraso"] = "⚪ N/A"
                        lista_sla.append(item)
                    st.dataframe(
                        lista_sla, use_container_width=True, hide_index=True
                    )
                else:
                    st.success("🎉 Nenhuma pendência!")

                st.markdown("---")
                st.subheader("📋 Resumo do Período (Copiar e Colar)")
                texto_relatorio = (
                    "📊 *RELATÓRIO DE COLETAS"
                    f" ({filtro_inicio.strftime('%d/%m')} até"
                    f" {filtro_fim.strftime('%d/%m')})*\n\n✅ *COLETAS"
                    f" FINALIZADAS:* {len(coletadas_periodo)} nota(s)\n"
                )
                if coletadas_periodo:
                    agrupado_coletadas = {}
                    for d in coletadas_periodo:
                        agrupado_coletadas.setdefault(
                            d["Transportadora"], []
                        ).append(f"Nº {d['Nota']} ({d['QTD']} vol)")
                    for transp, notas in agrupado_coletadas.items():
                        texto_relatorio += (
                            f"\n🚛 *{transp}* ({len(notas)}):\n  ↳"
                            f" {', '.join(notas)}\n"
                        )
                else:
                    texto_relatorio += "Nenhuma coleta.\n"
                texto_relatorio += (
                    "\n"
                    + "-" * 30
                    + f"\n\n⏳ *PENDÊNCIAS AGORA:* {len(pendentes_gerais)}"
                    " nota(s)\n"
                )
                if pendentes_gerais:
                    agrupado_pendentes = {}
                    for d in pendentes_gerais:
                        agrupado_pendentes.setdefault(
                            d["Transportadora"], []
                        ).append(
                            f"{'[URGENTE] ' if 'URGENTE' in d['Prioridade'] else ''}Nº"
                            f" {d['Nota']} ({d['QTD']} vol - emissão:"
                            f" {d['Data_Emissao_Nota']} - req:"
                            f" {d['Data_Solicitacao']})"
                        )
                    for transp, notas in agrupado_pendentes.items():
                        texto_relatorio += f"\n⚠️ *{transp}* ({len(notas)}):\n"
                        for n in notas:
                            texto_relatorio += f"    ↳ {n}\n"

                st.text_area(
                    "Texto Copiável:", value=texto_relatorio, height=300
                )

                output = io.StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=[
                        "Transportadora",
                        "QTD",
                        "Nota",
                        "Data_Solicitacao",
                        "Data_Coleta",
                        "Data_Emissao_Nota",
                        "Usuario_Lancamento",
                        "Prioridade",
                        "Usuario_Baixa",
                        "Cidade_Destino",
                        "Hora_Solicitacao",
                        "Hora_Coleta",
                    ],
                )
                writer.writeheader()
                writer.writerows(dados_globais)
                st.download_button(
                    "📥 Baixar Histórico em CSV",
                    data=output.getvalue().encode("utf-8"),
                    file_name="relatorio.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

elif aba_selecionada == "🔍 Consulta Rápida":
    st.markdown("### 🔍 Pesquisa & Rastreabilidade")
    nota_busca = st.text_input("Digite o Número da Nota:", autocomplete="off")
    if st.button("Procurar Nota", use_container_width=True):
        if nota_busca:
            with st.spinner("Buscando rastros..."):
                encontradas = [
                    d for d in dados_globais if d["Nota"] == nota_busca.strip()
                ]
                if encontradas:
                    for nota in encontradas:
                        status = (
                            "✅ Já Coletada"
                            if nota["Data_Coleta"] != ""
                            else "⏳ Aguardando"
                        )
                        cor_status, cor_texto = (
                            ("#d4edda", "#155724")
                            if nota["Data_Coleta"] != ""
                            else ("#fff3cd", "#856404")
                        )

                        hora_sol_info = (
                            f" às {nota.get('Hora_Solicitacao', '-')}"
                            if nota.get("Hora_Solicitacao", "-") != "-"
                            else ""
                        )
                        hora_col_info = (
                            f" às {nota.get('Hora_Coleta', '-')}"
                            if nota.get("Hora_Coleta", "-") != "-"
                            else ""
                        )

                        st.markdown(
                            f"""
                        <div style="background-color: {cor_status}; color: {cor_texto}; padding: 15px; border-radius: 10px; margin-top: 10px;">
                            <h4 style="margin-top:0;">{'🚨 ' if 'URGENTE' in nota['Prioridade'] else ''}Nota: {nota['Nota']}</h4>
                            <b>Status:</b> {status}<br><b>Transportadora:</b> {nota['Transportadora']}<br><b>Volumes:</b> {nota['QTD']}<br><b>Cidade Destino:</b> {nota['Cidade_Destino']}<br>
                            <hr style="border-top: 1px solid {cor_texto}; opacity: 0.3;">
                            <b>Lançado em:</b> {nota['Data_Solicitacao']}{hora_sol_info} <i>({nota['Usuario_Lancamento']})</i><br>
                            <b>Baixado em:</b> {nota['Data_Coleta'] if nota['Data_Coleta'] != "" else "-"}{hora_col_info} <i>({nota['Usuario_Baixa']})</i>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.error("❌ Nota não encontrada.")

elif aba_selecionada == "⚙️ Editar/Excluir":
    st.markdown("### ⚙️ Localizar, Editar ou Excluir Registro")
    nota_alvo = st.text_input(
        "Digite a Nota Fiscal para gerenciar:", autocomplete="off"
    )
    if st.button("Buscar Registro", use_container_width=True):
        if nota_alvo:
            encontradas = [
                d for d in dados_globais if d["Nota"] == nota_alvo.strip()
            ]
            if encontradas:
                st.session_state["nota_gerenciar"] = encontradas[0]
            else:
                st.error("❌ Nota não encontrada.")
                if "nota_gerenciar" in st.session_state:
                    del st.session_state["nota_gerenciar"]

    if "nota_gerenciar" in st.session_state:
        n = st.session_state["nota_gerenciar"]
        st.info(
            f"Registro Encontrado: **{n['Nota']}** ({n['Transportadora']}) -"
            f" {n['QTD']} volumes"
        )

        with st.expander(
            "✏️ Editar Informações (Atualização Interna)", expanded=True
        ):
            with st.form("form_editar_nota"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    novo_qtd = st.text_input("QTD (Volumes)", value=n["QTD"])
                    nova_prioridade = st.selectbox(
                        "Prioridade",
                        ["Normal", "🚨 URGENTE"],
                        index=0 if "Normal" in n["Prioridade"] else 1,
                    )
                    nova_cidade = st.text_input(
                        "Cidade Destino", value=n.get("Cidade_Destino", "-")
                    )
                with col_e2:
                    nova_dt_sol = st.text_input(
                        "Data Solicitação (DD/MM/AAAA)",
                        value=n["Data_Solicitacao"],
                    )
                    nova_dt_emi = st.text_input(
                        "Data Emissão da Nota (DD/MM/AAAA)",
                        value=n["Data_Emissao_Nota"],
                    )

                st.markdown(
                    "<small><i>Para alterar o número da Nota ou Transportadora,"
                    " exclua o registro e lance novamente.</i></small>",
                    unsafe_allow_html=True,
                )
                btn_salvar = st.form_submit_button(
                    "💾 Salvar Alterações na Planilha", use_container_width=True
                )

                if btn_salvar:
                    with st.spinner("Salvando alterações..."):
                        try:
                            planilha = conectar_planilha()
                            aba = planilha.worksheet(n["Transportadora"])
                            celula = aba.find(n["Nota"])
                            if celula:
                                aba.update_cell(celula.row, 1, novo_qtd)
                                aba.update_cell(celula.row, 3, nova_dt_sol)
                                aba.update_cell(celula.row, 5, nova_dt_emi)
                                aba.update_cell(celula.row, 7, nova_prioridade)
                                aba.update_cell(celula.row, 9, nova_cidade)

                                st.success(
                                    f"✅ Registro da Nota {n['Nota']} atualizado"
                                    " com sucesso!"
                                )
                                obter_dados_gerais.clear()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(
                                    "❌ Não foi possível localizar a linha"
                                    " correspondente na planilha."
                                )
                        except Exception as e:
                            st.error(f"Erro ao atualizar planilha: {e}")

        with st.expander("🗑️ Excluir Registro", expanded=False):
            st.warning(
                f"⚠️ Atenção: A exclusão da Nota **{n['Nota']}** na"
                f" transportadora **{n['Transportadora']}** é irreversível!"
            )
            if st.button(
                "❌ Confirmar Exclusão Definitiva", use_container_width=True
            ):
                with st.spinner("Excluindo registro..."):
                    try:
                        planilha = conectar_planilha()
                        aba = planilha.worksheet(n["Transportadora"])
                        celula = aba.find(n["Nota"])
                        if celula:
                            aba.delete_rows(celula.row)
                            st.success(
                                f"✅ Nota {n['Nota']} excluída com sucesso!"
                            )
                            obter_dados_gerais.clear()
                            if "nota_gerenciar" in st.session_state:
                                del st.session_state["nota_gerenciar"]
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(
                                "❌ Não foi possível localizar a nota na"
                                " planilha."
                            )
                    except Exception as e:
                        st.error(f"Erro ao excluir registro: {e}")

elif aba_selecionada == "🔔 Cobrar Atrasos":
    st.markdown("### 🔔 Gestão e Cobrança de Atrasos")
    st.markdown(
        "Monitore pendências e envie lembretes diretos para as transportadoras."
    )

    hoje_dt = datetime.now().date()
    pendentes = [d for d in dados_globais if d["Data_Coleta"] == ""]

    if not pendentes:
        st.success("🎉 Nenhuma carga pendente de coleta no momento!")
    else:
        st.info(f"📋 Total de cargas pendentes: **{len(pendentes)}**")

        por_transp = {}
        for p in pendentes:
            por_transp.setdefault(p["Transportadora"], []).append(p)

        for transp, itens in por_transp.items():
            st.markdown(
                f"#### 🚛 Transportadora: **{transp}** ({len(itens)}"
                " pendência(s))"
            )

            for item in itens:
                dt_sol = parse_data(item["Data_Solicitacao"])
                dias_atraso = (hoje_dt - dt_sol).days if dt_sol else 0
                badge = (
                    "🚨 URGENTE"
                    if "URGENTE" in item["Prioridade"]
                    else "Normal"
                )

                st.write(
                    f"- **Nota {item['Nota']}** | Vol: {item['QTD']} | Destino:"
                    f" {item['Cidade_Destino']} | Solicitado em:"
                    f" {item['Data_Solicitacao']} ({dias_atraso} dia(s)"
                    f" atrás) | Prioridade: {badge}"
                )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if transp in ["TRANSCHERRER", "GENEROSO"]:
                    if st.button(
                        f"📧 Reenviar Lembrete por E-mail ({transp})",
                        key=f"cobrar_email_{transp}",
                    ):
                        sucessos = 0
                        for item in itens:
                            if disparar_email_silencioso(
                                transp,
                                item["Nota"],
                                item["QTD"],
                                lembrete=True,
                                prioridade=item["Prioridade"],
                            ):
                                sucessos += 1
                        if sucessos > 0:
                            st.success(
                                f"✅ Lembrete disparado para {transp}"
                                f" ({sucessos} e-mail(s) enviado(s))."
                            )
                        else:
                            st.error(
                                f"❌ Não foi possível disparar e-mail para"
                                f" {transp}."
                            )
                elif transp == "FL":
                    st.info(
                        "💡 A cobrança para a **FL** deve ser realizada via"
                        " Teams."
                    )
                elif transp == "JARBAS":
                    st.info(
                        "💡 A **Jarbas** acompanha o painel em tempo real."
                    )

            with col_btn2:
                msg_cobranca = (
                    f"Olá, equipe da {transp}!\nPossuímos as seguintes coletas"
                    " pendentes em nosso galpão (Speedmax Campos):\n"
                )
                for item in itens:
                    msg_cobranca += (
                        f"• Nota: {item['Nota']} ({item['QTD']} vol) - Destino:"
                        f" {item['Cidade_Destino']}\n"
                    )
                msg_cobranca += (
                    "\nPodem nos confirmar a previsão de retirada dessas"
                    " cargas? Obrigado!"
                )

                st.text_area(
                    f"Copiar texto de cobrança ({transp}):",
                    value=msg_cobranca,
                    height=120,
                    key=f"text_cobranca_{transp}",
                )

            st.markdown("---")
