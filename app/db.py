"""Shared database query functions for the Streamlit dashboard."""
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from src.db.connection import get_conn


def _query(sql: str, params=None) -> pd.DataFrame:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
    # psycopg3 returns NUMERIC columns as decimal.Decimal — convert to float
    cleaned = [
        tuple(float(v) if isinstance(v, Decimal) else v for v in row)
        for row in rows
    ]
    return pd.DataFrame(cleaned, columns=cols)


# ─── Market metrics ──────────────────────────────────────────────────────────

def get_latest_macro() -> dict:
    df = _query("""
        SELECT code, value, metric_date
        FROM market_metric
        WHERE (code, metric_date) IN (
            SELECT code, MAX(metric_date) FROM market_metric GROUP BY code
        )
    """)
    return {row["code"]: {"value": row["value"], "date": row["metric_date"]}
            for _, row in df.iterrows()}


def get_macro_history(codes: list[str], since: date) -> pd.DataFrame:
    placeholders = ",".join(["%s"] * len(codes))
    return _query(f"""
        SELECT code, metric_date, value
        FROM market_metric
        WHERE code IN ({placeholders}) AND metric_date >= %s
        ORDER BY metric_date
    """, codes + [since])


# ─── Offers ──────────────────────────────────────────────────────────────────

def get_offers(
    since: date | None = None,
    until: date | None = None,
    status_filter: list[str] | None = None,
    coordinator_filter: str | None = None,
    audience_filter: str | None = None,
) -> pd.DataFrame:
    since = since or (date.today() - timedelta(days=730))
    until = until or date(2030, 12, 31)

    df = _query("""
        SELECT
            o.id,
            o.cvm_registration,
            COALESCE(v.name, 'Desconhecido')      AS fund_name,
            v.ticker,
            v.segment,
            st.code                                AS security_type_code,
            st.name                                AS security_type,
            o.status                               AS db_status,
            CASE
                WHEN o.registered_at > CURRENT_DATE                THEN 'futuro'
                WHEN o.ends_at IS NOT NULL AND o.ends_at < CURRENT_DATE THEN 'encerrado'
                WHEN o.started_at IS NOT NULL                       THEN 'em andamento'
                WHEN o.status NOT IN ('unknown','')                 THEN o.status
                ELSE 'pendente'
            END                                    AS status,
            o.registered_at,
            o.started_at,
            o.ends_at,
            o.total_volume,
            o.unit_price,
            o.distribution_regime,
            o.bookbuilding,
            o.target_audience,
            o.financial_terms_available,
            o.financial_terms_note,
            p.name                                 AS coordinator,
            o.extra->>'tipo_requerimento'           AS tipo_requerimento,
            o.extra->>'grupo_coordenador'           AS grupo_coordenador,
            o.extra->>'raw_status'                  AS cvm_status
        FROM offer o
        LEFT JOIN vehicle v          ON v.id = o.vehicle_id
        LEFT JOIN security_type st   ON st.id = o.security_type_id
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p      ON p.id = pr.participant_id
        WHERE (o.registered_at IS NULL OR o.registered_at BETWEEN %s AND %s)
        ORDER BY o.registered_at DESC NULLS LAST
    """, [since, until])

    if status_filter:
        df = df[df["status"].isin(status_filter)]
    if coordinator_filter and coordinator_filter != "Todos":
        df = df[df["coordinator"] == coordinator_filter]
    if audience_filter and audience_filter != "Todos":
        df = df[df["target_audience"] == audience_filter]

    return df


def get_offer_detail(offer_id: int) -> dict:
    df = _query("SELECT * FROM offer WHERE id = %s", [offer_id])
    return df.iloc[0].to_dict() if not df.empty else {}


def get_kpis() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM offer").fetchone()[0]
        in_progress = conn.execute("""
            SELECT COUNT(*) FROM offer
            WHERE (ends_at IS NULL OR ends_at >= CURRENT_DATE)
              AND started_at IS NOT NULL
              AND registered_at <= CURRENT_DATE
        """).fetchone()[0]
        # Valor_Total_Registrado (CVM) = maximum authorized amount per shelf program,
        # not the amount effectively raised in a single placement.
        # Median and typical-range average are the only meaningful volume aggregates.
        vol_row = conn.execute("""
            SELECT
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_volume)::numeric   AS median_vol,
                ROUND(AVG(total_volume) FILTER (WHERE total_volume BETWEEN 50e6 AND 500e6)::numeric / 1e6, 0) AS avg_typical_m,
                COUNT(*) FILTER (WHERE total_volume BETWEEN 50e6 AND 500e6)           AS typical_count
            FROM offer WHERE total_volume > 0
        """).fetchone()
        funds = conn.execute(
            "SELECT COUNT(*) FROM vehicle WHERE asset_class_id = (SELECT id FROM asset_class WHERE code='FII')"
        ).fetchone()[0]
        players = conn.execute(
            "SELECT COUNT(DISTINCT participant_id) FROM participant_role WHERE role='coordinator_leader'"
        ).fetchone()[0]
    return {
        "total_offers":    total,
        "in_progress":     in_progress,
        "median_volume":   float(vol_row[0] or 0),
        "avg_typical_m":   float(vol_row[1] or 0),
        "typical_count":   int(vol_row[2] or 0),
        "total_funds":     funds,
        "total_players":   players,
    }


# ─── Players ─────────────────────────────────────────────────────────────────

def get_players_summary(since: date) -> pd.DataFrame:
    return _query("""
        SELECT
            COALESCE(p.name, 'Não identificado')   AS coordinator,
            COUNT(DISTINCT o.id)                    AS total_offers,
            COALESCE(SUM(o.total_volume), 0)        AS total_volume,
            COUNT(DISTINCT o.vehicle_id)            AS unique_funds,
            MIN(o.registered_at)                    AS first_offer,
            MAX(o.registered_at)                    AS last_offer
        FROM offer o
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p       ON p.id = pr.participant_id
        WHERE o.registered_at >= %s
        GROUP BY COALESCE(p.name, 'Não identificado')
        ORDER BY total_offers DESC
    """, [since])


def get_players_timeline(since: date) -> pd.DataFrame:
    return _query("""
        SELECT
            DATE_TRUNC('month', o.registered_at)::date AS month,
            COALESCE(p.name, 'Não identificado')        AS coordinator,
            COUNT(*)                                     AS offers,
            COALESCE(SUM(o.total_volume), 0)            AS volume
        FROM offer o
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p       ON p.id = pr.participant_id
        WHERE o.registered_at >= %s AND o.registered_at IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """, [since])


def get_coordinator_list() -> list[str]:
    df = _query("""
        SELECT DISTINCT p.name
        FROM participant_role pr
        JOIN participant p ON p.id = pr.participant_id
        WHERE pr.role = 'coordinator_leader'
        ORDER BY p.name
    """)
    return ["Todos"] + df["name"].tolist()


# ─── FII market data (Fundamentus) ──────────────────────────────────────────

def get_fii_metrics() -> pd.DataFrame:
    return _query("""
        SELECT
            v.ticker,
            v.name,
            v.segment,
            ds.dy_12m,
            ds.pvp,
            ds.price,
            ds.vacancy_rate,
            ds.snapshot_date
        FROM daily_snapshot ds
        JOIN vehicle v ON v.id = ds.vehicle_id
        WHERE ds.snapshot_date = (
            SELECT MAX(snapshot_date) FROM daily_snapshot
        )
        ORDER BY ds.dy_12m DESC NULLS LAST
    """)


# ─── Institutional activity ──────────────────────────────────────────────────

def get_institutional_activity(since: date) -> pd.DataFrame:
    return _query("""
        SELECT
            o.cvm_registration,
            COALESCE(v.name, 'Desconhecido')      AS fund_name,
            v.ticker,
            o.registered_at,
            o.started_at,
            o.ends_at,
            o.total_volume,
            o.financial_terms_available,
            o.financial_terms_note,
            COALESCE(p.name, 'Não identificado')  AS coordinator,
            o.target_audience,
            o.distribution_regime,
            o.extra->>'raw_status'                 AS cvm_status,
            o.extra->>'tipo_requerimento'           AS tipo_requerimento,
            o.extra->>'grupo_coordenador'           AS grupo_coordenador
        FROM offer o
        LEFT JOIN vehicle v          ON v.id = o.vehicle_id
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p      ON p.id = pr.participant_id
        WHERE o.registered_at >= %s
        ORDER BY o.registered_at DESC NULLS LAST
    """, [since])


def get_concentration_by_coordinator(since: date) -> pd.DataFrame:
    df = get_players_summary(since)
    total_offers = df["total_offers"].sum()
    total_volume = df["total_volume"].sum()
    if total_offers > 0:
        df["share_offers_pct"] = (df["total_offers"] / total_offers * 100).round(1)
    if total_volume > 0:
        df["share_volume_pct"] = (df["total_volume"] / total_volume * 100).round(1)
    return df


# ─── Alerts ──────────────────────────────────────────────────────────────────

def get_alerts(days_back: int = 30, only_unread: bool = False) -> pd.DataFrame:
    since = date.today() - timedelta(days=days_back)
    unread_clause = "AND NOT a.is_read" if only_unread else ""
    return _query(f"""
        SELECT
            a.id,
            a.type,
            a.is_read,
            a.created_at,
            COALESCE(v.name, '')      AS fund_name,
            v.ticker,
            a.detail
        FROM alert_log a
        LEFT JOIN vehicle v  ON v.id  = a.vehicle_id
        WHERE a.created_at >= %s {unread_clause}
        ORDER BY a.created_at DESC
    """, [since])


def mark_alerts_read(alert_ids: list[int]) -> None:
    if not alert_ids:
        return
    from src.db.connection import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE alert_log SET is_read = TRUE WHERE id = %s",
                [(i,) for i in alert_ids],
            )
        conn.commit()


def get_alert_counts() -> dict:
    with get_conn() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0]
        unread  = conn.execute("SELECT COUNT(*) FROM alert_log WHERE NOT is_read").fetchone()[0]
        by_type = conn.execute("""
            SELECT type, COUNT(*) FROM alert_log GROUP BY type ORDER BY COUNT(*) DESC
        """).fetchall()
    return {
        "total": total,
        "unread": unread,
        "by_type": {r[0]: r[1] for r in by_type},
    }


# ─── CDI history (for Macro page) ────────────────────────────────────────────

def get_cdi_history(since: date) -> pd.DataFrame:
    return _query("""
        SELECT metric_date, value AS cdi_daily
        FROM market_metric
        WHERE code = 'CDI' AND metric_date >= %s
        ORDER BY metric_date
    """, [since])


def get_ipca_history(since: date) -> pd.DataFrame:
    return _query("""
        SELECT metric_date, value AS ipca_monthly
        FROM market_metric
        WHERE code = 'IPCA' AND metric_date >= %s
        ORDER BY metric_date
    """, [since])
