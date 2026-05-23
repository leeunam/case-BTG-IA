from fastapi import APIRouter, Query
from src.api.deps import DbConn, Period
from src.api.schemas.macro import (
    MacroKpi, IpcaMonthlyPoint, PlayerItem,
    TopPlayerInsight, OffersByCoordinator, FundVolume,
)

router = APIRouter(prefix="/general-scenario", tags=["general-scenario"])


@router.get("/macro-kpis", response_model=list[MacroKpi])
def get_macro_kpis(db: DbConn):
    codes = {
        "SELIC_META": ("Meta Selic (COPOM)", "% a.a.", "BCB"),
        "CDI":        ("CDI diário",          "% a.a.", "B3/CETIP via BCB/SGS"),
        "IPCA":       ("IPCA mensal",         "% a.m.", "IBGE via BCB/SGS"),
        "IPCA_PROJ":  ("IPCA projetado",      "% a.a.", "BCB Focus"),
        "CDI_PROJ":   ("Selic projetada",     "% a.a.", "BCB Focus"),
        "IFIX":       ("IFIX",                "pts",    "B3 via Yahoo Finance"),
    }
    result = []
    for code, (label, unit, source) in codes.items():
        row = db.execute("""
            SELECT value, metric_date FROM market_metric
            WHERE code = %s ORDER BY metric_date DESC LIMIT 1
        """, (code,)).fetchone()

        if row:
            val = float(row[0])
            if code == "CDI":
                # annualize daily rate
                display = f"{((1 + val/100)**252 - 1)*100:.2f}%"
                unit = "% a.a."
            elif code == "IFIX":
                display = f"{val:,.0f} pts"
            else:
                display = f"{val:.2f}%"
            result.append(MacroKpi(code=code, label=label, value=val,
                                   display_value=display, unit=unit,
                                   metric_date=row[1], source=source))
        else:
            result.append(MacroKpi(code=code, label=label, value=None,
                                   display_value="N/D", unit=unit,
                                   metric_date=None, source=source))
    return result


@router.get("/ipca-monthly", response_model=list[IpcaMonthlyPoint])
def get_ipca_monthly(db: DbConn, months: int = Query(12, ge=3, le=60)):
    rows = db.execute("""
        SELECT TO_CHAR(metric_date, 'YYYY-MM'), value
        FROM market_metric WHERE code = 'IPCA'
        ORDER BY metric_date DESC LIMIT %s
    """, (months,)).fetchall()
    return [IpcaMonthlyPoint(month=r[0], value=float(r[1])) for r in reversed(rows)]


@router.get("/offers-by-coordinator", response_model=list[OffersByCoordinator])
def get_offers_by_coordinator(db: DbConn, dates: Period, limit: int = Query(10)):
    start, end = dates
    rows = db.execute("""
        SELECT COALESCE(p.name, 'Não identificado'),
               COUNT(DISTINCT o.id), COALESCE(SUM(o.total_volume), 0)
        FROM offer o
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p ON p.id = pr.participant_id
        WHERE o.registered_at BETWEEN %s AND %s
        GROUP BY COALESCE(p.name, 'Não identificado')
        ORDER BY 2 DESC LIMIT %s
    """, (start, end, limit)).fetchall()
    return [OffersByCoordinator(coordinator=r[0], count=r[1], volume=float(r[2])) for r in rows]


@router.get("/top-funds-volume", response_model=list[FundVolume])
def get_top_funds_volume(db: DbConn, dates: Period, limit: int = Query(10, le=50)):
    start, end = dates
    rows = db.execute("""
        SELECT COALESCE(v.name, 'Desconhecido'), v.ticker,
               COALESCE(SUM(o.total_volume), 0) AS total_vol
        FROM offer o
        LEFT JOIN vehicle v ON v.id = o.vehicle_id
        WHERE o.registered_at BETWEEN %s AND %s AND o.total_volume IS NOT NULL
        GROUP BY v.name, v.ticker
        ORDER BY total_vol DESC LIMIT %s
    """, (start, end, limit)).fetchall()
    return [FundVolume(name=r[0], ticker=r[1], total_volume=float(r[2])) for r in rows]


@router.get("/players", response_model=list[PlayerItem])
def get_players(db: DbConn, dates: Period, limit: int = Query(20)):
    start, end = dates
    rows = db.execute("""
        SELECT
            COALESCE(p.name, 'Não identificado'),
            COUNT(DISTINCT o.id),
            COALESCE(SUM(o.total_volume), 0),
            COUNT(DISTINCT o.vehicle_id),
            MAX(o.registered_at)
        FROM offer o
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p ON p.id = pr.participant_id
        WHERE o.registered_at BETWEEN %s AND %s
        GROUP BY COALESCE(p.name, 'Não identificado')
        ORDER BY COUNT(DISTINCT o.id) DESC LIMIT %s
    """, (start, end, limit)).fetchall()

    total_offers = sum(r[1] for r in rows) or 1
    total_vol    = sum(float(r[2]) for r in rows) or 1

    return [
        PlayerItem(
            coordinator=r[0],
            total_offers=r[1],
            total_volume=float(r[2]),
            unique_funds=r[3],
            share_qty_pct=round(r[1] / total_offers * 100, 1),
            share_vol_pct=round(float(r[2]) / total_vol * 100, 1),
            last_offer_date=r[4],
        )
        for r in rows
    ]


@router.get("/top-player-insight", response_model=TopPlayerInsight)
def get_top_player_insight(db: DbConn, dates: Period):
    start, end = dates
    row = db.execute("""
        SELECT COALESCE(p.name,'?'),
               COUNT(DISTINCT o.id) AS n,
               COALESCE(SUM(o.total_volume),0) AS vol,
               COUNT(DISTINCT o.vehicle_id)
        FROM offer o
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p ON p.id = pr.participant_id
        WHERE o.registered_at BETWEEN %s AND %s
        GROUP BY COALESCE(p.name,'?')
        ORDER BY vol DESC LIMIT 1
    """, (start, end)).fetchone()

    if not row:
        return TopPlayerInsight(coordinator="N/D", share_vol_pct=0, offer_count=0,
                                dominant_offer_type="N/D", status="not_generated", text=None)

    total_vol = db.execute(
        "SELECT COALESCE(SUM(total_volume),1) FROM offer WHERE registered_at BETWEEN %s AND %s",
        (start, end),
    ).fetchone()[0]

    share = round(float(row[2]) / float(total_vol) * 100, 1)
    dominant = db.execute("""
        SELECT CASE WHEN o.is_ipo THEN 'IPO' ELSE 'Follow-on' END, COUNT(*)
        FROM offer o
        JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        JOIN participant p ON p.id = pr.participant_id
        WHERE p.name = %s AND o.registered_at BETWEEN %s AND %s
        GROUP BY 1 ORDER BY 2 DESC LIMIT 1
    """, (row[0], start, end)).fetchone()

    return TopPlayerInsight(
        coordinator=row[0], share_vol_pct=share, offer_count=row[1],
        dominant_offer_type=dominant[0] if dominant else "N/D",
        status="not_generated", text=None,
    )
