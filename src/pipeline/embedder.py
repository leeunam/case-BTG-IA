"""
Embedding pipeline for BTG FII Analyzer.

Two chunk types:
  1. offer_profile  — primary offer description + market context at registration time
  2. fund_monthly   — FII monthly informe (PL, DY, cotistas, assets) from CVM

Embedding backend (auto-selected):
  - OpenAI text-embedding-3-small (1536 dims) if OPENAI_API_KEY has quota
  - sentence-transformers paraphrase-multilingual-mpnet-base-v2 (768 dims) as free fallback

Schema uses VECTOR(768) — compatible with the multilingual model.
If you switch to OpenAI, run: ALTER TABLE embedding ALTER COLUMN embedding TYPE VECTOR(1536);

Usage:
    python -m src.pipeline.embedder                  # embed all pending
    python -m src.pipeline.embedder --type=offers    # only offer profiles
    python -m src.pipeline.embedder --type=monthly   # only fund monthly
    python -m src.pipeline.embedder --limit=200      # cap chunks per run
    python -m src.pipeline.embedder --backend=openai # force OpenAI
    python -m src.pipeline.embedder --backend=local  # force sentence-transformers
"""
import os
import sys
import time
from datetime import date, datetime
from typing import Iterator

import pandas as pd
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from src.db.connection import get_conn

load_dotenv()

_BATCH_SIZE = 64   # texts per batch (safe for both backends)
_RATE_DELAY = 0.2  # seconds between batches

# ─── Backend selection ────────────────────────────────────────────────────────

def _build_openai_backend():
    from openai import OpenAI
    client = OpenAI()
    # Quick quota check
    client.embeddings.create(model="text-embedding-3-small", input="ping", dimensions=1536)
    def embed(texts: list[str]) -> list[list[float]]:
        resp = client.embeddings.create(
            model="text-embedding-3-small", input=texts, dimensions=1536
        )
        return [e.embedding for e in resp.data]
    return embed, 1536, "openai/text-embedding-3-small"


def _build_local_backend():
    from sentence_transformers import SentenceTransformer
    _ST_MODEL = "paraphrase-multilingual-mpnet-base-v2"
    print(f"  Loading local model {_ST_MODEL} (first run downloads ~280MB)...")
    model = SentenceTransformer(_ST_MODEL)
    def embed(texts: list[str]) -> list[list[float]]:
        return model.encode(texts, show_progress_bar=False).tolist()
    return embed, 768, f"sentence-transformers/{_ST_MODEL}"


def _select_backend(force: str | None = None):
    if force == "openai":
        return _build_openai_backend()
    if force == "local":
        return _build_local_backend()
    try:
        return _build_openai_backend()
    except Exception:
        print("  OpenAI unavailable — falling back to local sentence-transformers")
        return _build_local_backend()


_embed_fn, _dimensions, _model_name = None, None, None  # lazy init


# ═══════════════════════════════════════════════════════════════════════════
# Text generators
# ═══════════════════════════════════════════════════════════════════════════

def _fmt(val, prefix="R$ ", suffix="", decimals=2, divisor=1):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/D"
    v = float(val) / divisor
    return f"{prefix}{v:,.{decimals}f}{suffix}"


def _make_offer_text(row: dict, macro: dict) -> str:
    """Generate descriptive text for one primary offer."""
    lines = [
        f"OFERTA PRIMÁRIA DE FII: {row.get('fund_name', 'Desconhecido')}",
    ]
    if row.get("ticker"):
        lines[0] += f" [{row['ticker']}]"

    lines += [
        f"Tipo: {row.get('security_type', 'N/D')}",
        f"Registro CVM: {row.get('cvm_registration', 'N/D')}",
        f"Data de registro: {row.get('registered_at', 'N/D')}",
        f"Status: {row.get('status', 'N/D')}",
        "",
        "ESTRUTURA DA OFERTA:",
        f"Coordenador líder: {row.get('coordinator', 'N/D')}",
        f"Volume autorizado: {_fmt(row.get('total_volume'))}",
        f"Público-alvo: {row.get('target_audience', 'N/D')}",
        f"Regime de distribuição: {row.get('distribution_regime', 'N/D')}",
        f"Bookbuilding: {'Sim' if row.get('bookbuilding') else 'Não'}",
        f"Segmento do fundo: {row.get('segment', 'N/D')}",
    ]

    if row.get("dy_12m") is not None:
        lines += [
            "",
            "INDICADORES DO FUNDO (mercado secundário):",
            f"Dividend Yield 12m: {float(row['dy_12m']):.2f}%",
            f"P/VP: {float(row['pvp']):.2f}" if row.get("pvp") else "P/VP: N/D",
            f"Preço de mercado: {_fmt(row.get('market_price'))}",
            f"Vacância média: {float(row['vacancy_rate']):.2f}%"
            if row.get("vacancy_rate") is not None else "Vacância média: N/D",
        ]

    if macro:
        selic = macro.get("CDI_PROJ")
        ipca  = macro.get("IPCA_PROJ")
        lines += [
            "",
            "CONTEXTO MACROECONÔMICO (projeções Focus mais próximas do registro):",
            f"Selic projetada: {float(selic['value']):.2f}% a.a. (em {selic['date']})"
            if selic else "Selic projetada: N/D",
            f"IPCA projetado: {float(ipca['value']):.2f}% a.a. (em {ipca['date']})"
            if ipca else "IPCA projetado: N/D",
        ]
        if selic and row.get("dy_12m"):
            spread = float(row["dy_12m"]) - float(selic["value"])
            lines.append(f"Spread DY vs Selic: {spread:+.2f}pp")

    return "\n".join(lines)


def _make_fund_monthly_text(row: pd.Series) -> str:
    """Generate descriptive text for one FII monthly informe row."""
    nome  = str(row.get("Nome_Fundo_Classe", "N/D")).strip()
    cnpj  = str(row.get("CNPJ_Fundo_Classe",  "N/D")).strip()
    period = str(row.get("Data_Referencia",   "N/D")).strip()
    seg   = str(row.get("Segmento_Atuacao",   "N/D")).strip()
    admin = str(row.get("Nome_Administrador", "N/D")).strip()
    gestao = str(row.get("Tipo_Gestao",       "N/D")).strip()
    publico = str(row.get("Publico_Alvo",     "N/D")).strip()

    def n(col, div=1):
        return _fmt(row.get(col), divisor=div)

    lines = [
        f"RELATÓRIO MENSAL FII: {nome}",
        f"CNPJ: {cnpj} | Período: {period}",
        f"Segmento: {seg} | Gestão: {gestao} | Público-alvo: {publico}",
        f"Administrador: {admin}",
        "",
        "PATRIMÔNIO E COTISTAS:",
        f"Patrimônio Líquido: {n('Patrimonio_Liquido')}",
        f"Cotas Emitidas: {n('Cotas_Emitidas', 1)}",
        f"Valor Patrimonial da Cota: {n('Valor_Patrimonial_Cotas')}",
        f"Total de Cotistas: {n('Total_Numero_Cotistas', 1)}",
        f"  Pessoa Física: {n('Numero_Cotistas_Pessoa_Fisica', 1)}",
        "",
        "RENTABILIDADE NO MÊS:",
        f"Dividend Yield: {n('Percentual_Dividend_Yield_Mes', 1)}%",
        f"Rentabilidade Efetiva: {n('Percentual_Rentabilidade_Efetiva_Mes', 1)}%",
        f"Rentabilidade Patrimonial: {n('Percentual_Rentabilidade_Patrimonial_Mes', 1)}%",
        "",
        "ALOCAÇÃO DE ATIVOS:",
        f"Total Investido: {n('Total_Investido')}",
        f"  Imóveis de Renda Acabados: {n('Imoveis_Renda_Acabados')}",
        f"  Imóveis em Construção: {n('Imoveis_Renda_Construcao')}",
        f"  CRI / LCI: {n('CRI')} / {n('LCI')}",
        f"  Disponibilidades: {n('Disponibilidades')}",
        f"Total Passivo: {n('Total_Passivo')}",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# DB queries
# ═══════════════════════════════════════════════════════════════════════════

def _get_pending_offers(limit: int) -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(f"""
            SELECT
                o.id                                                           AS id,
                o.cvm_registration,
                COALESCE(v.name, 'Desconhecido')                               AS fund_name,
                v.ticker,
                v.segment,
                st.name                                                        AS security_type,
                CASE
                    WHEN o.registered_at > CURRENT_DATE                        THEN 'futuro'
                    WHEN o.ends_at IS NOT NULL AND o.ends_at < CURRENT_DATE    THEN 'encerrado'
                    WHEN o.started_at IS NOT NULL                              THEN 'em andamento'
                    ELSE 'pendente'
                END                                                            AS status,
                o.registered_at,
                o.total_volume,
                o.distribution_regime,
                o.bookbuilding,
                o.target_audience,
                p.name                                                         AS coordinator,
                ds.dy_12m,
                ds.pvp,
                ds.price                                                       AS market_price,
                ds.vacancy_rate
            FROM offer o
            LEFT JOIN vehicle v           ON v.id  = o.vehicle_id
            LEFT JOIN security_type st    ON st.id = o.security_type_id
            LEFT JOIN participant_role pr ON pr.offer_id = o.id
                                         AND pr.role = 'coordinator_leader'
            LEFT JOIN participant p       ON p.id = pr.participant_id
            LEFT JOIN LATERAL (
                SELECT dy_12m, pvp, price, vacancy_rate
                FROM daily_snapshot
                WHERE vehicle_id = v.id
                ORDER BY snapshot_date DESC LIMIT 1
            ) ds ON TRUE
            WHERE NOT EXISTS (
                SELECT 1 FROM embedding e
                WHERE e.offer_id = o.id AND e.section_type = 'offer_profile'
            )
            ORDER BY o.registered_at DESC NULLS LAST
            LIMIT {limit}
        """)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()

    return [dict(zip(cols, r)) for r in rows]


def _get_macro_near(ref_date) -> dict:
    """Get Focus projections closest to ref_date."""
    if not ref_date:
        return {}
    with get_conn() as conn:
        result = {}
        for code in ("CDI_PROJ", "IPCA_PROJ"):
            row = conn.execute("""
                SELECT value, metric_date FROM market_metric
                WHERE code = %s AND metric_date <= %s
                ORDER BY metric_date DESC LIMIT 1
            """, (code, ref_date)).fetchone()
            if row:
                result[code] = {"value": row[0], "date": row[1]}
    return result


def _get_pending_monthly(limit: int) -> pd.DataFrame:
    """Return monthly informe rows not yet embedded."""
    from src.pipeline.collectors.cvm_docs import CVMDocsCollector
    collector = CVMDocsCollector()
    df = collector.get_informe_dataframe()
    if df.empty:
        return df

    known_cnpjs = collector._get_known_cnpjs()
    df = df[df["CNPJ_Fundo_Classe"].isin(known_cnpjs)].copy()

    # Check which (cnpj, period) already embedded
    with get_conn() as conn:
        done = conn.execute("""
            SELECT metadata->>'cnpj', metadata->>'period'
            FROM embedding
            WHERE section_type = 'fund_monthly'
        """).fetchall()
    done_set = {(r[0], r[1]) for r in done}

    df["_key"] = list(zip(df["CNPJ_Fundo_Classe"], df["Data_Referencia"]))
    df = df[~df["_key"].apply(lambda k: k in done_set)].copy()
    df.drop(columns=["_key"], inplace=True)

    return df.head(limit)


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def _batched(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ═══════════════════════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════════════════════

def _store_embeddings(chunks: list[dict]) -> int:
    """Batch-insert chunks into embedding table. Returns count stored."""
    stored = 0
    with get_conn() as conn:
        for chunk in chunks:
            conn.execute(
                """
                INSERT INTO embedding
                    (offer_id, vehicle_id, content, embedding,
                     section_type, metadata)
                VALUES (%s, %s, %s, %s::vector, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    chunk.get("offer_id"),
                    chunk.get("vehicle_id"),
                    chunk["content"],
                    _vec_literal(chunk["embedding"]),
                    chunk["section_type"],
                    Jsonb(chunk["metadata"]),
                ),
            )
            stored += 1
        conn.commit()
    return stored


# ═══════════════════════════════════════════════════════════════════════════
# Main entry points
# ═══════════════════════════════════════════════════════════════════════════

def _ensure_backend(force: str | None = None) -> None:
    global _embed_fn, _dimensions, _model_name
    if _embed_fn is None:
        _embed_fn, _dimensions, _model_name = _select_backend(force)
        print(f"  Backend: {_model_name}  ({_dimensions} dims)")


def embed_offers(limit: int = 500, backend: str | None = None) -> int:
    _ensure_backend(backend)
    print(f"  Loading up to {limit} unembedded offers...")
    offers = _get_pending_offers(limit)
    print(f"  Found {len(offers)} pending offers")

    if not offers:
        return 0

    total_stored = 0

    for batch in _batched(offers, _BATCH_SIZE):
        texts = []
        meta  = []

        for row in batch:
            macro = _get_macro_near(row.get("registered_at"))
            text  = _make_offer_text(row, macro)
            texts.append(text)
            meta.append({
                "offer_id":   row["id"],
                "vehicle_id": None,
                "section_type": "offer_profile",
                "metadata": {
                    "source":             "offer_db",
                    "collected_at":       datetime.now().isoformat(),
                    "ticker":             row.get("ticker"),
                    "cvm_registration":   row.get("cvm_registration"),
                    "offer_type":         row.get("security_type"),
                    "offer_status":       row.get("status"),
                    "period":             str(row.get("registered_at") or ""),
                    "extraction_method":  "template",
                    "confidence_score":   0.95,
                    "financial_data_available": True,
                },
            })

        print(f"    Embedding {len(texts)} offer profiles...", end=" ", flush=True)
        vectors = _embed_fn(texts)
        print("OK")

        chunks = [
            {
                "offer_id":    m["offer_id"],
                "vehicle_id":  m["vehicle_id"],
                "content":     t,
                "embedding":   v,
                "section_type": m["section_type"],
                "metadata":    m["metadata"],
            }
            for t, v, m in zip(texts, vectors, meta)
        ]
        total_stored += _store_embeddings(chunks)
        time.sleep(_RATE_DELAY)

    return total_stored


def embed_fund_monthly(limit: int = 300, backend: str | None = None) -> int:
    _ensure_backend(backend)
    print(f"  Loading up to {limit} unembedded monthly informes...")
    df = _get_pending_monthly(limit)
    print(f"  Found {len(df)} pending fund-months")

    if df.empty:
        return 0

    # Get vehicle_id by CNPJ
    cnpj_to_vid: dict[str, int] = {}
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT i.cnpj, v.id FROM vehicle v
            JOIN issuer i ON i.id = v.issuer_id
            WHERE i.cnpj IS NOT NULL
        """).fetchall()
    cnpj_to_vid = {r[0]: r[1] for r in rows}

    total_stored = 0

    for batch_df in _batched(list(df.iterrows()), _BATCH_SIZE):
        texts = []
        meta  = []

        for _, row in batch_df:
            cnpj   = str(row.get("CNPJ_Fundo_Classe", "")).strip()
            period = str(row.get("Data_Referencia",   "")).strip()
            vid    = cnpj_to_vid.get(cnpj)
            text   = _make_fund_monthly_text(row)
            texts.append(text)
            meta.append({
                "offer_id":   None,
                "vehicle_id": vid,
                "section_type": "fund_monthly",
                "metadata": {
                    "source":             "cvm_inf_mensal",
                    "collected_at":       datetime.now().isoformat(),
                    "cnpj":               cnpj,
                    "period":             period,
                    "fund_name":          str(row.get("Nome_Fundo_Classe", "") or "").strip(),
                    "extraction_method":  "csv_template",
                    "confidence_score":   0.95,
                    "financial_data_available": True,
                },
            })

        print(f"    Embedding {len(texts)} fund-month profiles...", end=" ", flush=True)
        vectors = _embed_fn(texts)
        print("OK")

        chunks = [
            {
                "offer_id":    m["offer_id"],
                "vehicle_id":  m["vehicle_id"],
                "content":     t,
                "embedding":   v,
                "section_type": m["section_type"],
                "metadata":    m["metadata"],
            }
            for t, v, m in zip(texts, vectors, meta)
        ]
        total_stored += _store_embeddings(chunks)
        time.sleep(_RATE_DELAY)

    return total_stored


def create_ivfflat_index() -> None:
    """Create ANN index — call AFTER first batch of embeddings is loaded."""
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM embedding WHERE embedding IS NOT NULL").fetchone()[0]
        if n < 100:
            print(f"  Skipping index creation ({n} embeddings — need ≥ 100)")
            return
        print(f"  Creating IVFFlat index on {n} embeddings...")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_embedding_ivfflat "
            "ON embedding USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)",
            prepare=False,
        )
        conn.commit()
        print("  Index created.")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    embed_type = "all"
    limit      = 500
    backend    = None  # auto

    for arg in sys.argv[1:]:
        if arg.startswith("--type="):
            embed_type = arg.split("=")[1]
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg.startswith("--backend="):
            backend = arg.split("=")[1]

    # Init backend once
    _ensure_backend(backend)

    total = 0
    if embed_type in ("all", "offers"):
        stored = embed_offers(limit=limit)
        print(f"  Offers embedded: {stored}")
        total += stored

    if embed_type in ("all", "monthly"):
        stored = embed_fund_monthly(limit=limit)
        print(f"  Fund-months embedded: {stored}")
        total += stored

    create_ivfflat_index()
    print(f"\nTotal chunks embedded: {total}")
