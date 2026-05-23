from datetime import date
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from src.api.deps import DbConn, Period
from src.api.schemas.offer import OfferItem, OfferList, IndicatorData, CompareOffer

router = APIRouter(prefix="/offers", tags=["offers"])


def _row_to_offer(row: tuple, participants: list[str]) -> OfferItem:
    return OfferItem(
        id=row[0], cvm_registration=row[1],
        name=row[2], ticker=row[3],
        offer_type="ipo" if row[4] else "follow_on",
        status=row[5],
        total_volume=float(row[6]) if row[6] else None,
        fund_type=row[7], segment=row[8],
        manager=row[9], administrator=row[10],
        lead_coordinator=row[11],
        participants=participants,
        distribution_rite=row[12],
        financial_terms_available=bool(row[13]) if row[13] is not None else True,
        start_date=row[14], registered_at=row[15], updated_at=row[16],
    )


@router.get("", response_model=OfferList)
def list_offers(
    db: DbConn,
    dates: Period,
    status: str = Query("ongoing"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    start, end = dates
    # status mapping
    status_filter = {
        "ongoing": "AND o.status IN ('active', 'pending')",
        "new":     f"AND o.registered_at = '{date.today()}'",
        "closed":  "AND o.status = 'closed'",
        "cancelled":"AND o.status = 'cancelled'",
        "all":     "",
    }.get(status, "AND o.status IN ('active', 'pending')")

    base_where = f"WHERE o.registered_at BETWEEN %s AND %s {status_filter}"
    offset = (page - 1) * page_size

    total = db.execute(
        f"SELECT COUNT(*) FROM offer o {base_where}", (start, end)
    ).fetchone()[0]

    rows = db.execute(f"""
        SELECT
            o.id, o.cvm_registration,
            COALESCE(v.name, 'Desconhecido'),
            v.ticker, o.is_ipo, o.status,
            o.total_volume, v.fund_type, v.segment,
            g.name AS manager, a.name AS administrator,
            p.name AS coordinator,
            o.distribution_rite, o.financial_terms_available,
            o.started_at, o.registered_at, o.updated_at
        FROM offer o
        LEFT JOIN vehicle v ON v.id = o.vehicle_id
        LEFT JOIN participant g ON g.id = v.gestor_id
        LEFT JOIN participant a ON a.id = v.administrador_id
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p ON p.id = pr.participant_id
        {base_where}
        ORDER BY o.registered_at DESC NULLS LAST, o.total_volume DESC NULLS LAST
        LIMIT %s OFFSET %s
    """, (start, end, page_size, offset)).fetchall()

    items = []
    for row in rows:
        offer_id = row[0]
        part_rows = db.execute("""
            SELECT p.short_name FROM participant_role pr
            JOIN participant p ON p.id = pr.participant_id
            WHERE pr.offer_id = %s AND pr.role != 'coordinator_leader'
            LIMIT 5
        """, (offer_id,)).fetchall()
        participants = [r[0] or "" for r in part_rows if r[0]]
        items.append(_row_to_offer(row, participants))

    return OfferList(items=items, page=page, page_size=page_size, total_count=total)


@router.get("/{offer_id}/indicators", response_model=IndicatorData)
def get_indicators(offer_id: int, db: DbConn):
    offer = db.execute(
        "SELECT vehicle_id, is_ipo, unit_price FROM offer WHERE id = %s", (offer_id,)
    ).fetchone()
    if not offer:
        raise HTTPException(404, "Offer not found")

    vehicle_id, is_ipo, unit_price = offer

    ds = db.execute("""
        SELECT dy_12m, dy_6m, pvp, price, pl_total, vacancy_rate,
               volume_daily, nav_per_unit, monthly_return, snapshot_date
        FROM daily_snapshot
        WHERE vehicle_id = %s
        ORDER BY snapshot_date DESC LIMIT 1
    """, (vehicle_id,)).fetchone() if vehicle_id else None

    if not ds:
        return IndicatorData(
            dy_12m=None, dy_6m=None, pvp=None, price=None, pl_total=None,
            vacancy_rate=None, volume_daily=None, nav_per_unit=None,
            monthly_return=None, unit_price=unit_price and float(unit_price),
            market_price=None, spread_pct=None, snapshot_date=None,
        )

    market_price = ds[3] and float(ds[3])
    offer_price  = unit_price and float(unit_price)
    spread = None
    if market_price and offer_price:
        spread = (offer_price - market_price) / market_price * 100

    return IndicatorData(
        dy_12m=ds[0] and float(ds[0]),
        dy_6m=ds[1] and float(ds[1]),
        pvp=ds[2] and float(ds[2]),
        price=market_price,
        pl_total=ds[4] and float(ds[4]),
        vacancy_rate=ds[5] and float(ds[5]),
        volume_daily=ds[6] and float(ds[6]),
        nav_per_unit=ds[7] and float(ds[7]),
        monthly_return=ds[8] and float(ds[8]),
        unit_price=offer_price,
        market_price=market_price,
        spread_pct=spread,
        snapshot_date=ds[9],
    )


@router.get("/compare", response_model=list[CompareOffer])
def compare_offers(offer_ids: str = Query(...), db: DbConn = None):
    ids = [int(x.strip()) for x in offer_ids.split(",") if x.strip()]
    if len(ids) != 2:
        raise HTTPException(400, "Exactly 2 offer IDs required")
    result = []
    for oid in ids:
        rows = db.execute(f"""
            SELECT
                o.id, o.cvm_registration,
                COALESCE(v.name, 'Desconhecido'), v.ticker, o.is_ipo, o.status,
                o.total_volume, v.fund_type, v.segment,
                g.name, a.name, p.name, o.distribution_rite,
                o.financial_terms_available, o.started_at, o.registered_at, o.updated_at
            FROM offer o
            LEFT JOIN vehicle v ON v.id = o.vehicle_id
            LEFT JOIN participant g ON g.id = v.gestor_id
            LEFT JOIN participant a ON a.id = v.administrador_id
            LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
            LEFT JOIN participant p ON p.id = pr.participant_id
            WHERE o.id = %s
        """, (oid,)).fetchone()
        if not rows:
            raise HTTPException(404, f"Offer {oid} not found")
        offer = _row_to_offer(rows, [])
        from src.api.routers.offers import get_indicators
        indicators = get_indicators(oid, db)
        result.append(CompareOffer(offer=offer, indicators=indicators))
    return result
