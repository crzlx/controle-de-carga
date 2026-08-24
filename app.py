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

# Link Base do Google Sheets (Fonte Única de Dados)
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


@st.cache_data(ttl=30, show_spinner=False)
def obter_dados_gerais():
    """Conecta à planilha base e puxa todos os registros das abas."""
    planilha = conectar_planilha()
    dados = []
    for transp in TRANSPORTADORAS:
        try:
            aba = planilha.worksheet(transp)
            linhas = aba.get_all_values()[1:]  # Ignora o cabeçalho

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
            st.error(f"❌ Aba '{transp}' não encontrada no Google Sheets.")
        except Exception as e:
            st.error(f"❌ Erro ao ler dados da aba {transp}: {e}")

    return dados


try:
    dados_globais = obter_dados_gerais()
except Exception as e:
    st.error(f"Erro de conexão com a planilha base: {e}")
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
                        DADOS DE CARGAS PENDENTES HOJE (PUXADOS DA PLANILHA BASE): {json.dumps(pendentes, ensure_ascii=False)}
                        HISTÓRICO RECENTE: {historico}
                        Responda à pergunta do usuário de forma útil e direta: "{nova_msg}"
                        """
                        resposta = modelo.generate_content(prompt)
                        st.markdown(resposta.text)
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": resposta.text}
                        )

                    except Exception as e:
                        st.error(f"❌ Ocorreu um erro na IA: {e}")


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
            "Registrar Nota na Planilha Base", use_container_width=True
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

                    # Grava a nova linha diretamente no Google Sheets
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
                    st.success(f"✅ Nota {nota_nova} gravada na planilha base!")

                    obter_dados_gerais.clear()

                    if transp_nova == "FL":
                        st.info(
                            "💻 **ATENÇÃO:** O aviso para a FL deve ser enviado"
                            " via Teams!"
                        )
                    elif transp_nova == "JARBAS":
                        st.info(
                            "🚛 **ATENÇÃO:** A Jarbas acompanha em tempo real"
                            " pela planilha!"
                        )
                    else:
                        resultado_email = disparar_email_silencioso(
                            transp_nova,
                            nota_nova,
                            qtd,
                            prioridade=prioridade,
                        )
                        if resultado_email:
                            st.info(f"📧 E-mail disparado para {transp_nova}.")

                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar na planilha: {e}")

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
                f"📦 **Notas pendentes na planilha ({transp_baixa}):**"
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
                    with st.spinner("Atualizando planilha base..."):
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

                            st.success("✅ Baixas sincronizadas na planilha!")

                            obter_dados_gerais.clear()
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar planilha: {e}")
    else:
        st.success(f"🎉 Nenhuma pendência encontrada para {transp_baixa}.")

elif aba_selecionada == "📊 Painel & Relatórios":
    st.markdown("### 📊 Dashboard Analítico (Dados em Tempo Real)")
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
            with st.spinner("Processando dados da planilha..."):
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

                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.metric("📦 Separadas no Período", len(lancadas_periodo))
                c2.metric("✅ Coletadas no Período", len(coletadas_periodo))
                c3.metric("⏳ Pendentes Hoje", len(pendentes_gerais))

                st.markdown("---")
                st.subheader("📋 Resumo do Período")
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

                st.text_area(
                    "Texto Copiável:", value=texto_relatorio, height=250
                )

elif aba_selecionada == "🔍 Consulta Rápida":
    st.markdown("### 🔍 Pesquisa & Rastreabilidade")
    nota_busca = st.text_input("Digite o Número da Nota:", autocomplete="off")
    if st.button("Procurar na Planilha Base", use_container_width=True):
        if nota_busca:
            encontradas = [
                d for d in dados_globais if d["Nota"] == nota_busca.strip()
            ]
            if encontradas:
                for nota in encontradas:
                    status = (
                        "✅ Já Coletada"
                        if nota["Data_Coleta"] != ""
                        else "⏳ Aguardando Coleta"
                    )
                    st.info(
                        f"**Nota:** {nota['Nota']} | **Status:** {status} |"
                        f" **Transportadora:** {nota['Transportadora']} |"
                        f" **Destino:** {nota['Cidade_Destino']}"
                    )
            else:
                st.error("❌ Nota não encontrada na planilha base.")

elif aba_selecionada == "⚙️ Editar/Excluir":
    st.markdown("### ⚙️ Alterar Registro na Planilha Base")
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
                st.error("❌ Nota não encontrada na planilha.")

    if "nota_gerenciar" in st.session_state:
        n = st.session_state["nota_gerenciar"]
        st.info(
            f"Registro Localizado: **{n['Nota']}** ({n['Transportadora']})"
        )

        with st.form("form_editar_nota"):
            novo_qtd = st.text_input("QTD (Volumes)", value=n["QTD"])
            nova_cidade = st.text_input(
                "Cidade Destino", value=n.get("Cidade_Destino", "-")
            )
            btn_salvar = st.form_submit_button("💾 Salvar Alterações")

            if btn_salvar:
                planilha = conectar_planilha()
                aba = planilha.worksheet(n["Transportadora"])
                celula = aba.find(n["Nota"])
                if celula:
                    aba.update_cell(celula.row, 1, novo_qtd)
                    aba.update_cell(celula.row, 9, nova_cidade)
                    st.success("✅ Atualizado diretamente na planilha!")
                    obter_dados_gerais.clear()
                    time.sleep(2)
                    st.rerun()

elif aba_selecionada == "🔔 Cobrar Atrasos":
    st.markdown("### 🔔 Gestão de Pendências da Planilha")
    pendentes = [d for d in dados_globais if d["Data_Coleta"] == ""]
    if not pendentes:
        st.success("🎉 Todas as cargas da planilha foram coletadas!")
    else:
        st.write(f"Total de cargas pendentes na base: **{len(pendentes)}**")
        for p in pendentes:
            st.write(
                f"- **[{p['Transportadora']}] Nota {p['Nota']}** | Vol:"
                f" {p['QTD']} | Destino: {p['Cidade_Destino']} | Solicitado:"
                f" {p['Data_Solicitacao']}"
            )
