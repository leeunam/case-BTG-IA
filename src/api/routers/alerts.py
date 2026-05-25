from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from src.api.deps import DbConn, Period
from src.api.schemas.alert import AlertItem, AlertList, AlertSummary

router = APIRouter(prefix="/alerts", tags=["alerts"])

_ALERT_TYPE_LABELS = {
    "new_offer":         "Nova oferta",
    "status_change":     "Mudança de status",
    "volume_change":     "Alteração de volume",
    "collection_failed": "Falha de coleta",
    "source_stale":      "Fonte desatualizada",
    "data_inconsistency":"Inconsistência de dados",
    "concentration":     "Concentração de mercado",
    "data_gap":          "Dado indisponível",
}


def _fmt_detail(alert_type: str, detail: dict) -> str:
    if alert_type == "status_change":
        return f"Status: {detail.get('old_status','?')} → {detail.get('new_status','?')}"
    if alert_type == "new_offer":
        vol = detail.get("total_volume")
        return f"Vol. autorizado: R${vol/1e6:.0f}M" if vol else "Nova oferta registrada"
    if alert_type == "collection_failed":
        return detail.get("error", "Erro de coleta")
    return str(detail) if detail else _ALERT_TYPE_LABELS.get(alert_type, alert_type)


@router.get("/summary", response_model=AlertSummary)
def get_summary(db: DbConn, dates: Period):
    start, end = dates
    row = db.execute("""
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE is_read),
            COUNT(*) FILTER (WHERE NOT is_read)
        FROM alert_log
        WHERE created_at::date BETWEEN %s AND %s
    """, (start, end)).fetchone()
    return AlertSummary(total=row[0], seen=row[1], unseen=row[2])


@router.get("", response_model=AlertList)
def list_alerts(
    db: DbConn,
    dates: Period,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    start, end = dates
    offset = (page - 1) * page_size

    total = db.execute(
        "SELECT COUNT(*) FROM alert_log WHERE created_at::date BETWEEN %s AND %s",
        (start, end),
    ).fetchone()[0]

    rows = db.execute("""
        SELECT
            al.id, al.type, al.offer_id,
            COALESCE(v.name, o.cvm_registration) AS offer_name,
            v.ticker,
            CASE WHEN o.is_ipo THEN 'ipo' ELSE 'follow_on' END AS offer_type,
            al.is_read, al.created_at, al.detail
        FROM alert_log al
        LEFT JOIN offer o ON o.id = al.offer_id
        LEFT JOIN vehicle v ON v.id = COALESCE(al.vehicle_id, o.vehicle_id)
        WHERE al.created_at::date BETWEEN %s AND %s
        ORDER BY al.is_read ASC, al.created_at DESC
        LIMIT %s OFFSET %s
    """, (start, end, page_size, offset)).fetchall()

    items = [
        AlertItem(
            id=r[0], type=r[1], offer_id=r[2],
            offer_name=r[3], ticker=r[4],
            offer_type=r[5] if r[2] else None,
            seen=bool(r[6]), created_at=r[7],
            detail=_fmt_detail(r[1], r[8] or {}),
        )
        for r in rows
    ]
    return AlertList(items=items, page=page, page_size=page_size, total_count=total)


class SeenPayload(BaseModel):
    seen: bool


@router.patch("/{alert_id}/seen")
def mark_seen(alert_id: int, payload: SeenPayload, db: DbConn):
    updated = db.execute(
        "UPDATE alert_log SET is_read = %s WHERE id = %s RETURNING id",
        (payload.seen, alert_id),
    ).fetchone()
    if not updated:
        raise HTTPException(404, "Alert not found")
    db.commit()
    return {"id": alert_id, "seen": payload.seen}


@router.patch("/seen-all")
def mark_all_seen(db: DbConn, dates: Period):
    start, end = dates
    db.execute(
        "UPDATE alert_log SET is_read = TRUE WHERE created_at::date BETWEEN %s AND %s AND NOT is_read",
        (start, end),
    )
    db.commit()
    return {"status": "ok"}
