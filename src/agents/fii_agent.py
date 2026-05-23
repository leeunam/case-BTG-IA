"""
BTG FII Analyzer — Agente LangGraph com memória persistente (PostgresSaver).

Ferramentas disponíveis:
  - buscar_ofertas      → busca estruturada SQL em ofertas primárias de FII
  - buscar_semantico    → busca vetorial pgvector em perfis de ofertas e informes mensais
  - contexto_macro      → Selic, CDI, IPCA e projeções Focus do banco
  - perfil_fundo        → DY, P/VP, vacância e relatório mensal de um fundo específico
  - ranking_players     → concentração e ranking de coordenadores

Guard rails:
  O agente NUNCA faz recomendação de investimento.
  NUNCA infere taxas, preços ou condições financeiras ausentes nos dados.
  Quando termos não estiverem disponíveis, responde com mensagem padrão.
"""
import os
from datetime import date, timedelta
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src.db.connection import get_conn

load_dotenv()

_SYSTEM_PROMPT = SystemMessage(content=(
    "Você é assistente de análise do mercado primário de FII para o time de mesa do BTG Pactual. "
    "Exponha dados, comparações e evidências — NÃO faça recomendação de investimento. "
    "NÃO infira taxas ou condições financeiras ausentes nos dados. "
    "Quando termos financeiros não estiverem disponíveis responda: "
    "'Termos financeiros não disponíveis na fonte consultada.' "
    "Responda em português. Cite sempre a fonte e data de cada dado. "
    "DY e P/VP são do mercado secundário (Fundamentus), não da oferta primária. "
    "Para IPOs, DY histórico e P/VP são indisponíveis — o fundo não tem histórico realizado."
))

# ─── LLM (singleton) ─────────────────────────────────────────────────────────

_model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=2048,
    max_retries=3,
)

# ─── Embedding model (lazy singleton) ────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embed_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")


def _embed_query(text: str) -> list[float]:
    return _get_embed_model().encode(text).tolist()


def _vec_literal(vec: list[float]) -> str:
    """Format a float list as pgvector literal string for %s::vector parameterization."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


# ═══════════════════════════════════════════════════════════════════════════════
# Tools
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def buscar_ofertas(
    status: str = "",
    coordenador: str = "",
    segmento: str = "",
    ticker: str = "",
    dias: int = 30,
    limite: int = 15,
) -> str:
    """
    Busca ofertas primárias de FII no banco de dados (fonte: CVM).

    Args:
        status: filtro de status — 'em andamento', 'encerrado', 'pendente' ou 'futuro'
        coordenador: nome parcial do coordenador líder (ex: 'BTG', 'XP')
        segmento: tipo do fundo — 'logistica', 'shoppings', 'lajes', 'papel', 'hibrido'
        ticker: ticker do fundo (ex: 'XPML11')
        dias: janela histórica em dias (730 = 2 anos)
        limite: número máximo de resultados retornados
    """
    since = date.today() - timedelta(days=dias)
    with get_conn() as conn:
        cur = conn.execute("""
            SELECT
                o.cvm_registration,
                COALESCE(v.name, 'Desconhecido')  AS fund_name,
                v.ticker, v.segment,
                CASE
                    WHEN o.registered_at > CURRENT_DATE THEN 'futuro'
                    WHEN o.ends_at IS NOT NULL AND o.ends_at < CURRENT_DATE THEN 'encerrado'
                    WHEN o.started_at IS NOT NULL THEN 'em andamento'
                    ELSE 'pendente'
                END AS status,
                o.registered_at, o.ends_at,
                o.total_volume, o.bookbuilding, o.target_audience,
                o.is_ipo, o.distribution_rite,
                p.name AS coordinator,
                ds.dy_12m, ds.pvp
            FROM offer o
            LEFT JOIN vehicle v ON v.id = o.vehicle_id
            LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
            LEFT JOIN participant p ON p.id = pr.participant_id
            LEFT JOIN LATERAL (
                SELECT dy_12m, pvp FROM daily_snapshot
                WHERE vehicle_id = v.id ORDER BY snapshot_date DESC LIMIT 1
            ) ds ON TRUE
            WHERE o.registered_at >= %s
            ORDER BY o.registered_at DESC NULLS LAST
            LIMIT 500
        """, (since,))
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    def match(row, field, term):
        val = str(row.get(field) or "").lower()
        return not term or term.lower() in val

    rows = [
        r for r in rows
        if match(r, "status",      status)
        and match(r, "coordinator", coordenador)
        and match(r, "segment",    segmento)
        and match(r, "ticker",     ticker)
    ][:limite]

    if not rows:
        return "Nenhuma oferta encontrada com os filtros informados."

    lines = [f"**{len(rows)} ofertas encontradas** (fonte: CVM Res. 160, desde {since}):\n"]
    for r in rows:
        vol    = f"R${float(r['total_volume'])/1e6:.0f}M" if r.get("total_volume") else "N/D"
        tk     = f" [{r['ticker']}]" if r.get("ticker") else ""
        ipo    = " | IPO" if r.get("is_ipo") else ""
        rito   = f" | {r['distribution_rite']}" if r.get("distribution_rite") else ""
        # DY e P/VP só fazem sentido em follow-on
        dy  = f" | DY={float(r['dy_12m']):.1f}%" if r.get("dy_12m") and not r.get("is_ipo") else ""
        pvp = f" | P/VP={float(r['pvp']):.2f}"   if r.get("pvp")    and not r.get("is_ipo") else ""
        lines.append(
            f"• {r['fund_name'][:45]}{tk}{ipo}{rito}\n"
            f"  Status: {r['status']} | Vol. autorizado: {vol} | Coord: {r['coordinator'] or 'N/D'}"
            f" | Reg: {r['registered_at']}{dy}{pvp}"
        )
    lines.append(
        "\n⚠️ DY e P/VP são do mercado secundário (Fundamentus), não da oferta primária. "
        "Para IPOs, DY histórico e P/VP são indisponíveis."
    )
    return "\n".join(lines)


@tool
def buscar_semantico(
    consulta: str,
    tipo: str = "offer_profile",
    top_k: int = 5,
) -> str:
    """
    Busca semântica por similaridade (pgvector) em perfis de ofertas e informes mensais.

    Args:
        consulta: pergunta ou descrição em linguagem natural (ex: 'fundos de logística com vacância baixa')
        tipo: 'offer_profile' para ofertas primárias ou 'fund_monthly' para informes mensais
        top_k: número de resultados mais similares a retornar (máximo 10)
    """
    with get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM embedding WHERE section_type = %s AND embedding IS NOT NULL",
            (tipo,),
        ).fetchone()[0]

    if n == 0:
        return (
            f"Nenhum embedding do tipo '{tipo}' disponível. "
            "Execute `python -m src.pipeline.embedder` para gerar os vetores."
        )

    top_k   = min(top_k, 10)
    vec_str = _vec_literal(_embed_query(consulta))

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                e.content,
                e.metadata->>'ticker'    AS ticker,
                e.metadata->>'period'    AS period,
                e.metadata->>'fund_name' AS fund_name,
                1 - (e.embedding <=> %s::vector) AS similarity
            FROM embedding e
            WHERE e.section_type = %s AND e.embedding IS NOT NULL
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
            """,
            (vec_str, tipo, vec_str, top_k),
        ).fetchall()

    if not rows:
        return "Nenhum resultado encontrado."

    lines = [f"**{len(rows)} resultados para:** '{consulta}'\n"]
    for i, r in enumerate(rows, 1):
        sim = float(r[4]) if r[4] is not None else 0.0
        tk  = f"[{r[1]}]" if r[1] else ""
        pd_ = f"({r[2]})" if r[2] else ""
        lines.append(f"--- Resultado {i} | Similaridade: {sim:.3f} | {tk} {pd_} ---")
        lines.append(r[0][:600])
        lines.append("")
    return "\n".join(lines)


@tool
def contexto_macro() -> str:
    """
    Retorna os indicadores macroeconômicos mais recentes do banco.
    Inclui meta Selic (COPOM), CDI, IPCA, IGP-M e projeções Focus.
    Fontes: BCB (Selic), B3/CETIP via BCB (CDI), IBGE via BCB (IPCA), FGV via BCB (IGP-M).
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT code, value, metric_date
            FROM market_metric
            WHERE (code, metric_date) IN (
                SELECT code, MAX(metric_date) FROM market_metric GROUP BY code
            )
            ORDER BY code
        """).fetchall()

    if not rows:
        return "Dados macroeconômicos não disponíveis. Execute o pipeline BCB primeiro."

    selic_meta  = next((r for r in rows if r[0] == "SELIC_META"), None)
    selic_daily = next((r for r in rows if r[0] == "SELIC"), None)
    selic_proj  = next((r for r in rows if r[0] == "CDI_PROJ"), None)
    cdi_daily   = next((r for r in rows if r[0] == "CDI"), None)
    ipca        = next((r for r in rows if r[0] == "IPCA"), None)
    ipca_proj   = next((r for r in rows if r[0] == "IPCA_PROJ"), None)
    igpm        = next((r for r in rows if r[0] == "IGPM"), None)
    ifix        = next((r for r in rows if r[0] == "IFIX"), None)

    lines = ["**Indicadores Macroeconômicos**\n"]

    if selic_meta:
        lines.append(
            f"Selic meta (COPOM): **{float(selic_meta[1]):.2f}% a.a.** "
            f"(em {selic_meta[2]}) — Fonte: BCB"
        )
    elif selic_daily:
        anual = ((1 + float(selic_daily[1]) / 100) ** 252 - 1) * 100
        lines.append(
            f"Selic efetiva: {float(selic_daily[1]):.4f}%/dia → **{anual:.2f}% a.a.** "
            f"(em {selic_daily[2]}) — Fonte: BCB/SGS série 11"
        )

    if selic_proj:
        lines.append(
            f"Selic projetada (Focus): **{float(selic_proj[1]):.2f}% a.a.** "
            f"(mediana em {selic_proj[2]}) — Fonte: BCB Focus"
        )

    if cdi_daily:
        anual = ((1 + float(cdi_daily[1]) / 100) ** 252 - 1) * 100
        lines.append(
            f"CDI diário: {float(cdi_daily[1]):.4f}%/dia → **{anual:.2f}% a.a.** "
            f"(em {cdi_daily[2]}) — Fonte: B3/CETIP, via BCB/SGS série 12"
        )

    if ipca:
        lines.append(
            f"IPCA mensal: {float(ipca[1]):.2f}% "
            f"(em {ipca[2]}) — Fonte: IBGE, via BCB/SGS série 433"
        )

    if ipca_proj:
        lines.append(
            f"IPCA projetado (Focus): **{float(ipca_proj[1]):.2f}% a.a.** "
            f"(mediana em {ipca_proj[2]}) — Fonte: BCB Focus"
        )

    if igpm:
        lines.append(
            f"IGP-M mensal: {float(igpm[1]):.2f}% "
            f"(em {igpm[2]}) — Fonte: FGV, via BCB/SGS série 189"
        )

    if ifix:
        lines.append(
            f"IFIX: **{float(ifix[1]):.2f} pts** "
            f"(em {ifix[2]}) — Fonte: B3, via Yahoo Finance"
        )

    lines.append("\n⚠️ Dados expostos como referência. Análise de impacto é responsabilidade da mesa.")
    return "\n".join(lines)


@tool
def perfil_fundo(ticker: str) -> str:
    """
    Retorna o perfil completo de um FII: indicadores de mercado e histórico de ofertas primárias.
    Para IPOs, indicadores de mercado são indisponíveis (sem histórico realizado).

    Args:
        ticker: ticker do fundo no padrão B3 (ex: 'XPML11', 'HGLG11')
    """
    ticker = ticker.upper().strip()
    with get_conn() as conn:
        v_row = conn.execute("""
            SELECT v.id, v.name, v.segment, v.fund_type, v.ticker
            FROM vehicle v WHERE v.ticker = %s LIMIT 1
        """, (ticker,)).fetchone()

        if not v_row:
            return f"Fundo com ticker '{ticker}' não encontrado na base."

        vid = v_row[0]

        ds = conn.execute("""
            SELECT dy_12m, pvp, price, pl_total, vacancy_rate, snapshot_date
            FROM daily_snapshot WHERE vehicle_id = %s
            ORDER BY snapshot_date DESC LIMIT 1
        """, (vid,)).fetchone()

        offers = conn.execute("""
            SELECT o.cvm_registration, o.registered_at, o.is_ipo,
                   CASE WHEN o.ends_at < CURRENT_DATE THEN 'encerrado' ELSE 'ativo/pendente' END AS status,
                   o.total_volume, p.name AS coordinator
            FROM offer o
            LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
            LEFT JOIN participant p ON p.id = pr.participant_id
            WHERE o.vehicle_id = %s
            ORDER BY o.registered_at DESC LIMIT 5
        """, (vid,)).fetchall()

    lines = [f"**Perfil: {v_row[1]} [{ticker}]**\n"]
    lines.append(f"Segmento: {v_row[2] or 'N/D'} | Tipo: {v_row[3] or 'N/D'}")

    if ds:
        lines.append(f"\n**Indicadores de Mercado Secundário** (em {ds[5]}, fonte: Fundamentus):")
        lines.append(f"  DY 12m: {float(ds[0]):.2f}%" if ds[0] else "  DY 12m: N/D")
        lines.append(f"  P/VP: {float(ds[1]):.2f}"    if ds[1] else "  P/VP: N/D")
        lines.append(f"  Preço: R${float(ds[2]):.2f}" if ds[2] else "  Preço: N/D")
        lines.append(f"  PL: R${float(ds[3])/1e6:.0f}M" if ds[3] else "  PL: N/D")
        lines.append(f"  Vacância: {float(ds[4]):.2f}%" if ds[4] else "  Vacância: N/D")
        lines.append("  ⚠️ Indicadores do mercado secundário — não são termos da oferta primária.")
    else:
        lines.append("\nIndicadores de mercado secundário não disponíveis para este fundo.")

    if offers:
        lines.append(f"\n**Ofertas Primárias Registradas ({len(offers)}):**")
        for o in offers:
            vol  = f"R${float(o[4])/1e6:.0f}M" if o[4] else "N/D"
            tipo = " [IPO]" if o[2] else " [Follow-on]"
            lines.append(
                f"  • CVM {o[0]}{tipo} | {o[1]} | {o[3]} "
                f"| Vol. autorizado: {vol} | Coord: {o[5] or 'N/D'}"
            )
    else:
        lines.append("\nNenhuma oferta primária registrada para este fundo.")

    return "\n".join(lines)


@tool
def ranking_players(dias: int = 30, top_n: int = 10) -> str:
    """
    Ranking dos coordenadores líderes por número de ofertas e volume no período.

    Args:
        dias: janela de análise em dias (365 = 1 ano, 730 = 2 anos)
        top_n: número de coordenadores a exibir
    """
    since = date.today() - timedelta(days=dias)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                COALESCE(p.name, 'Não identificado') AS coordinator,
                COUNT(DISTINCT o.id)                  AS total_offers,
                COALESCE(SUM(o.total_volume), 0)      AS total_volume,
                COUNT(DISTINCT o.vehicle_id)          AS unique_funds
            FROM offer o
            LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
            LEFT JOIN participant p       ON p.id = pr.participant_id
            WHERE o.registered_at >= %s
            GROUP BY COALESCE(p.name, 'Não identificado')
            ORDER BY total_offers DESC
            LIMIT %s
        """, (since, top_n)).fetchall()

    if not rows:
        return "Dados de coordenadores não encontrados para o período."

    total_offers = sum(r[1] for r in rows)
    total_vol    = sum(float(r[2]) for r in rows)

    lines = [
        f"**Ranking de Coordenadores** (últimos {dias} dias, top {top_n})\n",
        f"{'Coordenador':<45} {'Ofertas':>7} {'Share':>6} {'Vol. Aut.':>12} {'Fundos':>7}",
        "-" * 82,
    ]
    for r in rows:
        share = r[1] / total_offers * 100 if total_offers else 0
        vol   = f"R${float(r[2])/1e9:.1f}B" if r[2] else "N/D"
        lines.append(f"{r[0][:44]:<45} {r[1]:>7} {share:>5.1f}% {vol:>12} {r[3]:>7}")

    lines.append(f"\n{'TOTAL':<45} {total_offers:>7} {'100%':>6} {f'R${total_vol/1e9:.1f}B':>12}")
    lines.append(
        "\n⚠️ 'Vol. Aut.' = volume máximo autorizado, não o valor efetivamente captado."
    )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Agent — lazy singleton
# ═══════════════════════════════════════════════════════════════════════════════

_TOOLS = [buscar_ofertas, buscar_semantico, contexto_macro, perfil_fundo, ranking_players]

_agent = None
_pg_conn = None


def _setup_checkpointer():
    """
    Create a PostgresSaver instance using the same connection parameters as
    PostgresSaver.from_conn_string() — autocommit=True, prepare_threshold=0,
    row_factory=dict_row.

    Returns None if DATABASE_URL is not set or connection fails.
    """
    global _pg_conn
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Warning: DATABASE_URL not set — agent will run without persistent memory.")
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres import PostgresSaver

        _pg_conn = psycopg.connect(
            db_url,
            autocommit=True,
            prepare_threshold=0,     # matches PostgresSaver.from_conn_string internals
            row_factory=dict_row,    # required by PostgresSaver
        )
        checkpointer = PostgresSaver(_pg_conn)
        checkpointer.setup()
        return checkpointer
    except Exception as exc:
        print(f"Warning: PostgresSaver setup failed ({exc}) — running without memory.")
        return None


def build_agent():
    """
    Return the compiled LangGraph ReAct agent.
    Creates the agent (and its PostgreSQL checkpointer) once and reuses the instance.
    Thread-safe for single-process servers. For multi-process (Gunicorn workers),
    each worker maintains its own singleton.
    """
    global _agent
    if _agent is None:
        checkpointer = _setup_checkpointer()
        _agent = create_react_agent(
            _model,
            _TOOLS,
            checkpointer=checkpointer,
            prompt=_SYSTEM_PROMPT,
        )
    return _agent
