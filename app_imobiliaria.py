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
# 1. BANCO DE DADOS (SQLite v5 - Completo com Permuta, Bairros Proibidos e Auto-Kanban)
# =====================================================================
DB_FILE = "crm_imobiliaria_v5.db"

IMOVEIS_INICIAIS = [
    {
        "codigo": "8212",
        "titulo": "Gaia Cabral (Pronto / Valor Promocional)",
        "cidade_bairro": "Curitiba - Cabral",
        "modalidade": "Pronto para Morar / Lançamento",
        "valor": 922700.00,
        "entrada_condicoes": "2Q (68m²/74m²) a partir de R$ 922.700 | 3Q a partir de R$ 1.136.400. Aceita propostas e analisa permuta.",
        "previsao_entrega": "Pronto (Entrega Outubro)",
        "quartos": 3,
        "vagas_garagem": 2,
        "aceita_pet": 1,
        "aceita_fgts": 0,
        "descricao": "Unidades de 2 e 3 dormitórios no Cabral com decorados prontos para visita e tabela promocional."
    },
    {
        "codigo": "CTBA-1650",
        "titulo": "Reserva Juvevê / Cabral High End",
        "cidade_bairro": "Curitiba - Cabral / Juvevê",
        "modalidade": "Pronto para Morar (Alto Padrão)",
        "valor": 1680000.00,
        "entrada_condicoes": "Negociação direta para fechamento rápido até Dezembro. Estuda permuta.",
        "previsao_entrega": "Imediata (Pronto)",
        "quartos": 3,
        "vagas_garagem": 3,
        "aceita_pet": 1,
        "aceita_fgts": 0,
        "descricao": "3 suítes amplas, 148m² privativos, churrasqueira a carvão, pronto para mudança ainda este ano."
    },
    {
        "codigo": "8094",
        "titulo": "Hera Botânica - Cristo Rei",
        "cidade_bairro": "Curitiba - Cristo Rei",
        "modalidade": "Lançamento / Condomínio Clube",
        "valor": 888800.00,
        "entrada_condicoes": "Entrada parcelada + Financiamento (Aceita FGTS)",
        "previsao_entrega": "Dez/2027",
        "quartos": 2,
        "vagas_garagem": 1,
        "aceita_pet": 1,
        "aceita_fgts": 1,
        "descricao": "70 m², 2 quartos (1 suíte), a 3 minutos do Jardim Botânico. Decorado disponível."
    },
    {
        "codigo": "CTBA-350",
        "titulo": "Residencial Parque das Araucárias",
        "cidade_bairro": "Curitiba - Capão Raso / Pinheirinho",
        "modalidade": "Na Planta / Entrada Facilitada",
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
        "titulo": "Residencial Horizon Água Verde",
        "cidade_bairro": "Curitiba - Água Verde",
        "modalidade": "Lançamento / Na Planta",
        "valor": 780000.00,
        "entrada_condicoes": "Entrada de R$ 78 mil (Aceita FGTS) + 36x na obra",
        "previsao_entrega": "Dez/2027",
        "quartos": 3,
        "vagas_garagem": 2,
        "aceita_pet": 1,
        "aceita_fgts": 1,
        "descricao": "3 quartos (1 suíte), varanda gourmet a carvão, face norte, próximo à Praça do Japão."
    },
    {
        "codigo": "IMB-001",
        "titulo": "Casa Geminada a 400m da Praia da Vila Nova",
        "cidade_bairro": "Imbituba - Vila Nova",
        "modalidade": "Locação Anual",
        "valor": 2400.00,
        "entrada_condicoes": "IPTU R$ 85/mês. Caução ou Seguro Fiança",
        "previsao_entrega": "Imediata",
        "quartos": 2,
        "vagas_garagem": 1,
        "aceita_pet": 1,
        "aceita_fgts": 0,
        "descricao": "Pátio fechado com muros altos ideal para cães, cozinha planejada."
    }
]

LEADS_EXEMPLO = [
    ("Ana Rosset", "(41) 99111-2233", "MORNO", 1136400.0, "Curitiba - Cabral", "Cristo Rei",
     "Casa em condomínio clube de R$ 2,2M (saiu da Especiale) para angariar ou permutar por 2 aptos de 3Q",
     "Depende da venda/permuta da casa atual",
     "8212 - Gaia Cabral (2Q R$ 922k e 3Q R$ 1,13M), 8094 - Cristo Rei (Rejeitou o bairro)",
     "8212 (Unidades promocionais Gaia Cabral)",
     "Avalia compra de 2 aptos de 3Q no Gaia Cabral mediante venda ou permuta de sua casa de campo de R$ 2,2 milhões. Descartou Cristo Rei.",
     "ATENDIMENTO", datetime.now().strftime("%Y-%m-%d %H:%M"), "WhatsApp Espelhado", "Acompanhar captação da casa de 2.2M"),
    
    ("Rose Miguel", "(49) 98503-3656", "MORNO", 350000.0, "Curitiba - Geral", "Nenhum",
     "Não possui", "Médio prazo",
     "8094 - Hera Botânica (Achou caro p/ o bolso de 350k)",
     "CTBA-350 (Parque das Araucárias - R$ 345k)",
     "Veio pelo anúncio do Hera Botânica (888k), mas revelou ter R$ 350 mil. IA já separou o CTBA-350.",
     "REENGAJAR", "2026-10-14 14:00", "Facebook / Instagram", "14/10/2026 às 14:00 (ATRASADO)"),
    
    ("Comprador Áudio (Alto Padrão)", "(41) 99888-5544", "QUENTE", 1800000.0, "Curitiba - Cabral, Juvevê, Batel", "Nenhum",
     "Compra direta", "Alta urgência (Fechar até Dezembro)",
     "Opções acima de 2M (Ficaram fora do teto)",
     "CTBA-1650 (Reserva Juvevê/Cabral - R$ 1,68M)",
     "Mandou áudio confirmando busca ativa para fechar até Dezembro na faixa de R$ 1,5M a R$ 1,8M no máximo.",
     "VISITA", datetime.now().strftime("%Y-%m-%d %H:%M"), "WhatsApp Áudio", "Enviar opções até R$ 1,8M hoje")
]

def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS imoveis (
            codigo TEXT PRIMARY KEY,
            titulo TEXT,
            cidade_bairro TEXT,
            modalidade TEXT,
            valor REAL,
            entrada_condicoes TEXT,
            previsao_entrega TEXT,
            quartos INTEGER,
            vagas_garagem INTEGER,
            aceita_pet INTEGER,
            aceita_fgts INTEGER,
            descricao TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            telefone TEXT UNIQUE,
            temperatura TEXT,
            orcamento_max REAL,
            bairros_interesse TEXT,
            bairros_descartados TEXT,
            oportunidade_permuta_captacao TEXT,
            prazo_urgencia TEXT,
            imoveis_ja_mostrados TEXT,
            imoveis_sugeridos_ia TEXT,
            resumo_historico TEXT,
            coluna_kanban TEXT,
            ultima_interacao TEXT,
            origem TEXT DEFAULT 'WhatsApp Espelhado',
            data_retorno TEXT DEFAULT 'Automático'
        )
    """)

    c.execute("SELECT COUNT(*) FROM imoveis")
    if c.fetchone()[0] == 0:
        for im in IMOVEIS_INICIAIS:
            c.execute("""
                INSERT INTO imoveis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (im["codigo"], im["titulo"], im["cidade_bairro"], im["modalidade"], im["valor"],
                  im["entrada_condicoes"], im["previsao_entrega"], im["quartos"], im["vagas_garagem"],
                  im["aceita_pet"], im["aceita_fgts"], im["descricao"]))

    c.execute("SELECT COUNT(*) FROM leads")
    if c.fetchone()[0] == 0:
        c.executemany("""
            INSERT INTO leads (
                nome, telefone, temperatura, orcamento_max, bairros_interesse,
                bairros_descartados, oportunidade_permuta_captacao, prazo_urgencia,
                imoveis_ja_mostrados, imoveis_sugeridos_ia, resumo_historico,
                coluna_kanban, ultima_interacao, origem, data_retorno
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, LEADS_EXEMPLO)

    conn.commit()
    conn.close()

def carregar_imoveis() -> List[dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM imoveis")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def carregar_leads() -> List[dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY ultima_interacao DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def salvar_lead_escuta_whatsapp(dados_ia: 'ExtracaoEscutaWhatsApp'):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    mostrados_str = ", ".join(dados_ia.imoveis_ja_mostrados_pelo_corretor) if dados_ia.imoveis_ja_mostrados_pelo_corretor else "Nenhum ainda"
    sugeridos_str = ", ".join([f"{m.codigo_imovel} ({m.compatibilidade_percentual}%)" for m in dados_ia.imoveis_sugeridos_do_catalogo])
    bairros_str = ", ".join(dados_ia.bairros_interesse) if dados_ia.bairros_interesse else "Aberto"
    descartados_str = ", ".join(dados_ia.bairros_descartados) if dados_ia.bairros_descartados else "Nenhum"
    permuta_str = dados_ia.possui_imovel_permuta_ou_venda or "Não mencionado"

    c.execute("SELECT id FROM leads WHERE telefone = ?", (dados_ia.telefone_cliente,))
    existente = c.fetchone()

    if existente:
        c.execute("""
            UPDATE leads
            SET nome=?, temperatura=?, orcamento_max=?, bairros_interesse=?,
                bairros_descartados=?, oportunidade_permuta_captacao=?, prazo_urgencia=?,
                imoveis_ja_mostrados=?, imoveis_sugeridos_ia=?, resumo_historico=?,
                coluna_kanban=?, ultima_interacao=?, data_retorno=?
            WHERE telefone=?
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'WhatsApp Espelhado (Auto)', ?)
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
# 2. UTILITÁRIOS DE FORMATAÇÃO E UX
# =====================================================================
def formatar_moeda_br(valor: Optional[float]) -> str:
    if valor is None:
        return "A definir"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def icone_temperatura(temp: str) -> str:
    mapa = {
        "QUENTE": "🔴 Quente",
        "MORNO": "🟠 Morno",
        "FRIO": "🩵 Frio",
        "CONGELADO": "🔵 Congelado",
        "NEUTRO": "⚪ Neutro"
    }
    return mapa.get((temp or "").upper(), f"⚪ {temp}")

def sanitizar_markdown_whatsapp(texto: str) -> str:
    if not texto:
        return ""
    texto_limpo = texto.replace("$", r"\$")
    texto_limpo = re.sub(r'(?<!\*)\*([^\*\n]+)\*(?!\*)', r'**\1**', texto_limpo)
    return texto_limpo

# =====================================================================
# 3. CONTRATOS DE SAÍDA DA IA (Pydantic Schemas)
# =====================================================================
class MatchEmpreendimento(BaseModel):
    codigo_imovel: str = Field(description="Código exato do imóvel no catálogo (ex: 8212, CTBA-1650, CTBA-350, CTBA-101).")
    compatibilidade_percentual: int = Field(description="Nota de 0 a 100.")
    motivo_para_mostrar_agora: str = Field(description="Por que este imóvel encaixa perfeitamente no pedido, prazo ou permuta do cliente.")

class ExtracaoEscutaWhatsApp(BaseModel):
    nome_cliente: str = Field(description="Nome do cliente identificado na conversa.")
    telefone_cliente: str = Field(description="Telefone do cliente.")
    temperatura_lead: str = Field(description="Escolha estritamente: 'QUENTE', 'MORNO', 'FRIO', 'CONGELADO' ou 'NEUTRO'.")
    coluna_kanban_automatica: str = Field(
        description="Para qual coluna do Kanban o card deve ir sozinho: 'NOVOS', 'ATENDIMENTO', 'REENGAJAR' ou 'VISITA'."
    )
    orcamento_identificado: Optional[float] = Field(description="Orçamento máximo em R$ descoberto na conversa (ex: 1800000 para '1 e 800').")
    bairros_interesse: List[str] = Field(description="Bairros de interesse aprovados pelo cliente.")
    bairros_descartados: List[str] = Field(description="Bairros que o cliente disse explicitamente que NÃO deseja (ex: ['Cristo Rei']).")
    possui_imovel_permuta_ou_venda: Optional[str] = Field(
        description="Se o cliente tem imóvel para dar em permuta (troca) ou precisa vender a casa atual (oportunidade de angariação/captação para a imobiliária), descreva aqui com valor. Caso contrário, null."
    )
    prazo_urgencia_compra: str = Field(description="Prazo desejado pelo cliente (ex: 'Compra até Dezembro', 'Aguardando venda da casa atual').")
    imoveis_ja_mostrados_pelo_corretor: List[str] = Field(
        description="Lista dos imóveis que o corretor JÁ apresentou na conversa e a reação do cliente."
    )
    resumo_do_que_conversaram: str = Field(
        description="Resumo executivo completo do bate-papo para ficar gravado no card do Kanban."
    )
    proximo_passo_ou_agenda: str = Field(
        description="Próximo passo combinado ou lembrete de agenda."
    )
    imoveis_sugeridos_do_catalogo: List[MatchEmpreendimento] = Field(
        description="Imóveis do catálogo recomendados (JAMAIS sugira imóveis que fiquem nos bairros_descartados pelo cliente!)."
    )
    sugestao_proxima_resposta_corretor: str = Field(
        description="Mensagem pronta para o corretor colar no WhatsApp agora, dando sequência natural à conversa."
    )

class AnaliseAtendimento(BaseModel):
    resposta_whatsapp: str = Field(description="Mensagem para o cliente.")
    imoveis_recomendados: List[str] = Field(description="Códigos recomendados.")
    temperatura_lead: str = Field(description="'QUENTE', 'MORNO', 'FRIO', 'CONGELADO' ou 'NEUTRO'.")
    orcamento_identificado: Optional[float] = Field(description="Valor máximo em R$.")
    bairros_interesse: List[str] = Field(description="Bairros mencionados.")
    resumo_para_corretor: str = Field(description="Resumo executivo.")

class MensagemReativacao(BaseModel):
    mensagem_personalizada: str = Field(description="Mensagem de WhatsApp personalizada citando o histórico, respeitando bairros proibidos e ofertando o imóvel.")
    motivo_do_match: str = Field(description="Explicação curta do match.")

# =====================================================================
# 4. CONFIGURAÇÃO DA PÁGINA E BARRA LATERAL
# =====================================================================
st.set_page_config(page_title="Auto-CRM & Copiloto IA Imobiliário", page_icon="🎧", layout="wide")

if "db_iniciado_v5" not in st.session_state:
    inicializar_banco()
    st.session_state.db_iniciado_v5 = True

st.markdown("""
<style>
    .card-escuta {
        background-color: #0f172a;
        border: 1px solid #334155;
        border-left: 5px solid #10b981;
        padding: 14px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .alerta-agenda {
        background-color: #450a0a;
        border: 1px solid #ef4444;
        border-left: 6px solid #ef4444;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 14px;
    }
    .alerta-permuta {
        background-color: #422006;
        border: 1px solid #f59e0b;
        border-left: 5px solid #f59e0b;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .tag-mostrado {
        background-color: #334155;
        color: #f8fafc;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.82em;
        display: inline-block;
        margin-bottom: 4px;
    }
    .tag-sugerido {
        background-color: #065f46;
        color: #ecfdf5;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.82em;
        display: inline-block;
        margin-bottom: 4px;
    }
    .tag-proibido {
        background-color: #7f1d1d;
        color: #fef2f2;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.82em;
        display: inline-block;
        margin-bottom: 4px;
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

# =====================================================================
# CHAVE EMBARCADA (A Pâmela não precisará digitar nada!)
# =====================================================================
CHAVE_EMBARCADA = "COLE_SUA_CHAVE_AIzaSy_AQUI"

def obter_chave_api() -> str:
    # 1º Tenta pegar do cofre seguro da nuvem (Streamlit Cloud)
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    # 2º Tenta pegar da variável do Windows ou usa a Chave Embarcada direto no código
    return os.environ.get("GEMINI_API_KEY") or CHAVE_EMBARCADA

with st.sidebar:
    st.header("⚙️ Painel da Corretora")
    chave_automatica = obter_chave_api()

    # Se a chave já estiver embarcada, NÃO mostra campo de senha para não confundir a Pâmela!
    if chave_automatica and chave_automatica != "COLE_SUA_CHAVE_AIzaSy_AQUI":
        api_key_input = chave_automatica
        st.success("🔒 **Motor IA:** `Conectado e Ativo`")
    else:
        api_key_input = st.text_input("🔑 Chave da API:", type="password")

    modelo_selecionado = "gemini-3.5-flash-lite"  # Fixo no mais rápido para ela não precisar mexer!
    
    st.success("🟢 **WhatsApp:** `Espelhado (Auto-CRM)`")
    st.caption("⚡ **Tempo Médio 1ª Resposta:** `0.03 min (2s)`")
    st.divider()
    if st.button("🔄 Reiniciar Dados de Teste", use_container_width=True):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        inicializar_banco()
        st.session_state.ultima_escuta = None
        st.rerun()

# =====================================================================
# 5. MOTORES DE CHAMADA DA API DO GEMINI (COM TIMEOUT DE 12s)
# =====================================================================
def chamar_gemini_estruturado(conteudos, schema_pydantic, system_prompt: str, chave_api: str, modelo_primario: str):
    if not chave_api:
        raise ValueError("Insira a sua GEMINI_API_KEY na barra lateral esquerda.")
    
    client = genai.Client(
        api_key=chave_api.strip(),
        http_options=types.HttpOptions(timeout=12000)
    )
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
            response = client.models.generate_content(
                model=modelo,
                contents=conteudos,
                config=config_geracao,
            )
            return schema_pydantic.model_validate_json(response.text), modelo
        except Exception as e:
            ultimo_erro = e
            time.sleep(0.3)
            continue

    raise RuntimeError(f"Oscilação na rede da API: {ultimo_erro}")

def analisar_conversa_whatsapp_espelhada(dialogo_texto: str, arquivo_audio, chave_api: str, modelo_primario: str) -> tuple[ExtracaoEscutaWhatsApp, str]:
    imoveis_atuais = carregar_imoveis()
    catalogo_json = json.dumps(imoveis_atuais, ensure_ascii=False, indent=2)
    
    prompt_sistema = f"""
    Você é o Motor de Escuta Passiva (Shadow CRM) conectado ao WhatsApp da corretora Pâmela Maioki (Paulo Celles Imóveis).
    Sua função é ler a conversa (ou ouvir o áudio enviado pelo cliente) no WhatsApp e alimentar o CRM/Kanban 100% sozinho!
    
    REGRAS DE OURO DE NEGÓCIO IMOBILIÁRIO:
    1. DETECÇÃO DE PERMUTA E ANGARIAÇÃO: Se o cliente mencionar que tem uma casa/imóvel próprio para dar em troca (permuta) ou que precisa vender o imóvel atual (ex: tirou de outra imobiliária como a Especiale), registre isso em `possui_imovel_permuta_ou_venda` como oportunidade de captação!
    2. BAIRROS DESCARTADOS (LISTA NEGRA): Se o cliente disser "Não desejo bairro X" (ex: Cristo Rei), anote em `bairros_descartados` e JAMAIS sugira imóveis desse bairro.
    3. COMPREENSÃO DE VALORES FALADOS: Expressões como "1 e meio a 1 e 800" significam R$ 1.500.000,00 a R$ 1.800.000,00. "2.2 mi" significa R$ 2.200.000,00.
    4. HISTÓRICO DE IMÓVEIS MOSTRADOS: Liste em `imoveis_ja_mostrados_pelo_corretor` tudo o que a corretora já enviou na conversa e separe em `imoveis_sugeridos_do_catalogo` as melhores opções compatíveis do catálogo abaixo.

    CATÁLOGO OFICIAL DA IMOBILIÁRIA:
    {catalogo_json}
    """

    partes = []
    if arquivo_audio is not None:
        partes.append(types.Part.from_bytes(data=arquivo_audio.read(), mime_type=arquivo_audio.type or "audio/ogg"))
        partes.append(types.Part.from_text(text="Ouça este áudio do cliente para a corretora Pâmela, extraia o orçamento (ex: 1.5M a 1.8M), o prazo (ex: até dezembro) e indique os imóveis do catálogo que cabem nesse teto."))
    if dialogo_texto.strip():
        partes.append(types.Part.from_text(text=f"Conversa espelhada do WhatsApp:\n{dialogo_texto}"))

    return chamar_gemini_estruturado(partes, ExtracaoEscutaWhatsApp, prompt_sistema, chave_api, modelo_primario)

# =====================================================================
# 6. INTERFACE EM 5 ABAS (PRONTA PARA DEMONSTRAÇÃO)
# =====================================================================
st.title("🎧 Auto-CRM Imobiliário: O WhatsApp Alimenta o Kanban Sozinho")
st.caption("Protótipo personalizado com os casos reais de Curitiba (Gaia Cabral, Hera Botânica, Permuta de 2.2M e Áudio de 1.8M) + Imbituba.")

aba_escuta, aba_kanban, aba_chat, aba_match, aba_roi = st.tabs([
    "🎧 1. Escuta do WhatsApp ➔ Auto-CRM",
    "📋 2. Kanban Automático (Estilo Trello)",
    "💬 3. Super-Dory 24/7 (Caso Rose 888k ➔ 350k)",
    "🎯 4. Oferta Ativa Anti-Bloqueio",
    "📈 5. Seu Dashboard & Gestão"
])

# ---------------------------------------------------------------------
# ABA 1: ESCUTA PASSIVA DO WHATSAPP (COM OS CASOS REAIS DA PÂMELA)
# ---------------------------------------------------------------------
with aba_escuta:
    st.subheader("🎧 Você conversa no WhatsApp (ou recebe áudio) e o CRM se preenche sozinho")
    st.markdown("""
    **Teste com os casos reais enviados pela Pâmela:** Clique nos botões abaixo (ou suba o arquivo de áudio `.ogg` do cliente) para ver a IA extraindo **oportunidade de permuta/captação (R$ 2,2M)**, **bairros proibidos (Não desejo Cristo Rei)**, **orçamento por voz (R$ 1,5M a R$ 1,8M até Dezembro)** e montando o card lá na Guia 2 (Kanban)!
    """)

    col_wpp_espelho, col_card_gerado = st.columns([1.05, 1.15], gap="large")

    with col_wpp_espelho:
        st.markdown("#### 📱 Simulador de Conversa Espelhada do WhatsApp")
        st.caption("⚡ **Clique em um dos 3 Casos Reais abaixo para carregar:**")
        
        c_sim1, c_sim2, c_sim3 = st.columns(3)
        if c_sim1.button("🏡 1. Caso Ana Rosset (Gaia + Permuta 2.2M)", use_container_width=True):
            st.session_state.dialogo_wpp = (
                "Cliente: Ana Rosset | WhatsApp: (41) 99111-2233\n\n"
                "[Corretora Pâmela]: Oi Ana! Vi que demonstrou interesse no empreendimento Gaia Cabral (ID 8212). Te encaminhei todas as fotos e vídeos dos decorados de 2 dormitórios (68m² e 74m² iniciando em R$ 922.700,00) e de 3 dormitórios (R$ 1.136.400,00). A construtora aceita propostas.\n"
                "[Cliente Ana Rosset]: Vou avaliar com calma, obrigada. Tenho uma casa nova em condomínio clube avaliada em 2.6 mi, mas vou anunciar por 2.2 mi. Pedi hoje pra imobiliária Especiale excluir o anúncio de locação porque queremos vender. Teria que ver se aceitam troca (permuta) por 2 aptos de 3 quartos ou esperar vendermos a casa.\n"
                "[Corretora Pâmela]: Bom dia Ana! Vamos colocar seu imóvel à venda na Paulo Celles? Temos muito interesse em tê-lo na nossa carteira! Também saiu um empreendimento bem legal na região do Cristo Rei a 3 minutos do Jardim Botânico.\n"
                "[Cliente Ana Rosset]: Ainda não vendi minha casa. Não desejo bairro Cristo Rei.\n"
                "[Corretora Pâmela]: Sem problemas. O Gaia Cabral está com duas unidades de 2 e 3 dormitórios com valor promocional."
            )
        if c_sim2.button("🎙️ 2. Áudio Cliente (1.5M a 1.8M até Dez)", use_container_width=True):
            st.session_state.dialogo_wpp = (
                "Cliente: Comprador Alto Padrão (Áudio) | WhatsApp: (41) 99888-5544\n\n"
                "[Transcrição Automática de Áudio Recebido às 22:47]: Oi Pâmela, tudo bem? Boa noite. Pâmela, na verdade eu tô em busca sim de comprar algo, deveria acontecer até dezembro. Só assim, algo que eu busco tá entre 1 e meio, 1 e 800 no máximo [R$ 1.500.000 a R$ 1.800.000], tá bom? Então talvez pode ser que fique fora, mas se tiver dentro aí, se você quiser mandar, tudo bem. Agradeço!"
            )
        if c_sim3.button("💬 3. Cliente Quer 3Q c/ FGTS (Água Verde)", use_container_width=True):
            st.session_state.dialogo_wpp = (
                "Cliente: Rafael Souza | WhatsApp: (41) 99234-5678\n\n"
                "[Corretora Pâmela]: Oi Rafael! Te mandei o Hera Botânica no Cristo Rei (ID 8094) de 2 quartos por R$ 888.800.\n"
                "[Cliente Rafael]: Oi Pâmela! A localização é boa, mas 2 quartos fica pequeno pra nós. Precisamos de 3 quartos com churrasqueira até R$ 800 mil no Água Verde. Temos R$ 90 mil de FGTS."
            )

        dialogo_input = st.text_area(
            "Conversa capturada do WhatsApp (Corretor <-> Cliente):",
            value=st.session_state.get("dialogo_wpp", ""),
            height=195,
            placeholder="Clique em um dos botões acima ou cole qualquer conversa de WhatsApp aqui..."
        )
        audio_escuta = st.file_uploader(
            "🎙️ Ou suba diretamente o arquivo de áudio do cliente (.ogg, .mp3, .wav):",
            type=["ogg", "mp3", "wav"]
        )

        if st.button("⚡ Ler Conversa/Áudio, Alimentar CRM e Atualizar Kanban Sozinho!", type="primary", use_container_width=True):
            if not dialogo_input.strip() and audio_escuta is None:
                st.warning("Clique em um dos 3 Casos Reais acima ou suba um áudio para testar!")
            else:
                with st.spinner("IA lendo a conversa, detectando permutas/restrições e montando o card no Kanban..."):
                    try:
                        dados_escuta, mod_ativo = analisar_conversa_whatsapp_espelhada(
                            dialogo_input, audio_escuta, api_key_input, modelo_selecionado
                        )
                        st.session_state.ultima_escuta = dados_escuta
                        salvar_lead_escuta_whatsapp(dados_escuta)
                        st.toast(f"Card de {dados_escuta.nome_cliente} salvo e movido para '{dados_escuta.coluna_kanban_automatica}' no Kanban!", icon="🪄")
                    except Exception as e:
                        st.error(f"Erro: {e}")

    with col_card_gerado:
        st.markdown("#### 🗂️ Ficha Inteligente Gerada Sozinha (Zero Digitação)")
        if "ultima_escuta" in st.session_state and st.session_state.ultima_escuta:
            esc: ExtracaoEscutaWhatsApp = st.session_state.ultima_escuta
            
            st.success(f"🪄 **Kanban Atualizado!** Card enviado para a coluna: **`{esc.coluna_kanban_automatica}`** (Confira na Guia 2!)")

            with st.container(border=True):
                st.markdown(f"### 👤 {esc.nome_cliente} — {icone_temperatura(esc.temperatura_lead)}")
                st.caption(f"📲 {esc.telefone_cliente} | ⏳ Urgência/Prazo: **{esc.prazo_urgencia_compra}** | 📅 Próximo Passo: **{esc.proximo_passo_ou_agenda}**")
                
                if esc.possui_imovel_permuta_ou_venda and esc.possui_imovel_permuta_ou_venda.lower() not in ["não", "nao", "nenhum", "null", "none"]:
                    st.markdown(f"""
                    <div class="alerta-permuta">
                        🔄 <strong>OPORTUNIDADE DE PERMUTA / CAPTAÇÃO (ANGARIAÇÃO) DETECTADA:</strong><br>
                        {esc.possui_imovel_permuta_ou_venda}
                    </div>
                    """, unsafe_allow_html=True)

                k1, k2 = st.columns(2)
                k1.metric("💰 Teto de Orçamento Identificado", formatar_moeda_br(esc.orcamento_identificado))
                k2.metric("📍 Bairros Desejados", ", ".join(esc.bairros_interesse) if esc.bairros_interesse else "Aberto")

                if esc.bairros_descartados:
                    st.markdown(f"<span class='tag-proibido'>🚫 Bairros Rejeitados pelo Cliente (Bloqueados): {', '.join(esc.bairros_descartados)}</span>", unsafe_allow_html=True)

                st.markdown("**📝 O que conversaram (Resumo salvo no CRM):**")
                st.info(esc.resumo_do_que_conversaram)

                st.markdown("**👁️ Imóveis que a Corretora JÁ mostrou na conversa:**")
                if esc.imoveis_ja_mostrados_pelo_corretor:
                    for im_m in esc.imoveis_ja_mostrados_pelo_corretor:
                        st.markdown(f"<span class='tag-mostrado'>👁️ {im_m}</span>", unsafe_allow_html=True)
                else:
                    st.caption("Nenhum imóvel específico mostrado ainda.")

                st.markdown("**🎯 Imóveis do Catálogo que a IA separou para enviar agora:**")
                imoveis_cat = carregar_imoveis()
                for sug in esc.imoveis_sugeridos_do_catalogo:
                    im_d = next((i for i in imoveis_cat if i["codigo"] == sug.codigo_imovel), None)
                    tit = f"{im_d['titulo']} — {im_d['cidade_bairro']} ({formatar_moeda_br(im_d['valor'])})" if im_d else sug.codigo_imovel
                    st.markdown(f"""
                    <div class="card-escuta">
                        <strong>🏢 ID {sug.codigo_imovel} — {tit}</strong> ({sug.compatibilidade_percentual}% Match)<br>
                        💡 <em>{sug.motivo_para_mostrar_agora}</em>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("**📲 Resposta Sugerida Pronta (1 clique para copiar e colar no WhatsApp):**")
                st.code(esc.sugestao_proxima_resposta_corretor, language=None)
        else:
            st.info("👈 Clique em **'🏡 1. Caso Ana Rosset'** ou **'🎙️ 2. Áudio Cliente (1.5M a 1.8M)'** à esquerda e depois no botão vermelho para ver a mágica acontecer!")

# ---------------------------------------------------------------------
# ABA 2: GUIA EXCLUSIVA PARA O KANBAN (COM PERMUTA, BAIRROS PROIBIDOS E MOSTRADOS)
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

        l["dias_parado"] = dias_parado
        l["dias_para_perder_roleta"] = max(0, 30 - dias_parado)

        if "ATRASADO" in (l.get("data_retorno") or "") or dias_parado >= 2:
            retornos_vencidos.append(l)

        status_col = (l.get("coluna_kanban") or "ATENDIMENTO").upper()
        if status_col == "VISITA" or l["temperatura"] == "QUENTE":
            col_visita.append(l)
        elif status_col == "REENGAJAR" or dias_parado >= 2:
            col_reengajar.append(l)
        elif status_col == "NOVOS":
            col_novos.append(l)
        else:
            col_atendimento.append(l)

    if retornos_vencidos:
        nomes_v = ", ".join([f"{r['nome']} ({r['data_retorno']})" for r in retornos_vencidos])
        st.markdown(f"""
        <div class="alerta-agenda">
            🔔 <strong>ALERTA ATIVO DE AGENDA (O QUE O CRM ANTIGO ESCONDE):</strong> Você tem <strong>{len(retornos_vencidos)} retorno(s) pendente(s)</strong>: {nomes_v}
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📋 Quadro Kanban Automático (Alimentado pela Escuta do WhatsApp)")
    st.caption("Veja tudo sem abrir a ficha: Orçamento, Imóveis já mostrados, Sugestão da IA, Alerta de Permuta/Captação e Bairros Proibidos.")

    k1, k2, k3, k4 = st.columns(4, gap="medium")

    def renderizar_card_rico(item: dict):
        with st.container(border=True):
            st.markdown(f"**👤 {item['nome']}** — {icone_temperatura(item['temperatura'])}")
            st.caption(f"📲 {item['telefone']} | ⏳ **{item.get('prazo_urgencia', 'A definir')}**")
            st.write(f"💰 Teto: **{formatar_moeda_br(item['orcamento_max'])}** | 📍 {item['bairros_interesse']}")
            
            if item.get("bairros_descartados") and item["bairros_descartados"] != "Nenhum":
                st.markdown(f"<span class='tag-proibido'>🚫 Não quer: {item['bairros_descartados']}</span>", unsafe_allow_html=True)
            
            if item.get("oportunidade_permuta_captacao") and item["oportunidade_permuta_captacao"] not in ["Não possui", "Não mencionado", "Compra direta"]:
                st.markdown(f"<span class='tag-mostrado' style='background-color:#78350f;'>🔄 Permuta/Captação: {item['oportunidade_permuta_captacao']}</span>", unsafe_allow_html=True)

            st.markdown(f"<span class='tag-mostrado'>👁️ Mostrou: {item.get('imoveis_ja_mostrados', 'Nenhum')}</span>", unsafe_allow_html=True)
            st.markdown(f"<span class='tag-sugerido'>🎯 Sugerido IA: {item.get('imoveis_sugeridos_ia', 'A analisar')}</span>", unsafe_allow_html=True)
            st.caption(f"💬 *{item['resumo_historico']}*")

    with k1:
        st.info(f"📥 **1. Novos / Roleta** (`{len(col_novos)}`)")
        for item in col_novos:
            renderizar_card_rico(item)
            if st.button("➡️ Em Atendimento", key=f"k1_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO")
                st.rerun()

    with k2:
        st.warning(f"💬 **2. Em Atendimento** (`{len(col_atendimento)}`)")
        for item in col_atendimento:
            renderizar_card_rico(item)
            b_v, b_r = st.columns(2)
            if b_v.button("📅 Visita", key=f"k2v_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "VISITA", "QUENTE")
                st.rerun()
            if b_r.button("⏳ Atrasar", key=f"k2r_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "REENGAJAR", "FRIO")
                st.rerun()

    with k3:
        st.error(f"🚨 **3. Reengajar / Atrasados** (`{len(col_reengajar)}`)")
        for item in col_reengajar:
            renderizar_card_rico(item)
            st.caption(f"⚠️ **Perde na roleta em: {item['dias_para_perder_roleta']} dias**")
            if st.button("🤖 Reengajar IA (Salvar Lead)", key=f"k3_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO", "MORNO")
                st.toast(f"IA reengajou {item['nome']} e renovou seus 30 dias!", icon="🛡️")
                time.sleep(0.5)
                st.rerun()

    with k4:
        st.success(f"🏆 **4. Visita / Alta Urgência** (`{len(col_visita)}`)")
        for item in col_visita:
            renderizar_card_rico(item)
            if st.button("⏪ Voltar p/ Atendimento", key=f"k4_{item['id']}", use_container_width=True):
                mover_card_kanban(item["id"], "ATENDIMENTO", "MORNO")
                st.rerun()

# ---------------------------------------------------------------------
# ABA 3: SUPER-DORY 24/7 (SIMULADOR DO CASO ROSE MIGUEL 888k -> 350k)
# ---------------------------------------------------------------------
with aba_chat:
    st.subheader("💬 Super-Dory 24/7: Quando o Cliente vem do Anúncio Caro mas tem Menos Orçamento")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    cb1, cb2, cb3 = st.columns(3)
    msg_atalho = None
    if cb1.button("1️⃣ Simular Clique no Hera Botânica (ID 8094 - 888k)", use_container_width=True):
        msg_atalho = "Olá! Quero continuar com atendimento personalizado! AnúncioADV2 - Hera || 8094. Aguardo"
    if cb2.button("2️⃣ Responder igual à Rose: 'Eu tenho 350 mil'", use_container_width=True):
        msg_atalho = "Será que compro algo bom em Curitiba? Eu tenho 350 mil."
    if cb3.button("🧹 Limpar Conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    chat_box = st.container(height=360, border=True)
    input_wpp = st.chat_input("Digite a mensagem do cliente...")
    texto_enviado = msg_atalho or input_wpp

    with chat_box:
        if not st.session_state.messages and not texto_enviado:
            st.info("👋 Clique em **1️⃣** e depois em **2️⃣** para ver como a nossa IA pivota do Hera Botânica (R$ 888 mil) para o imóvel de R$ 345 mil na mesma hora sem abandonar a cliente!")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                st.markdown(sanitizar_markdown_whatsapp(msg["content"]))

        if texto_enviado:
            st.session_state.messages.append({"role": "user", "content": texto_enviado})
            with st.chat_message("user", avatar="🧑"):
                st.markdown(sanitizar_markdown_whatsapp(texto_enviado))

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Consultando catálogo e respondendo..."):
                    try:
                        catalogo_str = json.dumps(carregar_imoveis(), ensure_ascii=False)
                        sis_chat = (
                            f"Você é a Super-Dory da imobiliária. Catálogo: {catalogo_str}. "
                            "Se o cliente vier pelo anúncio 8094 (R$ 888.800) mas disser que tem R$ 350 mil, apresente na hora o imóvel CTBA-350 (R$ 345.000)!"
                        )
                        conteudos = [types.Content(role="user" if m["role"]=="user" else "model", parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages]
                        analise_wpp, mod_usado = chamar_gemini_estruturado(conteudos, AnaliseAtendimento, sis_chat, api_key_input, modelo_selecionado)
                        st.markdown(sanitizar_markdown_whatsapp(analise_wpp.resposta_whatsapp))
                        st.session_state.messages.append({"role": "assistant", "content": analise_wpp.resposta_whatsapp})
                    except Exception as e:
                        st.error(f"Erro: {e}")

# ---------------------------------------------------------------------
# ABA 4: OFERTA ATIVA ANTI-BLOQUEIO (RESPEITANDO BAIRROS PROIBIDOS!)
# ---------------------------------------------------------------------
with aba_match:
    st.subheader("🎯 Oferta Ativa Inteligente por Lançamento (Filtra Bairros Rejeitados)")
    leads_s = carregar_leads()
    imoveis_a = carregar_imoveis()
    opcoes = {f"ID {im['codigo']} - {im['titulo']} ({im['cidade_bairro']} - {formatar_moeda_br(im['valor'])})": im for im in imoveis_a}
    escolha = st.selectbox("Selecione o Imóvel/Lançamento para cruzar com a carteira:", list(opcoes.keys()))
    imovel_alvo = opcoes[escolha]

    for lead_m in leads_s:
        # Trava inteligente: se o cliente descartou o bairro deste imóvel (ex: Ana Rosset descartou Cristo Rei), não oferece!
        descartados_lead = (lead_m.get("bairros_descartados") or "").lower()
        bairro_proibido = any(b.strip() in imovel_alvo["cidade_bairro"].lower() for b in descartados_lead.split(",") if len(b.strip()) > 2 and b.strip() != "nenhum")
        
        orc_ok = (lead_m["orcamento_max"] is None) or (lead_m["orcamento_max"] * 1.25 >= imovel_alvo["valor"] and lead_m["orcamento_max"] * 0.4 <= imovel_alvo["valor"])
        
        if orc_ok and not bairro_proibido:
            with st.container(border=True):
                st.markdown(f"**👤 {lead_m['nome']} — {lead_m['telefone']}** | {icone_temperatura(lead_m['temperatura'])}")
                st.caption(f"👁️ Já viu: `{lead_m.get('imoveis_ja_mostrados')}` | 🚫 Não quer: `{lead_m.get('bairros_descartados')}` | 💰 Teto: **{formatar_moeda_br(lead_m['orcamento_max'])}**")
                if st.button(f"✨ Criar Mensagem Anti-Bloqueio para {lead_m['nome']}", key=f"m_{lead_m['id']}"):
                    p_sis = "Escreva uma mensagem curta e natural de WhatsApp apresentando este imóvel exatamente para o perfil deste cliente."
                    p_usr = f"Cliente: {json.dumps(lead_m, ensure_ascii=False)} | Imóvel: {json.dumps(imovel_alvo, ensure_ascii=False)}"
                    res_m, _ = chamar_gemini_estruturado(p_usr, MensagemReativacao, p_sis, api_key_input, modelo_selecionado)
                    st.code(res_m.mensagem_personalizada, language=None)

# ---------------------------------------------------------------------
# ABA 5: SEU DASHBOARD & GESTÃO
# ---------------------------------------------------------------------
with aba_roi:
    st.subheader("📈 Seu Dashboard — Alimentado 100% pela Escuta do WhatsApp")
    leads_g = carregar_leads()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("🎧 Conversas Auditadas", f"{len(leads_g)} leads", "Zero digitação manual")
    d2.metric("🔄 Oportunidades de Permuta/Captação", f"{sum(1 for l in leads_g if '2,2M' in (l.get('oportunidade_permuta_captacao') or ''))} imóveis", "R$ 2,2M em potencial de angariação")
    d3.metric("🏆 Alta Urgência / Visitas", f"{sum(1 for l in leads_g if l.get('coluna_kanban')=='VISITA')}", "Movidos automaticamente")
    orc_v = [l["orcamento_max"] for l in leads_g if l["orcamento_max"] and l["orcamento_max"] > 50000]
    d4.metric("🎯 Ticket Médio da Carteira", formatar_moeda_br(sum(orc_v)/len(orc_v) if orc_v else 0), "De R$ 350k a R$ 1,8M")