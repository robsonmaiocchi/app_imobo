import json
import os
import re
import sqlite3
import time
from datetime import datetime
from typing import List, Optional
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# =====================================================================
# 1. BANCO DE DADOS (SQLite v6 - Clean UI & Regra "Faz Sentido?")
# =====================================================================
DB_FILE = "crm_imobiliaria_v6.db"
CHAVE_EMBARCADA = "COLE_SUA_CHAVE_AIzaSy_AQUI"

IMOVEIS_INICIAIS = [
    {
        "codigo": "8212",
        "titulo": "Gaia Cabral",
        "cidade_bairro": "Curitiba - Cabral",
        "modalidade": "Pronto para Morar",
        "valor": 922700.00,
        "entrada_condicoes": "2Q (68/74m²) R$ 922.700 | 3Q R$ 1.136.400. Aceita proposta/permuta.",
        "previsao_entrega": "Pronto",
        "quartos": 3,
        "vagas_garagem": 2,
        "aceita_pet": 1,
        "aceita_fgts": 0,
        "descricao": "Unidades promocionais de 2 e 3 dormitórios no Cabral com decorados prontos."
    },
    {
        "codigo": "CTBA-1650",
        "titulo": "Reserva Juvevê High End",
        "cidade_bairro": "Curitiba - Juvevê / Cabral",
        "modalidade": "Alto Padrão Pronto",
        "valor": 1680000.00,
        "entrada_condicoes": "Fechamento rápido até Dezembro. Estuda permuta.",
        "previsao_entrega": "Imediata",
        "quartos": 3,
        "vagas_garagem": 3,
        "aceita_pet": 1,
        "aceita_fgts": 0,
        "descricao": "3 suítes, 148m² privativos, churrasqueira a carvão, pronto para morar."
    },
    {
        "codigo": "8094",
        "titulo": "Hera Botânica - Cristo Rei",
        "cidade_bairro": "Curitiba - Cristo Rei",
        "modalidade": "Lançamento Clube",
        "valor": 888800.00,
        "entrada_condicoes": "Entrada parcelada + Financiamento / FGTS",
        "previsao_entrega": "Dez/2027",
        "quartos": 2,
        "vagas_garagem": 1,
        "aceita_pet": 1,
        "aceita_fgts": 1,
        "descricao": "70 m², 2 quartos (1 suíte), a 3 min do Jardim Botânico."
    },
    {
        "codigo": "CTBA-350",
        "titulo": "Parque das Araucárias",
        "cidade_bairro": "Curitiba - Capão Raso",
        "modalidade": "Na Planta / FGTS",
        "valor": 345000.00,
        "entrada_condicoes": "Entrada em 48x + Uso total de FGTS",
        "previsao_entrega": "Ago/2027",
        "quartos": 2,
        "vagas_garagem": 1,
        "aceita_pet": 1,
        "aceita_fgts": 1,
        "descricao": "2 quartos com sacada e churrasqueira, condomínio clube completo."
    },
    {
        "codigo": "CTBA-101",
        "titulo": "Horizon Água Verde",
        "cidade_bairro": "Curitiba - Água Verde",
        "modalidade": "Lançamento",
        "valor": 780000.00,
        "entrada_condicoes": "Entrada c/ FGTS + 36x na obra",
        "previsao_entrega": "Dez/2027",
        "quartos": 3,
        "vagas_garagem": 2,
        "aceita_pet": 1,
        "aceita_fgts": 1,
        "descricao": "3 quartos (1 suíte), varanda gourmet a carvão, próximo à Praça do Japão."
    }
]

LEADS_EXEMPLO = [
    ("Ana Rosset", "(41) 99111-2233", "MORNO", 1136400.0, "Cabral", "Cristo Rei",
     "Casa em condomínio de R$ 2,2M (saiu da Especiale) p/ angariar ou permutar",
     "Depende da venda/permuta da casa",
     "8212 - Gaia Cabral, 8094 - Cristo Rei",
     "8212 (Gaia Cabral Promocional)",
     "Avalia 2 aptos de 3Q no Gaia Cabral mediante permuta/venda de sua casa de R$ 2,2M. Não quer Cristo Rei.",
     "ATENDIMENTO", datetime.now().strftime("%Y-%m-%d %H:%M"), "WhatsApp", "Hoje às 17:00"),
    
    ("Rose Miguel", "(49) 98503-3656", "MORNO", 350000.0, "Curitiba", "Nenhum",
     "Não possui", "Médio prazo",
     "8094 - Hera Botânica (Acima do bolso)",
     "CTBA-350 (Parque das Araucárias - R$ 345k)",
     "Veio do anúncio do Hera (888k), mas tem R$ 350 mil. IA já separou opção de R$ 345k.",
     "REENGAJAR", "2026-10-14 14:00", "Instagram", "14/10 (ATRASADO)"),
    
    ("Cliente Alto Padrão (Áudio)", "(41) 99888-5544", "QUENTE", 1800000.0, "Cabral, Juvevê", "Nenhum",
     "Compra direta", "Urgente (Até Dezembro)",
     "Acima de 2M",
     "CTBA-1650 (Reserva Juvevê - R$ 1,68M)",
     "Mandou áudio buscando imóvel pronto até Dezembro na faixa de R$ 1,5M a R$ 1,8M.",
     "VISITA", datetime.now().strftime("%Y-%m-%d %H:%M"), "Áudio WhatsApp", "Agendar visita")
]

def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS imoveis (
            codigo TEXT PRIMARY KEY, titulo TEXT, cidade_bairro TEXT, modalidade TEXT,
            valor REAL, entrada_condicoes TEXT, previsao_entrega TEXT, quartos INTEGER,
            vagas_garagem INTEGER, aceita_pet INTEGER, aceita_fgts INTEGER, descricao TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT UNIQUE,
            temperatura TEXT, orcamento_max REAL, bairros_interesse TEXT,
            bairros_descartados TEXT, oportunidade_permuta_captacao TEXT,
            prazo_urgencia TEXT, imoveis_ja_mostrados TEXT, imoveis_sugeridos_ia TEXT,
            resumo_historico TEXT, coluna_kanban TEXT, ultima_interacao TEXT,
            origem TEXT, data_retorno TEXT
        )
    """)
    c.execute("SELECT COUNT(*) FROM imoveis")
    if c.fetchone()[0] == 0:
        for im in IMOVEIS_INICIAIS:
            c.execute("INSERT INTO imoveis VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(im.values()))
    c.execute("SELECT COUNT(*) FROM leads")
    if c.fetchone()[0] == 0:
        c.executemany("""
            INSERT INTO leads (
                nome, telefone, temperatura, orcamento_max, bairros_interesse,
                bairros_descartados, oportunidade_permuta_captacao, prazo_urgencia,
                imoveis_ja_mostrados, imoveis_sugeridos_ia, resumo_historico,
                coluna_kanban, ultima_interacao, origem, data_retorno
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, LEADS_EXEMPLO)
    conn.commit()
    conn.close()

def carregar_imoveis() -> List[dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.cursor().execute("SELECT * FROM imoveis").fetchall()]
    conn.close()
    return rows

def carregar_leads() -> List[dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.cursor().execute("SELECT * FROM leads ORDER BY ultima_interacao DESC").fetchall()]
    conn.close()
    return rows

def salvar_lead_escuta_whatsapp(dados_ia: 'ExtracaoEscutaWhatsApp'):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    mostrados_str = ", ".join(dados_ia.imoveis_ja_mostrados_pelo_corretor) if dados_ia.imoveis_ja_mostrados_pelo_corretor else "Nenhum"
    sugeridos_str = ", ".join([f"{m.codigo_imovel} ({m.compatibilidade_percentual}%)" for m in dados_ia.imoveis_sugeridos_do_catalogo])
    bairros_str = ", ".join(dados_ia.bairros_interesse) if dados_ia.bairros_interesse else "Aberto"
    descartados_str = ", ".join(dados_ia.bairros_descartados) if dados_ia.bairros_descartados else "Nenhum"
    permuta_str = dados_ia.possui_imovel_permuta_ou_venda or "Não possui"

    c.execute("SELECT id FROM leads WHERE telefone = ?", (dados_ia.telefone_cliente,))
    if c.fetchone():
        c.execute("""
            UPDATE leads SET nome=?, temperatura=?, orcamento_max=?, bairros_interesse=?,
            bairros_descartados=?, oportunidade_permuta_captacao=?, prazo_urgencia=?,
            imoveis_ja_mostrados=?, imoveis_sugeridos_ia=?, resumo_historico=?,
            coluna_kanban=?, ultima_interacao=?, data_retorno=? WHERE telefone=?
        """, (dados_ia.nome_cliente, dados_ia.temperatura_lead, dados_ia.orcamento_identificado,
              bairros_str, descartados_str, permuta_str, dados_ia.prazo_urgencia_compra,
              mostrados_str, sugeridos_str, dados_ia.resumo_do_que_conversaram,
              dados_ia.coluna_kanban_automatica, agora, dados_ia.proximo_passo_ou_agenda, dados_ia.telefone_cliente))
    else:
        c.execute("""
            INSERT INTO leads (
                nome, telefone, temperatura, orcamento_max, bairros_interesse,
                bairros_descartados, oportunidade_permuta_captacao, prazo_urgencia,
                imoveis_ja_mostrados, imoveis_sugeridos_ia, resumo_historico,
                coluna_kanban, ultima_interacao, origem, data_retorno
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'WhatsApp',?)
        """, (dados_ia.nome_cliente, dados_ia.telefone_cliente, dados_ia.temperatura_lead,
              dados_ia.orcamento_identificado, bairros_str, descartados_str, permuta_str,
              dados_ia.prazo_urgencia_compra, mostrados_str, sugeridos_str,
              dados_ia.resumo_do_que_conversaram, dados_ia.coluna_kanban_automatica, agora, dados_ia.proximo_passo_ou_agenda))
    conn.commit()
    conn.close()

def mover_card_kanban(lead_id: int, nova_coluna: str, nova_temp: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    if nova_temp:
        c.execute("UPDATE leads SET coluna_kanban=?, temperatura=?, ultima_interacao=?, data_retorno='Hoje' WHERE id=?", (nova_coluna, nova_temp, agora, lead_id))
    else:
        c.execute("UPDATE leads SET coluna_kanban=?, ultima_interacao=? WHERE id=?", (nova_coluna, agora, lead_id))
    conn.commit()
    conn.close()

# =====================================================================
# 2. UTILITÁRIOS VISUAIS
# =====================================================================
def formatar_moeda_br(valor: Optional[float]) -> str:
    if valor is None:
        return "A definir"
    return f"R$ {valor:,.0f}".replace(",", ".")

def badge_temperatura(temp: str) -> str:
    t = (temp or "NEUTRO").upper()
    cores = {
        "QUENTE": ("#fee2e2", "#dc2626", "🔴 Quente"),
        "MORNO": ("#ffedd5", "#ea580c", "🟠 Morno"),
        "FRIO": ("#e0f2fe", "#0284c7", "🩵 Frio"),
        "CONGELADO": ("#dbeafe", "#1d4ed8", "🔵 Congelado"),
        "NEUTRO": ("#f1f5f9", "#475569", "⚪ Neutro"),
    }
    bg, txt, label = cores.get(t, ("#f1f5f9", "#475569", f"⚪ {t}"))
    return f"<span style='background:{bg}; color:{txt}; padding:3px 10px; border-radius:99px; font-weight:600; font-size:0.78rem;'>{label}</span>"

def sanitizar_markdown_whatsapp(texto: str) -> str:
    if not texto:
        return ""
    return re.sub(r'(?<!\*)\*([^\*\n]+)\*(?!\*)', r'**\1**', texto.replace("$", r"\$"))

# =====================================================================
# 3. SCHEMAS PYDANTIC (COM A REGRA DO "FAZ SENTIDO?")
# =====================================================================
class MatchEmpreendimento(BaseModel):
    codigo_imovel: str = Field(description="Código do imóvel (ex: 8212, CTBA-1650, CTBA-350, CTBA-101).")
    compatibilidade_percentual: int = Field(description="Nota de 0 a 100.")
    motivo_para_mostrar_agora: str = Field(description="Por que este imóvel encaixa no perfil do cliente.")

class ExtracaoEscutaWhatsApp(BaseModel):
    nome_cliente: str = Field(description="Nome do cliente.")
    telefone_cliente: str = Field(description="Telefone do cliente.")
    temperatura_lead: str = Field(description="'QUENTE', 'MORNO', 'FRIO', 'CONGELADO' ou 'NEUTRO'.")
    coluna_kanban_automatica: str = Field(description="'NOVOS', 'ATENDIMENTO', 'REENGAJAR' ou 'VISITA'.")
    orcamento_identificado: Optional[float] = Field(description="Orçamento máximo em R$.")
    bairros_interesse: List[str] = Field(description="Bairros desejados.")
    bairros_descartados: List[str] = Field(description="Bairros que o cliente NÃO deseja.")
    possui_imovel_permuta_ou_venda: Optional[str] = Field(description="Descrição se possui imóvel para permuta ou venda/captação.")
    prazo_urgencia_compra: str = Field(description="Prazo desejado (ex: 'Até Dezembro').")
    imoveis_ja_mostrados_pelo_corretor: List[str] = Field(description="Imóveis já mostrados na conversa.")
    resumo_do_que_conversaram: str = Field(description="Resumo executivo curto e direto.")
    proximo_passo_ou_agenda: str = Field(description="Próximo passo combinado.")
    imoveis_sugeridos_do_catalogo: List[MatchEmpreendimento] = Field(description="Imóveis recomendados do catálogo.")
    sugestao_proxima_resposta_corretor: str = Field(
        description="Mensagem de WhatsApp elegante, consultiva e curta para a corretora enviar agora. OBRIGATÓRIO terminar com uma pergunta usando a expressão 'Faz sentido para você?' ou 'Faz sentido dentro do que você busca?'."
    )

class AnaliseAtendimento(BaseModel):
    resposta_whatsapp: str = Field(
        description="Mensagem para o cliente. OBRIGATÓRIO finalizar com uma pergunta consultiva usando 'Faz sentido para você?'."
    )
    imoveis_recomendados: List[str] = Field(description="Códigos recomendados.")
    temperatura_lead: str = Field(description="'QUENTE', 'MORNO', 'FRIO', 'CONGELADO' ou 'NEUTRO'.")
    orcamento_identificado: Optional[float] = Field(description="Valor máximo em R$.")
    bairros_interesse: List[str] = Field(description="Bairros mencionados.")
    resumo_para_corretor: str = Field(description="Resumo executivo.")

class MensagemReativacao(BaseModel):
    mensagem_personalizada: str = Field(
        description="Mensagem de WhatsApp curta e natural apresentando o imóvel e finalizando obrigatoriamente com 'Faz sentido para você?' ou 'Faz sentido agendarmos uma visita?'."
    )
    motivo_do_match: str = Field(description="Explicação curta do match.")

# =====================================================================
# 4. DESIGN SYSTEM PREMIUM (MODO CLEAN SAAS IGUAL A APP DE IPHONE)
# =====================================================================
st.set_page_config(page_title="Pâmela Maioki | Smart CRM", page_icon="✨", layout="wide")

if "db_iniciado_v6" not in st.session_state:
    inicializar_banco()
    st.session_state.db_iniciado_v6 = True

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    /* Esconde menus técnicos do Streamlit para parecer App Nativo */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1280px !important;
    }

    /* Header Estilo App Imobiliário Clean (Azul Royal & Branco) */
    .top-bar {
        background: linear-gradient(135deg, #1e40af 0%, #2563eb 100%);
        color: white;
        padding: 18px 22px;
        border-radius: 16px;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.25);
        margin-bottom: 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
    }
    .top-bar-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .top-bar-sub {
        font-size: 0.82rem;
        opacity: 0.9;
        margin: 2px 0 0 0;
    }
    .status-pill {
        background: rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(6px);
        padding: 6px 14px;
        border-radius: 99px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #ffffff;
        border: 1px solid rgba(255,255,255,0.25);
    }

    /* Cartões Clean Flutuantes */
    .clean-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
        color: #0f172a;
    }
    .clean-card-match {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 4px solid #2563eb;
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 10px;
        color: #0f172a;
    }

    /* Alertas Elegantes */
    .banner-atraso {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-left: 5px solid #dc2626;
        color: #991b1b;
        padding: 12px 16px;
        border-radius: 12px;
        margin-bottom: 16px;
        font-size: 0.88rem;
    }
    .banner-permuta {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-left: 5px solid #d97706;
        color: #92400e;
        padding: 12px 14px;
        border-radius: 12px;
        margin-bottom: 12px;
        font-size: 0.86rem;
    }

    /* Pílulas de Informação */
    .pill-gray {
        background: #f1f5f9;
        color: #334155;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.76rem;
        font-weight: 500;
        display: inline-block;
        margin: 2px 4px 2px 0;
    }
    .pill-blue {
        background: #eff6ff;
        color: #1d4ed8;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.76rem;
        font-weight: 600;
        display: inline-block;
        margin: 2px 4px 2px 0;
    }
    .pill-red {
        background: #fef2f2;
        color: #b91c1c;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.76rem;
        font-weight: 600;
        display: inline-block;
        margin: 2px 4px 2px 0;
    }

    /* Abas Estilo Pílula Moderna */
    button[data-baseweb="tab"] {
        border-radius: 10px !important;
        padding: 8px 14px !important;
        margin-right: 4px !important;
    }
    button[data-baseweb="tab"] p {
        font-weight: 600 !important;
        font-size: 0.86rem !important;
    }

    /* Botões Arredondados */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.15s ease-in-out !important;
    }

    /* Responsividade Mobile Refinada */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 3.2rem !important; /* Desce o cartão azul para não cortar o 'Olá, Pâmela' */
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        .top-bar {
            padding: 14px 16px;
            border-radius: 12px;
        }
        .top-bar-title {
            font-size: 1.05rem;
        }
        h2, h3 {
            font-size: 1rem !important;
        }
        .stButton > button {
            font-size: 0.80rem !important;
            padding: 0.45rem 0.6rem !important;
            white-space: normal !important;
            height: auto !important;
        }
    }
</style>
""", unsafe_allow_html=True)

MODELOS_DISPONIVEIS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-omni-1.2-flash",
]

def obter_chave_api() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY") or CHAVE_EMBARCADA

with st.sidebar:
    st.markdown("### 👤 Perfil da Corretora")
    st.caption("**Pâmela Maioki** • Curitiba / PR")
    chave_auto = obter_chave_api()
    if chave_auto and chave_auto != "COLE_SUA_CHAVE_AIzaSy_AQUI":
        api_key_input = chave_auto
        st.success("🟢 WhatsApp Espelhado Ativo")
    else:
        api_key_input = st.text_input("🔑 Chave da API:", type="password")
    modelo_selecionado = "gemini-3.5-flash-lite"
    if st.button("🔄 Restaurar Exemplos", use_container_width=True):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        inicializar_banco()
        st.session_state.ultima_escuta = None
        st.rerun()

# =====================================================================
# 5. MOTOR DE IA (COM GATILHO "FAZ SENTIDO?" EMBARCADO)
# =====================================================================
def chamar_gemini_estruturado(conteudos, schema_pydantic, system_prompt: str, chave_api: str, modelo_primario: str):
    if not chave_api:
        raise ValueError("Configure a GEMINI_API_KEY nas Secrets.")
    client = genai.Client(api_key=chave_api.strip(), http_options=types.HttpOptions(timeout=12000))
    fila_modelos = [modelo_primario] + [m for m in MODELOS_DISPONIVEIS if m != modelo_primario]
    config_geracao = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=schema_pydantic,
        temperature=0.2,
    )
    ultimo_erro = None
    for modelo in fila_modelos:
        try:
            response = client.models.generate_content(model=modelo, contents=conteudos, config=config_geracao)
            return schema_pydantic.model_validate_json(response.text), modelo
        except Exception as e:
            ultimo_erro = e
            time.sleep(0.3)
            continue
    raise RuntimeError(f"Oscilação na rede: {ultimo_erro}")

def analisar_conversa_whatsapp_espelhada(dialogo_texto: str, arquivo_audio, chave_api: str, modelo_primario: str) -> tuple[ExtracaoEscutaWhatsApp, str]:
    catalogo_json = json.dumps(carregar_imoveis(), ensure_ascii=False)
    prompt_sistema = f"""
    Você é o assistente invisível de CRM da corretora Pâmela Maioki.
    Analise a conversa ou áudio do WhatsApp e preencha o CRM sozinho.
    REGRAS CRÍTICAS:
    1. Detecte oportunidades de Permuta ou Captação/Angariação da casa atual do cliente (ex: 2.2M).
    2. Anote bairros rejeitados (ex: Cristo Rei) em `bairros_descartados` e nunca recomende imóveis lá.
    3. REGRA DE OURO DE FECHAMENTO DA PÂMELA: Na `sugestao_proxima_resposta_corretor`, escreva uma mensagem super natural de WhatsApp apresentando a solução e SEMPRE termine com uma frase consultiva usando **"Faz sentido para você?"** (ex: "Faz sentido agendarmos uma visita rápida para você conhecer?", "Faz sentido essa configuração para a sua família?").
    CATÁLOGO: {catalogo_json}
    """
    partes = []
    if arquivo_audio is not None:
        partes.append(types.Part.from_bytes(data=arquivo_audio.read(), mime_type=arquivo_audio.type or "audio/ogg"))
        partes.append(types.Part.from_text(text="Extraia os dados deste áudio e gere a resposta terminando com 'Faz sentido?'."))
    if dialogo_texto.strip():
        partes.append(types.Part.from_text(text=f"Conversa:\n{dialogo_texto}"))
    return chamar_gemini_estruturado(partes, ExtracaoEscutaWhatsApp, prompt_sistema, chave_api, modelo_primario)

# =====================================================================
# 6. CABEÇALHO CLEAN E NAVEGAÇÃO
# =====================================================================
st.markdown("""
<div class="top-bar">
    <div>
        <p class="top-bar-title">Olá, Pâmela Maioki 👋</p>
        <p class="top-bar-sub">Seu Copiloto & Funil Automático • Paulo Celles Imóveis</p>
    </div>
    <div class="status-pill">🟢 WhatsApp Conectado • Tempo Resposta: 2s</div>
</div>
""", unsafe_allow_html=True)

aba_escuta, aba_kanban, aba_chat, aba_match, aba_roi = st.tabs([
    "✨ 1. Auto-CRM",
    "📋 2. Seu Funil",
    "💬 3. Super-Dory",
    "🎯 4. Match Carteira",
    "📊 5. Seu Dia"
])

# ---------------------------------------------------------------------
# ABA 1: AUTO-CRM CLEAN
# ---------------------------------------------------------------------
with aba_escuta:
    col_in, col_out = st.columns([1, 1.15], gap="large")

    with col_in:
        st.markdown("##### 📱 Conversa ou Áudio Recebido no WhatsApp")
        st.caption("Toque em um atendimento real abaixo para testar:")
        
        c1, c2, c3 = st.columns(3)
        if c1.button("🏡 Ana Rosset (2.2M)", use_container_width=True):
            st.session_state.dialogo_wpp = (
                "Cliente: Ana Rosset | Tel: (41) 99111-2233\n"
                "[Pâmela]: Oi Ana! Te enviei os vídeos do Gaia Cabral (ID 8212), 2Q a partir de R$ 922.700 e 3Q R$ 1.136.400.\n"
                "[Ana Rosset]: Tenho uma casa nova em condomínio avaliada em 2.6 mi, vou anunciar por 2.2 mi. Pedi pra Especiale excluir o anúncio de locação pois queremos vender. Teria que ver se aceitam permuta por 2 aptos de 3 quartos ou esperar vender.\n"
                "[Pâmela]: Vamos colocar sua casa à venda aqui na Paulo Celles? Também saiu lançamento no Cristo Rei.\n"
                "[Ana Rosset]: Ainda não vendi minha casa. Não desejo bairro Cristo Rei."
            )
        if c2.button("🎙️ Áudio (1.8M Dez)", use_container_width=True):
            st.session_state.dialogo_wpp = (
                "Cliente: Comprador Alto Padrão | Tel: (41) 99888-5544\n"
                "[Áudio no WhatsApp]: Oi Pâmela, boa noite! Tô em busca de comprar algo até dezembro. O que eu busco tá entre 1 milhão e meio e 1 milhão e 800 no máximo, tá bom? Se tiver dentro disso pode me mandar."
            )
        if c3.button("💬 Rafael (3Q FGTS)", use_container_width=True):
            st.session_state.dialogo_wpp = (
                "Cliente: Rafael Souza | Tel: (41) 99234-5678\n"
                "[Pâmela]: Oi Rafael! Te mandei o Hera Botânica (ID 8094) de 2 quartos.\n"
                "[Rafael]: Oi Pâmela! 2 quartos fica apertado. Precisamos de 3 quartos até R$ 800 mil no Água Verde usando nosso FGTS."
            )

        dialogo_input = st.text_area(
            "Histórico capturado:",
            value=st.session_state.get("dialogo_wpp", ""),
            height=155,
            label_visibility="collapsed",
            placeholder="Toque em um dos clientes acima ou cole uma conversa..."
        )
        audio_escuta = st.file_uploader("🎙️ Ou envie o áudio do cliente (.ogg, .mp3):", type=["ogg", "mp3", "wav"])

        if st.button("✨ Atualizar Ficha & Gerar Resposta", type="primary", use_container_width=True):
            if not dialogo_input.strip() and audio_escuta is None:
                st.warning("Selecione um dos exemplos acima primeiro.")
            else:
                with st.spinner("Montando card e preparando mensagem..."):
                    try:
                        dados_escuta, _ = analisar_conversa_whatsapp_espelhada(dialogo_input, audio_escuta, api_key_input, modelo_selecionado)
                        st.session_state.ultima_escuta = dados_escuta
                        salvar_lead_escuta_whatsapp(dados_escuta)
                        st.toast("Card atualizado no Funil!", icon="✅")
                    except Exception as e:
                        st.error(f"Erro: {e}")

    with col_out:
        st.markdown("##### 🗂️ Card do Cliente (Preenchido Sozinho)")
        if "ultima_escuta" in st.session_state and st.session_state.ultima_escuta:
            esc: ExtracaoEscutaWhatsApp = st.session_state.ultima_escuta
            
            permuta_html = ""
            if esc.possui_imovel_permuta_ou_venda and esc.possui_imovel_permuta_ou_venda.lower() not in ["não", "nao", "nenhum", "null", "none", "não possui"]:
                permuta_html = f"<div class='banner-permuta'>🔄 <strong>Oportunidade de Permuta / Angariação:</strong> {esc.possui_imovel_permuta_ou_venda}</div>"

            proibidos_html = ""
            if esc.bairros_descartados:
                proibidos_html = f"<span class='pill-red'>🚫 Não oferecer: {', '.join(esc.bairros_descartados)}</span>"

            mostrados_html = "".join([f"<span class='pill-gray'>👁️ Já viu: {m}</span>" for m in esc.imoveis_ja_mostrados_pelo_corretor])

            st.markdown(f"""
            <div class="clean-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:1.1rem; font-weight:700;">👤 {esc.nome_cliente}</span>
                    {badge_temperatura(esc.temperatura_lead)}
                </div>
                <div style="font-size:0.82rem; color:#64748b; margin-bottom:12px;">
                    📱 {esc.telefone_cliente} &nbsp;•&nbsp; ⏳ <strong>{esc.prazo_urgencia_compra}</strong> &nbsp;•&nbsp; 📌 Funil: <strong>{esc.coluna_kanban_automatica}</strong>
                </div>
                {permuta_html}
                <div style="display:flex; gap:12px; margin-bottom:10px; flex-wrap:wrap;">
                    <span class="pill-blue">💰 Teto: {formatar_moeda_br(esc.orcamento_identificado)}</span>
                    <span class="pill-blue">📍 Busca: {', '.join(esc.bairros_interesse) if esc.bairros_interesse else 'Aberto'}</span>
                    {proibidos_html}
                </div>
                <div style="margin-bottom:10px;">{mostrados_html}</div>
                <div style="background:#f8fafc; padding:10px 12px; border-radius:10px; font-size:0.85rem; color:#334155;">
                    📝 <strong>Resumo:</strong> {esc.resumo_do_que_conversaram}
                </div>
            </div>
            """, unsafe_allow_html=True)

            imoveis_cat = carregar_imoveis()
            for sug in esc.imoveis_sugeridos_do_catalogo:
                im_d = next((i for i in imoveis_cat if i["codigo"] == sug.codigo_imovel), None)
                tit = f"{im_d['titulo']} ({formatar_moeda_br(im_d['valor'])})" if im_d else sug.codigo_imovel
                st.markdown(f"""
                <div class="clean-card-match">
                    <strong>🎯 Sugestão da IA: ID {sug.codigo_imovel} — {tit}</strong>
                    <span style="float:right; color:#2563eb; font-weight:700; font-size:0.82rem;">{sug.compatibilidade_percentual}% Match</span><br>
                    <span style="font-size:0.82rem; color:#475569;">💡 {sug.motivo_para_mostrar_agora}</span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("**📲 Mensagem Pronta c/ Gatilho *'Faz sentido?'* (Toque para copiar):**")
            st.code(esc.sugestao_proxima_resposta_corretor, language=None)
        else:
            st.markdown("""
            <div class="clean-card" style="text-align:center; padding:32px 16px; color:#64748b;">
                👈 Toque em <strong>🏡 Ana Rosset (2.2M)</strong> ou <strong>🎙️ Áudio (1.8M Dez)</strong> e clique no botão azul para ver o card limpo e a resposta com o gatilho <em>"Faz sentido?"</em>.
            </div>
            """, unsafe_allow_html=True)

# ---------------------------------------------------------------------
# ABA 2: FUNIL KANBAN CLEAN
# ---------------------------------------------------------------------
with aba_kanban:
    leads_totais = carregar_leads()
    agora_dt = datetime.now()
    col_novos, col_atendimento, col_reengajar, col_visita = [], [], [], []
    retornos_vencidos = []

    for l in leads_totais:
        try:
            dt_lead = datetime.strptime(l["ultima_interacao"], "%Y-%m-%d %H:%M")
            dias_parado = int((agora_dt - dt_lead).total_seconds() // 86400)
        except Exception:
            dias_parado = 0
        l["dias_para_perder"] = max(0, 30 - dias_parado)

        if "ATRASADO" in (l.get("data_retorno") or "") or dias_parado >= 2:
            retornos_vencidos.append(l)

        st_col = (l.get("coluna_kanban") or "ATENDIMENTO").upper()
        if st_col == "VISITA" or l["temperatura"] == "QUENTE":
            col_visita.append(l)
        elif st_col == "REENGAJAR" or dias_parado >= 2:
            col_reengajar.append(l)
        elif st_col == "NOVOS":
            col_novos.append(l)
        else:
            col_atendimento.append(l)

    if retornos_vencidos:
        nomes_v = ", ".join([f"{r['nome']} ({r['data_retorno']})" for r in retornos_vencidos])
        st.markdown(f"""
        <div class="banner-atraso">
            🔔 <strong>Lembrete de Retornos Pendentes:</strong> {nomes_v}
        </div>
        """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4, gap="medium")

    def desenhar_card_kanban(item: dict):
        proib = f"<span class='pill-red'>🚫 {item['bairros_descartados']}</span>" if item.get("bairros_descartados") not in [None, "", "Nenhum"] else ""
        perm = f"<div style='font-size:0.75rem; color:#b45309; background:#fef3c7; padding:4px 8px; border-radius:6px; margin:4px 0;'>🔄 {item['oportunidade_permuta_captacao']}</div>" if item.get("oportunidade_permuta_captacao") not in [None, "", "Não possui", "Compra direta"] else ""
        st.markdown(f"""
        <div class="clean-card" style="padding:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:0.95rem;">{item['nome']}</strong>
                {badge_temperatura(item['temperatura'])}
            </div>
            <div style="font-size:0.76rem; color:#64748b; margin:4px 0 8px 0;">📱 {item['telefone']} • 📅 {item.get('data_retorno')}</div>
            <div style="margin-bottom:6px;">
                <span class="pill-blue">💰 {formatar_moeda_br(item['orcamento_max'])}</span>
                <span class="pill-gray">📍 {item['bairros_interesse']}</span>
                {proib}
            </div>
            {perm}
            <div style="font-size:0.76rem; color:#334155; margin-top:6px;">
                👁️ <strong>Viu:</strong> {item.get('imoveis_ja_mostrados')}<br>
                🎯 <strong>Sugerido:</strong> <span style="color:#1d4ed8; font-weight:600;">{item.get('imoveis_sugeridos_ia')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with k1:
        st.markdown(f"##### 📥 Novos ({len(col_novos)})")
        for item in col_novos:
            desenhar_card_kanban(item)
            if st.button("Atender ➡️", key=f"k1_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO")
                st.rerun()

    with k2:
        st.markdown(f"##### 💬 Em Atendimento ({len(col_atendimento)})")
        for item in col_atendimento:
            desenhar_card_kanban(item)
            b1, b2 = st.columns(2)
            if b1.button("📅 Visita", key=f"k2v_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "VISITA", "QUENTE")
                st.rerun()
            if b2.button("⏳ Atrasar", key=f"k2r_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "REENGAJAR", "FRIO")
                st.rerun()

    with k3:
        st.markdown(f"##### 🔄 Reengajar ({len(col_reengajar)})")
        for item in col_reengajar:
            desenhar_card_kanban(item)
            st.caption(f"🛡️ Proteção Roleta: faltam **{item['dias_para_perder']} dias**")
            if st.button("✨ Reengajar c/ IA", key=f"k3_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO", "MORNO")
                st.rerun()

    with k4:
        st.markdown(f"##### 🏆 Visita / Proposta ({len(col_visita)})")
        for item in col_visita:
            desenhar_card_kanban(item)
            if st.button("⏪ Voltar", key=f"k4_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO", "MORNO")
                st.rerun()

# ---------------------------------------------------------------------
# ABA 3: SUPER-DORY (COM O "FAZ SENTIDO?")
# ---------------------------------------------------------------------
with aba_chat:
    st.markdown("##### 💬 Pré-Atendimento Inteligente (Pivota Orçamento e finaliza com *'Faz sentido?'*)")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    cb1, cb2, cb3 = st.columns(3)
    msg_atalho = None
    if cb1.button("1️⃣ Clicou no Hera (888k)", use_container_width=True):
        msg_atalho = "Olá! Vi o anúncio do Hera Botânica (ID 8094) no Cristo Rei."
    if cb2.button("2️⃣ 'Só tenho 350 mil'", use_container_width=True):
        msg_atalho = "Será que compro algo bom em Curitiba? Eu tenho 350 mil."
    if cb3.button("🧹 Limpar", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    chat_box = st.container(height=340, border=True)
    input_wpp = st.chat_input("Escreva como cliente...")
    texto_enviado = msg_atalho or input_wpp

    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(sanitizar_markdown_whatsapp(msg["content"]))
        if texto_enviado:
            st.session_state.messages.append({"role": "user", "content": texto_enviado})
            with st.chat_message("user"):
                st.markdown(sanitizar_markdown_whatsapp(texto_enviado))
            with st.chat_message("assistant"):
                with st.spinner("Respondendo..."):
                    catalogo_str = json.dumps(carregar_imoveis(), ensure_ascii=False)
                    sis_chat = (
                        f"Você é a assistente da corretora Pâmela. Catálogo: {catalogo_str}. "
                        "Se o cliente tiver orçamento menor (ex: 350 mil), ofereça o CTBA-350 (R$ 345 mil) na hora! "
                        "SEMPRE finalize sua resposta com uma pergunta usando 'Faz sentido para você?'."
                    )
                    conteudos = [types.Content(role="user" if m["role"]=="user" else "model", parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages]
                    analise_wpp, _ = chamar_gemini_estruturado(conteudos, AnaliseAtendimento, sis_chat, api_key_input, modelo_selecionado)
                    st.markdown(sanitizar_markdown_whatsapp(analise_wpp.resposta_whatsapp))
                    st.session_state.messages.append({"role": "assistant", "content": analise_wpp.resposta_whatsapp})

# ---------------------------------------------------------------------
# ABA 4: MATCH DA CARTEIRA
# ---------------------------------------------------------------------
with aba_match:
    st.markdown("##### 🎯 Cruzamento Inteligente de Lançamentos")
    leads_s = carregar_leads()
    imoveis_a = carregar_imoveis()
    opcoes = {f"{im['titulo']} • {im['cidade_bairro']} ({formatar_moeda_br(im['valor'])})": im for im in imoveis_a}
    escolha = st.selectbox("Selecione o Imóvel:", list(opcoes.keys()))
    imovel_alvo = opcoes[escolha]

    for lead_m in leads_s:
        descartados_lead = (lead_m.get("bairros_descartados") or "").lower()
        bairro_proibido = any(b.strip() in imovel_alvo["cidade_bairro"].lower() for b in descartados_lead.split(",") if len(b.strip()) > 2 and b.strip() != "nenhum")
        orc_ok = (lead_m["orcamento_max"] is None) or (lead_m["orcamento_max"] * 1.25 >= imovel_alvo["valor"] and lead_m["orcamento_max"] * 0.4 <= imovel_alvo["valor"])
        if orc_ok and not bairro_proibido:
            st.markdown(f"""
            <div class="clean-card">
                <strong>👤 {lead_m['nome']}</strong> {badge_temperatura(lead_m['temperatura'])}<br>
                <span style="font-size:0.82rem; color:#475569;">💰 Teto: {formatar_moeda_br(lead_m['orcamento_max'])} • 👁️ Já viu: {lead_m.get('imoveis_ja_mostrados')}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"📲 Gerar abordagem p/ {lead_m['nome']}", key=f"m_{lead_m['id']}"):
                p_sis = "Crie uma mensagem curta de WhatsApp ofertando este imóvel e termine obrigatoriamente perguntando 'Faz sentido para você?'."
                p_usr = f"Cliente: {json.dumps(lead_m, ensure_ascii=False)} | Imóvel: {json.dumps(imovel_alvo, ensure_ascii=False)}"
                res_m, _ = chamar_gemini_estruturado(p_usr, MensagemReativacao, p_sis, api_key_input, modelo_selecionado)
                st.code(res_m.mensagem_personalizada, language=None)

# ---------------------------------------------------------------------
# ABA 5: SEU DIA & DASHBOARD
# ---------------------------------------------------------------------
with aba_roi:
    leads_g = carregar_leads()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Novos + Recontatos", f"{len(leads_g)} ativos", "+100% via WhatsApp")
    d2.metric("Tempo 1ª Resposta", "2 seg", "-9.9 min vs antigo")
    d3.metric("Captação / Permuta", "R$ 2,2 Mi", "Casa Ana Rosset")
    d4.metric("Visitas / Quentes", f"{sum(1 for l in leads_g if l.get('coluna_kanban')=='VISITA')}", "Prontos p/ fechar")