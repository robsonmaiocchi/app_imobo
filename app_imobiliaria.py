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
# 1. BANCO DE DADOS E CONFIGURAÇÃO (SQLite v8 - Enterprise BI & Gestão)
# =====================================================================
DB_FILE = "crm_imobiliaria_v8.db"
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
    
    ("Denise Morais De Oliveira", "(41) 99196-9521", "MORNO", 888800.0, "Cristo Rei", "Nenhum",
     "Não possui", "Médio prazo",
     "8094 - Hera Botânica",
     "8094 (Decorado disponível)",
     "Veio do Instagram interessada no Hera Botânica (ID 8094). Avaliando visita ao decorado.",
     "NOVOS", datetime.now().strftime("%Y-%m-%d %H:%M"), "Instagram", "Hoje às 18:30"),

    ("Rose Miguel", "(49) 98503-3656", "FRIO", 350000.0, "Curitiba", "Nenhum",
     "Não possui", "Médio prazo",
     "8094 - Hera Botânica (Acima do bolso)",
     "CTBA-350 (Parque das Araucárias - R$ 345k)",
     "Veio do anúncio do Hera (888k), mas tem R$ 350 mil. IA já separou opção de R$ 345k.",
     "REENGAJAR", "2026-10-14 14:00", "Facebook Ads", "14/10 (ATRASADO)"),
    
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
        c.execute("UPDATE leads SET coluna_kanban=?, temperatura=?, ultima_interacao=?, data_retorno='Atualizado Hoje' WHERE id=?", (nova_coluna, nova_temp, agora, lead_id))
    else:
        c.execute("UPDATE leads SET coluna_kanban=?, ultima_interacao=? WHERE id=?", (nova_coluna, agora, lead_id))
    conn.commit()
    conn.close()

# =====================================================================
# 2. UTILITÁRIOS VISUAIS PADRÃO PIPEDRIVE / HUBSPOT / CONVERTA+
# =====================================================================
def formatar_moeda_br(valor: Optional[float]) -> str:
    if valor is None or valor == 0:
        return "A definir"
    return f"R$ {valor:,.0f}".replace(",", ".")

def formatar_vgv_curto(valor: float) -> str:
    if valor >= 1_000_000:
        return f"R$ {valor/1_000_000:.2f}M".replace(".", ",")
    if valor >= 1_000:
        return f"R$ {valor/1_000:.0f}k"
    return f"R$ {valor:.0f}"

def cor_borda_temperatura(temp: str) -> str:
    t = (temp or "NEUTRO").upper()
    return {
        "QUENTE": "#ef4444",
        "MORNO": "#f97316",
        "FRIO": "#0ea5e9",
        "CONGELADO": "#3b82f6",
        "NEUTRO": "#94a3b8",
    }.get(t, "#94a3b8")

def badge_temperatura(temp: str) -> str:
    t = (temp or "NEUTRO").upper()
    cores = {
        "QUENTE": ("#fef2f2", "#dc2626", "🔴 Quente"),
        "MORNO": ("#fff7ed", "#ea580c", "🟠 Morno"),
        "FRIO": ("#f0f9ff", "#0284c7", "🩵 Frio"),
        "CONGELADO": ("#eff6ff", "#1d4ed8", "🔵 Congelado"),
        "NEUTRO": ("#f8fafc", "#475569", "⚪ Neutro"),
    }
    bg, txt, label = cores.get(t, ("#f8fafc", "#475569", f"⚪ {t}"))
    return f"<span style='background:{bg}; color:{txt}; border:1px solid {txt}33; padding:2px 8px; border-radius:99px; font-weight:600; font-size:0.72rem;'>{label}</span>"

def sanitizar_markdown_whatsapp(texto: str) -> str:
    if not texto:
        return ""
    return re.sub(r'(?<!\*)\*([^\*\n]+)\*(?!\*)', r'**\1**', texto.replace("$", r"\$"))

# =====================================================================
# 3. SCHEMAS PYDANTIC (COM GATILHO CONTEXTUAL SEM REPETIÇÃO)
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
        description="Mensagem de WhatsApp elegante, consultiva e curta para a corretora enviar agora. Finalize com uma pergunta consultiva natural como 'Faz sentido para você?'."
    )

class AnaliseAtendimento(BaseModel):
    resposta_whatsapp: str = Field(
        description="Mensagem natural para o cliente. Use 'Faz sentido para você?' APENAS quando apresentar um imóvel novo. Se o cliente já concordou ('Sim', 'Faz', 'Claro'), PROIBIDO repetir 'Faz sentido': avance convidando para ver fotos ou agendar visita!"
    )
    imoveis_recomendados: List[str] = Field(description="Códigos recomendados.")
    temperatura_lead: str = Field(description="'QUENTE', 'MORNO', 'FRIO', 'CONGELADO' ou 'NEUTRO'.")
    orcamento_identificado: Optional[float] = Field(description="Valor máximo em R$.")
    bairros_interesse: List[str] = Field(description="Bairros mencionados.")
    resumo_para_corretor: str = Field(description="Resumo executivo.")

class MensagemReativacao(BaseModel):
    mensagem_personalizada: str = Field(
        description="Mensagem de WhatsApp curta e natural apresentando o imóvel e finalizando com 'Faz sentido para você?'."
    )
    motivo_do_match: str = Field(description="Explicação curta do match.")

# =====================================================================
# 4. DESIGN SYSTEM ENTERPRISE CRM + 5 ABAS DE GESTÃO & BI
# =====================================================================
st.set_page_config(page_title="ConvertaAI Pro | CRM Imobiliário", page_icon="🏢", layout="wide")

if "db_iniciado_v8" not in st.session_state:
    inicializar_banco()
    st.session_state.db_iniciado_v8 = True

if "aba_ativa" not in st.session_state:
    st.session_state.aba_ativa = "KANBAN"

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: #f1f5f9 !important;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {
        padding-top: 2.2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 1440px !important;
    }

    /* TOPBAR ENTERPRISE */
    .crm-navbar {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-bottom: 3px solid #2563eb;
        border-radius: 12px;
        padding: 12px 20px;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 2px 4px rgba(15, 23, 42, 0.04);
        flex-wrap: wrap;
        gap: 10px;
    }
    .crm-brand {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .crm-logo-box {
        background: #2563eb;
        color: #ffffff;
        font-weight: 800;
        font-size: 0.95rem;
        padding: 7px 11px;
        border-radius: 8px;
        letter-spacing: -0.03em;
    }
    .crm-brand-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
    }
    .crm-brand-sub {
        font-size: 0.75rem;
        color: #64748b;
        margin: 0;
    }
    .crm-user-area {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .crm-badge-online {
        background: #ecfdf5;
        color: #059669;
        border: 1px solid #a7f3d0;
        padding: 4px 10px;
        border-radius: 99px;
        font-size: 0.74rem;
        font-weight: 600;
    }
    .crm-avatar {
        background: #1e293b;
        color: #ffffff;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.78rem;
        font-weight: 700;
    }

    /* FAIXA DE KPIs EXECUTIVOS */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-bottom: 14px;
    }
    .kpi-box {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-top: 3px solid #2563eb;
        border-radius: 10px;
        padding: 10px 14px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .kpi-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #64748b;
        font-weight: 600;
        margin-bottom: 2px;
    }
    .kpi-val {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
    }
    .kpi-sub {
        font-size: 0.72rem;
        color: #10b981;
        font-weight: 500;
    }

    /* BOTÕES RETANGULARES DELIMITADOS (ESTILO BOOTSTRAP) */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        padding: 0.55rem 0.6rem !important;
        border: 1px solid #94a3b8 !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05) !important;
        transition: all 0.15s ease-in-out !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: 1px solid #1e3a8a !important;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.28) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: #e2e8f0 !important;
        border-color: #64748b !important;
    }

    /* CABEÇALHO DE COLUNA DO KANBAN */
    .kanban-col-header {
        background: #e2e8f0;
        border: 1px solid #cbd5e1;
        border-top: 3px solid #2563eb;
        border-radius: 10px 10px 6px 6px;
        padding: 10px 12px;
        margin-bottom: 10px;
    }
    .kanban-col-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1e293b;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kanban-col-count {
        background: #ffffff;
        color: #0f172a;
        padding: 1px 8px;
        border-radius: 99px;
        font-size: 0.74rem;
        font-weight: 700;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
    }
    .kanban-col-vgv {
        font-size: 0.73rem;
        color: #475569;
        font-weight: 600;
        margin-top: 3px;
    }

    /* CARTÃO DE LEAD PROFISSIONAL */
    .deal-card {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(15, 23, 42, 0.04);
    }
    .deal-title {
        font-size: 0.90rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
    }
    .deal-meta {
        font-size: 0.73rem;
        color: #64748b;
        margin: 3px 0 8px 0;
    }
    .deal-price-badge {
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
        padding: 2px 7px;
        border-radius: 6px;
        font-size: 0.74rem;
        font-weight: 700;
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .deal-loc-badge {
        background: #f8fafc;
        color: #334155;
        border: 1px solid #e2e8f0;
        padding: 2px 7px;
        border-radius: 6px;
        font-size: 0.73rem;
        font-weight: 500;
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .deal-forbid-badge {
        background: #fef2f2;
        color: #b91c1c;
        border: 1px solid #fecaca;
        padding: 2px 7px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 4px;
    }
    .deal-permuta-box {
        background: #fffbeb;
        border: 1px solid #fde68a;
        color: #92400e;
        padding: 5px 8px;
        border-radius: 6px;
        font-size: 0.73rem;
        font-weight: 600;
        margin: 5px 0;
    }
    .deal-Origin-footer {
        border-top: 1px solid #f1f5f9;
        margin-top: 8px;
        padding-top: 6px;
        font-size: 0.71rem;
        color: #64748b;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .inbox-panel {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
    }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 3.3rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        .kpi-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
        .crm-navbar {
            padding: 10px 12px;
        }
        .crm-brand-title {
            font-size: 0.92rem;
        }
        .stButton > button {
            padding: 0.5rem 0.4rem !important;
            font-size: 0.75rem !important;
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
    st.markdown("### 🏢 Paulo Celles Imóveis")
    st.caption("Unidade Curitiba • Corretora: **Pâmela Maioki**")
    chave_auto = obter_chave_api()
    if chave_auto and chave_auto != "COLE_SUA_CHAVE_AIzaSy_AQUI":
        api_key_input = chave_auto
        st.success("🟢 API & WhatsApp Sincronizados")
    else:
        api_key_input = st.text_input("🔑 Chave da API:", type="password")
    modelo_selecionado = "gemini-3.5-flash-lite"
    st.divider()
    if st.button("🔄 Restaurar Base de Demonstração", use_container_width=True):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        inicializar_banco()
        st.session_state.ultima_escuta = None
        st.rerun()

# =====================================================================
# 5. MOTOR DE IA (COM GATILHO CONTEXTUAL INTELIGENTE)
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
    Você é o motor de inteligência comercial do CRM da corretora Pâmela Maioki.
    Analise a conversa ou áudio do WhatsApp e preencha o CRM sozinho.
    REGRAS CRÍTICAS:
    1. Detecte oportunidades de Permuta ou Captação/Angariação da casa atual do cliente (ex: 2.2M).
    2. Anote bairros rejeitados (ex: Cristo Rei) em `bairros_descartados` e nunca recomende imóveis lá.
    3. Na `sugestao_proxima_resposta_corretor`, escreva uma mensagem elegante de WhatsApp apresentando a solução e feche com uma pergunta consultiva como "Faz sentido para você?".
    CATÁLOGO: {catalogo_json}
    """
    partes = []
    if arquivo_audio is not None:
        partes.append(types.Part.from_bytes(data=arquivo_audio.read(), mime_type=arquivo_audio.type or "audio/ogg"))
        partes.append(types.Part.from_text(text="Extraia os dados deste áudio e gere a ficha completa."))
    if dialogo_texto.strip():
        partes.append(types.Part.from_text(text=f"Conversa:\n{dialogo_texto}"))
    return chamar_gemini_estruturado(partes, ExtracaoEscutaWhatsApp, prompt_sistema, chave_api, modelo_primario)

# =====================================================================
# 6. TOPBAR EXECUTIVA, KPIs E 5 BOTÕES DE MENU (COM GESTÃO & BI)
# =====================================================================
leads_atuais = carregar_leads()
vgv_total_pipeline = sum((l["orcamento_max"] or 0) for l in leads_atuais)
qtd_visitas = sum(1 for l in leads_atuais if (l.get("coluna_kanban") == "VISITA" or l.get("temperatura") == "QUENTE"))
qtd_atrasados = sum(1 for l in leads_atuais if "ATRASADO" in (l.get("data_retorno") or ""))

st.markdown(
    f"<div class='crm-navbar'>"
    f"<div class='crm-brand'>"
    f"<div class='crm-logo-box'>C+ AI</div>"
    f"<div>"
    f"<p class='crm-brand-title'>ConvertaAI Pro • Gestão de Funil & Escuta WhatsApp</p>"
    f"<p class='crm-brand-sub'>Paulo Celles Imóveis • Carteira: Pâmela Maioki</p>"
    f"</div>"
    f"</div>"
    f"<div class='crm-user-area'>"
    f"<span class='crm-badge-online'>● Roleta Ativa • SLA 1ª Resp: 2s</span>"
    f"<span class='crm-avatar'>PM</span>"
    f"</div>"
    f"</div>"
    f"<div class='kpi-grid'>"
    f"<div class='kpi-box' style='border-top-color:#2563eb;'>"
    f"<div class='kpi-label'>Negócios no Funil</div>"
    f"<div class='kpi-val'>{len(leads_atuais)} leads</div>"
    f"<div class='kpi-sub'>100% capturados s/ digitação</div>"
    f"</div>"
    f"<div class='kpi-box' style='border-top-color:#10b981;'>"
    f"<div class='kpi-label'>VGV em Negociação</div>"
    f"<div class='kpi-val'>{formatar_vgv_curto(vgv_total_pipeline)}</div>"
    f"<div class='kpi-sub'>Soma dos tetos qualificados</div>"
    f"</div>"
    f"<div class='kpi-box' style='border-top-color:#f59e0b;'>"
    f"<div class='kpi-label'>Oportunidade Captação</div>"
    f"<div class='kpi-val'>R$ 2,20M</div>"
    f"<div class='kpi-sub'>1 permuta/venda identificada</div>"
    f"</div>"
    f"<div class='kpi-box' style='border-top-color:#ef4444;'>"
    f"<div class='kpi-label'>Retornos / Visitas</div>"
    f"<div class='kpi-val'>{qtd_visitas} quentes • {qtd_atrasados} alerta</div>"
    f"<div class='kpi-sub'>Monitoramento anti-roleta (30d)</div>"
    f"</div>"
    f"</div>",
    unsafe_allow_html=True
)

# 5 BOTÕES DE NAVEGAÇÃO SUPERIOR (INCLUINDO GESTÃO & BI)
m1, m2, m3, m4, m5 = st.columns(5, gap="small")
if m1.button("📋 1. Kanban", type="primary" if st.session_state.aba_ativa == "KANBAN" else "secondary", use_container_width=True):
    st.session_state.aba_ativa = "KANBAN"
    st.rerun()

if m2.button("🎧 2. Inbox", type="primary" if st.session_state.aba_ativa == "INBOX" else "secondary", use_container_width=True):
    st.session_state.aba_ativa = "INBOX"
    st.rerun()

if m3.button("🤖 3. Super-Dory", type="primary" if st.session_state.aba_ativa == "DORY" else "secondary", use_container_width=True):
    st.session_state.aba_ativa = "DORY"
    st.rerun()

if m4.button("🎯 4. Match", type="primary" if st.session_state.aba_ativa == "MATCH" else "secondary", use_container_width=True):
    st.session_state.aba_ativa = "MATCH"
    st.rerun()

if m5.button("📊 5. Gestão & BI", type="primary" if st.session_state.aba_ativa == "BI" else "secondary", use_container_width=True):
    st.session_state.aba_ativa = "BI"
    st.rerun()

st.markdown("<div style='margin-bottom: 14px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# ABA 1: FUNIL KANBAN PADRÃO PIPEDRIVE / CONVERTA+
# ---------------------------------------------------------------------
if st.session_state.aba_ativa == "KANBAN":
    agora_dt = datetime.now()
    col_novos, col_atendimento, col_reengajar, col_visita = [], [], [], []
    retornos_vencidos = []

    for l in leads_atuais:
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
        st.markdown(
            f"<div style='background:#fef2f2; border:1px solid #fecaca; border-left:4px solid #dc2626; color:#991b1b; padding:9px 14px; border-radius:8px; margin-bottom:12px; font-size:0.82rem; display:flex; justify-content:space-between; align-items:center;'>"
            f"<span>🔔 <strong>Radar Anti-Roleta & Retornos Pendentes:</strong> {nomes_v}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    k1, k2, k3, k4 = st.columns(4, gap="small")

    def renderizar_header_coluna(titulo: str, lista_leads: list, cor_topo: str):
        soma_vgv = sum((x["orcamento_max"] or 0) for x in lista_leads)
        st.markdown(
            f"<div class='kanban-col-header' style='border-top-color:{cor_topo};'>"
            f"<div class='kanban-col-title'><span>{titulo}</span><span class='kanban-col-count'>{len(lista_leads)}</span></div>"
            f"<div class='kanban-col-vgv'>Potencial da etapa: {formatar_vgv_curto(soma_vgv)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    def desenhar_card_enterprise(item: dict):
        cor_esq = cor_borda_temperatura(item["temperatura"])
        proib = f"<span class='deal-forbid-badge'>🚫 {item['bairros_descartados']}</span>" if item.get("bairros_descartados") not in [None, "", "Nenhum"] else ""
        perm = f"<div class='deal-permuta-box'>🔄 Angariação/Permuta: {item['oportunidade_permuta_captacao']}</div>" if item.get("oportunidade_permuta_captacao") not in [None, "", "Não possui", "Compra direta"] else ""
        
        html_card = (
            f"<div class='deal-card' style='border-left: 4px solid {cor_esq};'>"
            f"<div style='display:flex; justify-content:space-between; align-items:flex-start; gap:4px;'>"
            f"<p class='deal-title'>{item['nome']}</p>"
            f"{badge_temperatura(item['temperatura'])}"
            f"</div>"
            f"<div class='deal-meta'>📞 {item['telefone']} • 🗓️ {item.get('data_retorno')}</div>"
            f"<div>"
            f"<span class='deal-price-badge'>{formatar_moeda_br(item['orcamento_max'])}</span>"
            f"<span class='deal-loc-badge'>📍 {item['bairros_interesse']}</span>"
            f"{proib}"
            f"</div>"
            f"{perm}"
            f"<div style='font-size:0.74rem; color:#334155; margin-top:6px; line-height:1.4;'>"
            f"🏠 <strong>Apresentado:</strong> {item.get('imoveis_ja_mostrados')}<br>"
            f"✨ <strong>Match IA:</strong> <span style='color:#1d4ed8; font-weight:600;'>{item.get('imoveis_sugeridos_ia')}</span>"
            f"</div>"
            f"<div class='deal-Origin-footer'>"
            f"<span>🌐 {item.get('origem', 'WhatsApp')}</span>"
            f"<span>🛡️ Roleta: {item['dias_para_perder']}d restantes</span>"
            f"</div>"
            f"</div>"
        )
        st.markdown(html_card, unsafe_allow_html=True)

    with k1:
        renderizar_header_coluna("1. Novos / Roleta", col_novos, "#3b82f6")
        for item in col_novos:
            desenhar_card_enterprise(item)
            if st.button("Iniciar Atendimento ➡️", key=f"k1_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO")
                st.rerun()

    with k2:
        renderizar_header_coluna("2. Em Atendimento", col_atendimento, "#f59e0b")
        for item in col_atendimento:
            desenhar_card_enterprise(item)
            b1, b2 = st.columns(2)
            if b1.button("📅 Agendar", key=f"k2v_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "VISITA", "QUENTE")
                st.rerun()
            if b2.button("⏳ Pendente", key=f"k2r_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "REENGAJAR", "FRIO")
                st.rerun()

    with k3:
        renderizar_header_coluna("3. Reengajar / Alerta", col_reengajar, "#ef4444")
        for item in col_reengajar:
            desenhar_card_enterprise(item)
            if st.button("⚡ Reengajar c/ IA", key=f"k3_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO", "MORNO")
                st.rerun()

    with k4:
        renderizar_header_coluna("4. Visita / Proposta", col_visita, "#10b981")
        for item in col_visita:
            desenhar_card_enterprise(item)
            if st.button("⏪ Retornar p/ Fila", key=f"k4_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO", "MORNO")
                st.rerun()

# ---------------------------------------------------------------------
# ABA 2: WORKSPACE SPLIT-VIEW (INBOX WHATSAPP <-> INSPECTOR DO CRM)
# ---------------------------------------------------------------------
elif st.session_state.aba_ativa == "INBOX":
    col_in, col_out = st.columns([1.05, 1.15], gap="medium")

    with col_in:
        st.markdown(
            "<div class='inbox-panel'>"
            "<div style='font-weight:700; font-size:0.95rem; color:#0f172a; margin-bottom:4px;'>💬 Espelhamento WhatsApp Business (Escuta Passiva)</div>"
            "<div style='font-size:0.80rem; color:#64748b;'>Selecione uma conversa ativa da corretora Pâmela abaixo ou envie um áudio recebido:</div>"
            "</div>",
            unsafe_allow_html=True
        )
        
        c1, c2, c3 = st.columns(3, gap="small")
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

        st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

        dialogo_input = st.text_area(
            "Conversa sincronizada:",
            value=st.session_state.get("dialogo_wpp", ""),
            height=150,
            label_visibility="collapsed",
            placeholder="Clique em um cliente acima ou cole a conversa do WhatsApp..."
        )
        audio_escuta = st.file_uploader("🎙️ Anexar nota de voz (.ogg, .mp3):", type=["ogg", "mp3", "wav"])

        if st.button("⚡ Sincronizar Ficha no CRM & Sugerir Imóveis", type="primary", use_container_width=True):
            if not dialogo_input.strip() and audio_escuta is None:
                st.warning("Selecione um atendimento acima primeiro.")
            else:
                with st.spinner("Extraindo dados estruturados para o Funil..."):
                    try:
                        dados_escuta, _ = analisar_conversa_whatsapp_espelhada(dialogo_input, audio_escuta, api_key_input, modelo_selecionado)
                        st.session_state.ultima_escuta = dados_escuta
                        salvar_lead_escuta_whatsapp(dados_escuta)
                        st.toast("Ficha sincronizada automaticamente no Kanban!", icon="✅")
                    except Exception as e:
                        st.error(f"Erro: {e}")

    with col_out:
        if "ultima_escuta" in st.session_state and st.session_state.ultima_escuta:
            esc: ExtracaoEscutaWhatsApp = st.session_state.ultima_escuta
            cor_esq = cor_borda_temperatura(esc.temperatura_lead)
            
            permuta_html = ""
            if esc.possui_imovel_permuta_ou_venda and esc.possui_imovel_permuta_ou_venda.lower() not in ["não", "nao", "nenhum", "null", "none", "não possui"]:
                permuta_html = f"<div class='deal-permuta-box'>🔄 <strong>Oportunidade de Captação / Permuta:</strong> {esc.possui_imovel_permuta_ou_venda}</div>"

            proibidos_html = f"<span class='deal-forbid-badge'>🚫 Restrição: {', '.join(esc.bairros_descartados)}</span>" if esc.bairros_descartados else ""
            mostrados_html = ", ".join(esc.imoveis_ja_mostrados_pelo_corretor) if esc.imoveis_ja_mostrados_pelo_corretor else "Nenhum"
            bairros_busca = ", ".join(esc.bairros_interesse) if esc.bairros_interesse else "Aberto"

            html_inspector = (
                f"<div class='inbox-panel' style='border-top: 4px solid {cor_esq};'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
                f"<span style='font-size:1.05rem; font-weight:700; color:#0f172a;'>🗂️ Ficha CRM: {esc.nome_cliente}</span>"
                f"{badge_temperatura(esc.temperatura_lead)}"
                f"</div>"
                f"<div style='font-size:0.78rem; color:#64748b; margin-bottom:10px;'>"
                f"📞 {esc.telefone_cliente} &nbsp;|&nbsp; ⏳ Prazo: <strong>{esc.prazo_urgencia_compra}</strong> &nbsp;|&nbsp; 📌 Etapa: <strong>{esc.coluna_kanban_automatica}</strong>"
                f"</div>"
                f"{permuta_html}"
                f"<div style='margin-bottom:8px;'>"
                f"<span class='deal-price-badge'>💰 Teto: {formatar_moeda_br(esc.orcamento_identificado)}</span>"
                f"<span class='deal-loc-badge'>📍 Regiões: {bairros_busca}</span>"
                f"{proibidos_html}"
                f"</div>"
                f"<div style='font-size:0.80rem; color:#334155; margin-bottom:8px;'>"
                f"👁️ <strong>Imóveis já apresentados no chat:</strong> {mostrados_html}"
                f"</div>"
                f"<div style='background:#f8fafc; border:1px solid #e2e8f0; padding:9px 12px; border-radius:8px; font-size:0.81rem; color:#1e293b;'>"
                f"📝 <strong> Síntese do Atendimento:</strong> {esc.resumo_do_que_conversaram}"
                f"</div>"
                f"</div>"
            )
            st.markdown(html_inspector, unsafe_allow_html=True)

            imoveis_cat = carregar_imoveis()
            for sug in esc.imoveis_sugeridos_do_catalogo:
                im_d = next((i for i in imoveis_cat if i["codigo"] == sug.codigo_imovel), None)
                tit = f"{im_d['titulo']} ({formatar_moeda_br(im_d['valor'])})" if im_d else sug.codigo_imovel
                st.markdown(
                    f"<div class='deal-card' style='border-left:4px solid #2563eb; margin-top:8px;'>"
                    f"<strong>🎯 Recomendação do Estoque: ID {sug.codigo_imovel} — {tit}</strong>"
                    f"<span style='float:right; color:#2563eb; font-weight:700; font-size:0.78rem;'>{sug.compatibilidade_percentual}% Match</span><br>"
                    f"<span style='font-size:0.79rem; color:#475569;'>💡 {sug.motivo_para_mostrar_agora}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.markdown("###### 📲 Script de Resposta Rápida (Clique no ícone de copiar no canto da caixa):")
            st.code(esc.sugestao_proxima_resposta_corretor, language=None)
        else:
            st.markdown(
                "<div class='inbox-panel' style='text-align:center; padding:36px 20px; color:#64748b;'>"
                "<strong>🗂️ Inspector de Ficha Automática</strong><br><br>"
                "Selecione um atendimento à esquerda (ex: <strong>🏡 Ana Rosset</strong> ou <strong>🎙️ Áudio 1.8M</strong>) e clique em <strong>Sincronizar Ficha</strong> para visualizar os campos extraídos automaticamente pela IA."
                "</div>",
                unsafe_allow_html=True
            )

# ---------------------------------------------------------------------
# ABA 3: SUPER-DORY (COM FECHAMENTO CONTEXTUAL SEM REPETIR FRASE!)
# ---------------------------------------------------------------------
elif st.session_state.aba_ativa == "DORY":
    st.markdown(
        "<div class='inbox-panel'>"
        "<strong>🤖 Roleta 24/7 — Qualificação & Pivotagem de Orçamento (Evolução Dory)</strong><br>"
        "<span style='font-size:0.79rem; color:#64748b;'>Quando o cliente clica em um anúncio caro (ex: ID 8094 de R$ 888 mil), mas informa orçamento de R$ 350 mil, a IA sugere na hora o imóvel compatível e avança para o agendamento sem repetir bordões.</span>"
        "</div>",
        unsafe_allow_html=True
    )
    if "messages" not in st.session_state:
        st.session_state.messages = []

    cb1, cb2, cb3 = st.columns(3, gap="small")
    msg_atalho = None
    if cb1.button("1️⃣ Cliente clica no Hera (888k)", use_container_width=True):
        msg_atalho = "Olá! Vi o anúncio do Hera Botânica (ID 8094) no Cristo Rei."
    if cb2.button("2️⃣ Cliente diz: 'Só tenho 350 mil'", use_container_width=True):
        msg_atalho = "Será que compro algo bom em Curitiba? Eu tenho 350 mil."
    if cb3.button("🧹 Reiniciar Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    chat_box = st.container(height=330, border=True)
    input_wpp = st.chat_input("Simule uma resposta do cliente (ex: 'Sim, faz sentido! Pode mandar as fotos')...")
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
                with st.spinner("Consultando estoque..."):
                    catalogo_str = json.dumps(carregar_imoveis(), ensure_ascii=False)
                    sis_chat = (
                        f"Você é a assistente virtual da corretora Pâmela. Catálogo: {catalogo_str}. "
                        "REGRAS DE CONVERSA NATURAL: "
                        "1. Se o cliente tiver orçamento menor (ex: 350 mil), apresente o CTBA-350 (R$ 345 mil) e pergunte 'Faz sentido para você essa opção?'. "
                        "2. PROIBIDO repetir 'Faz sentido para você?' se essa frase já apareceu no histórico anterior! Se o cliente disser 'Sim', 'Faz' ou concordar, convide-o diretamente para receber o vídeo do decorado ou agendar uma visita com a Pâmela."
                    )
                    conteudos = [types.Content(role="user" if m["role"]=="user" else "model", parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages]
                    analise_wpp, _ = chamar_gemini_estruturado(conteudos, AnaliseAtendimento, sis_chat, api_key_input, modelo_selecionado)
                    st.markdown(sanitizar_markdown_whatsapp(analise_wpp.resposta_whatsapp))
                    st.session_state.messages.append({"role": "assistant", "content": analise_wpp.resposta_whatsapp})

# ---------------------------------------------------------------------
# ABA 4: CRUZAMENTO DE CARTEIRA (MATCH REVERSO)
# ---------------------------------------------------------------------
elif st.session_state.aba_ativa == "MATCH":
    imoveis_a = carregar_imoveis()
    opcoes = {f"ID {im['codigo']} • {im['titulo']} ({im['cidade_bairro']} - {formatar_moeda_br(im['valor'])})": im for im in imoveis_a}
    escolha = st.selectbox("🏢 Selecione o Empreendimento para filtrar compradores compatíveis na carteira:", list(opcoes.keys()))
    imovel_alvo = opcoes[escolha]

    for lead_m in leads_atuais:
        descartados_lead = (lead_m.get("bairros_descartados") or "").lower()
        bairro_proibido = any(b.strip() in imovel_alvo["cidade_bairro"].lower() for b in descartados_lead.split(",") if len(b.strip()) > 2 and b.strip() != "nenhum")
        orc_ok = (lead_m["orcamento_max"] is None) or (lead_m["orcamento_max"] * 1.25 >= imovel_alvo["valor"] and lead_m["orcamento_max"] * 0.4 <= imovel_alvo["valor"])
        if orc_ok and not bairro_proibido:
            cor_esq = cor_borda_temperatura(lead_m["temperatura"])
            st.markdown(
                f"<div class='deal-card' style='border-left:4px solid {cor_esq};'>"
                f"<strong>👤 {lead_m['nome']} ({lead_m['telefone']})</strong> &nbsp;{badge_temperatura(lead_m['temperatura'])}<br>"
                f"<span style='font-size:0.79rem; color:#475569;'>💰 Teto: <strong>{formatar_moeda_br(lead_m['orcamento_max'])}</strong> • 👁️ Histórico: {lead_m.get('imoveis_ja_mostrados')}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            if st.button(f"📲 Gerar Script de Abordagem p/ {lead_m['nome']}", key=f"m_{lead_m['id']}"):
                p_sis = "Crie uma mensagem curta de WhatsApp ofertando este imóvel para o cliente com base no histórico dele."
                p_usr = f"Cliente: {json.dumps(lead_m, ensure_ascii=False)} | Imóvel: {json.dumps(imovel_alvo, ensure_ascii=False)}"
                res_m, _ = chamar_gemini_estruturado(p_usr, MensagemReativacao, p_sis, api_key_input, modelo_selecionado)
                st.code(res_m.mensagem_personalizada, language=None)

# ---------------------------------------------------------------------
# ABA 5: GESTÃO & BI (FORECAST DE COMISSÕES, SIMULADOR & BACKOFFICE)
# ---------------------------------------------------------------------
elif st.session_state.aba_ativa == "BI":
    st.markdown("### 📊 Inteligência Comercial, Forecast & Simulador de Propostas")
    
    tab_f, tab_s, tab_b = st.tabs(["📈 Forecast de Comissões & VGV", "🧮 Simulador & Proposta WhatsApp", "🏢 Estoque & Captações (Backoffice)"])
    
    with tab_f:
        c_meta1, c_meta2 = st.columns(2)
        with c_meta1:
            meta_comissao = st.number_input("🎯 Meta de Comissão Mensal (R$):", value=35000.0, step=5000.0)
            taxa_comissao = st.slider("💼 Taxa Média de Corretagem (%):", min_value=1.0, max_value=6.0, value=2.5, step=0.5)
        with c_meta2:
            st.markdown("##### 💡 Parâmetros Ponderados da Etapa (Pipeline)")
            st.caption("Novos (10%) | Atendimento (25%) | Reengajar (15%) | Visita/Quente (60%)")

        pesos_etapas = {"NOVOS": 0.10, "ATENDIMENTO": 0.25, "REENGAJAR": 0.15, "VISITA": 0.60}
        vgv_ponderado = 0
        for l in leads_atuais:
            col = (l.get("coluna_kanban") or "ATENDIMENTO").upper()
            peso = pesos_etapas.get(col, 0.20)
            vgv_ponderado += (l["orcamento_max"] or 0) * peso

        comissao_projetada = vgv_ponderado * (taxa_comissao / 100.0)
        progresso_meta = min(1.0, comissao_projetada / meta_comissao if meta_comissao > 0 else 0)

        st.markdown(f"#### 💰 Projeção de Faturamento: **{formatar_moeda_br(comissao_projetada)}**")
        st.progress(progresso_meta, text=f"Progresso da Meta Mensal: {progresso_meta*100:.1f}% batido")

        st.divider()
        st.markdown("##### 🌐 Análise de Canais & Demanda por Região")
        col_ori1, col_ori2 = st.columns(2)
        with col_ori1:
            st.info("📱 **Canais mais Qualificados:** Instagram e WhatsApp Direto lideram a conversão para imóveis acima de R$ 900k.")
        with col_ori2:
            st.success("📍 **Região em Alta:** Cabral e Juvevê concentram 78% das intenções de compra de alto padrão.")

    with tab_s:
        st.markdown("##### 🧮 Simulador de Fluxo Financeiro & Proposta Express")
        imoveis_lista = carregar_imoveis()
        opcoes_sim = {f"ID {im['codigo']} • {im['titulo']} ({formatar_moeda_br(im['valor'])})": im for im in imoveis_lista}
        escolha_sim = st.selectbox("Selecione o Imóvel para Simulação:", list(opcoes_sim.keys()), key="sel_sim")
        imv_escolhido = opcoes_sim[escolha_sim]

        val_imv = imv_escolhido["valor"]
        c_s1, c_s2, c_s3 = st.columns(3)
        with c_s1:
            entrada_val = st.number_input("Valor de Entrada / FGTS (R$):", value=val_imv * 0.2, step=10000.0)
        with c_s2:
            parcelas_obra = st.slider("Parcelas Mensais na Obra:", min_value=12, max_value=60, value=36, step=6)
        with c_s3:
            permuta_valor = st.number_input("Imóvel em Permuta / Troca (R$):", value=0.0, step=20000.0)

        saldo_devedor = max(0.0, val_imv - entrada_val - permuta_valor)
        prestacao_mensal = saldo_devedor / parcelas_obra if parcelas_obra > 0 else 0

        st.markdown(
            f"<div class='inbox-panel' style='background:#f8fafc; border-left:4px solid #2563eb;'>"
            f"<strong>📋 Simulação Executiva Gerada:</strong><br>"
            f"• Imóvel: <strong>{imv_escolhido['titulo']}</strong> ({formatar_moeda_br(val_imv)})<br>"
            f"• Entrada + FGTS: <strong>{formatar_moeda_br(entrada_val)}</strong><br>"
            f"• Permuta Envolvida: <strong>{formatar_moeda_br(permuta_valor)}</strong><br>"
            f"• Saldo Financiado / Obra: <strong>{formatar_moeda_br(saldo_devedor)}</strong> em {parcelas_obra}x de <strong>{formatar_moeda_br(prestacao_mensal)}</strong>"
            f"</div>",
            unsafe_allow_html=True
        )

        proposta_wpp_texto = (
            f"Olá! Segue a simulação financeira personalizada para o *{imv_escolhido['titulo']}* ({imv_escolhido['cidade_bairro']}):\n\n"
            f"💰 *Valor Total:* {formatar_moeda_br(val_imv)}\n"
            f"🤝 *Entrada / FGTS:* {formatar_moeda_br(entrada_val)}\n"
            f"🔄 *Permuta:* {formatar_moeda_br(permuta_valor) if permuta_valor > 0 else 'Não possui'}\n"
            f"📑 *Saldo:* {parcelas_obra}x de {formatar_moeda_br(prestacao_mensal)}\n\n"
            f"Faz sentido agendarmos uma reunião para fecharmos este fluxo?"
        )
        st.markdown("###### 📲 Copiar Proposta para o WhatsApp:")
        st.code(proposta_wpp_texto, language=None)

    with tab_b:
        st.markdown("##### 🏢 Catálogo de Imóveis & Captações de Clientes (Permutas)")
        st.caption("Imóveis cadastrados ativos no sistema:")
        for im in imoveis_lista:
            st.markdown(
                f"<div class='deal-card'>"
                f"<strong>ID {im['codigo']} — {im['titulo']}</strong> ({im['cidade_bairro']})<br>"
                f"<span style='font-size:0.78rem; color:#475569;'>💰 {formatar_moeda_br(im['valor'])} • {im['modalidade']} • Entrega: {im['previsao_entrega']}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.markdown("---")
        st.markdown("🔄 **Imóveis Captados de Clientes (Base de Permuta / Angariação):**")
        st.markdown(
            f"<div class='deal-permuta-box'>"
            f"🏠 <strong>Ana Rosset:</strong> Casa em condomínio avaliada em R$ 2.6M (anunciada por R$ 2.2M). Aceita permuta por 2 aptos no Gaia Cabral."
            f"</div>",
            unsafe_allow_html=True
        )