from datetime import date
from typing import Optional
from fastapi import APIRouter, Query

from src.api.deps import DbConn, Period
from src.api.schemas.dashboard import (
    DailyInsight, VolumeByPeriod, RankingItem,
    IpoVsFollowOn, TopNewOffer, PipelineHealth, PipelineSourceStatus,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/daily-insight", response_model=DailyInsight)
def get_daily_insight(db: DbConn, target_date: Optional[date] = Query(None)):
    d = target_date or date.today()
    row = db.execute(
        "SELECT insight_date, generated_at, status, text FROM daily_insight WHERE insight_date = %s",
        (d,),
    ).fetchone()
    if not row:
        return DailyInsight(insight_date=d, generated_at=None, status="not_generated", text=None)
    return DailyInsight(insight_date=row[0], generated_at=row[1], status=row[2], text=row[3])


@router.post("/daily-insight/generate")
def trigger_insight_generation(db: DbConn):
    """Trigger AI insight generation for today. Called by the scheduler at 07:00."""
    from src.api.services.insight import generate_daily_insight
    import threading
    threading.Thread(target=generate_daily_insight, daemon=True).start()
    return {"status": "generating", "date": date.today().isoformat()}


@router.get("/volume", response_model=VolumeByPeriod)
def get_volume(db: DbConn, dates: Period, period: str = Query("1m")):
    start, end = dates
    row = db.execute("""
        SELECT
            COALESCE(SUM(total_volume), 0)                                       AS total_volume,
            COUNT(*)                                                             AS offer_count,
            COALESCE(SUM(total_volume) FILTER (WHERE is_ipo = TRUE), 0)         AS ipo_volume,
            COALESCE(SUM(total_volume) FILTER (WHERE is_ipo = FALSE), 0)        AS fo_volume
        FROM offer
        WHERE registered_at BETWEEN %s AND %s
          AND status NOT IN ('cancelled')
    """, (start, end)).fetchone()
    return VolumeByPeriod(
        period=period,
        total_volume=float(row[0]),
        offer_count=int(row[1]),
        ipo_volume=float(row[2]),
        follow_on_volume=float(row[3]),
    )


@router.get("/ranking", response_model=list[RankingItem])
def get_ranking(db: DbConn, dates: Period, limit: int = Query(10)):
    start, end = dates
    rows = db.execute("""
        SELECT
            o.id, COALESCE(v.name, 'Desconhecido') AS name, v.ticker,
            CASE WHEN o.is_ipo THEN 'ipo' ELSE 'follow_on' END AS offer_type,
            COALESCE(o.total_volume, 0) AS total_volume,
            p.name AS coordinator
        FROM offer o
        LEFT JOIN vehicle v ON v.id = o.vehicle_id
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p ON p.id = pr.participant_id
        WHERE o.registered_at BETWEEN %s AND %s
          AND o.status NOT IN ('cancelled')
        ORDER BY o.total_volume DESC NULLS LAST
        LIMIT %s
    """, (start, end, limit)).fetchall()
    return [
        RankingItem(rank=i + 1, name=r[1], ticker=r[2], offer_type=r[3],
                    total_volume=float(r[4]), coordinator=r[5])
        for i, r in enumerate(rows)
    ]


@router.get("/ipo-vs-followon", response_model=IpoVsFollowOn)
def get_ipo_vs_followon(db: DbConn, dates: Period, period: str = Query("1m")):
    start, end = dates
    row = db.execute("""
        SELECT
            COALESCE(SUM(total_volume) FILTER (WHERE is_ipo = TRUE), 0),
            COUNT(*) FILTER (WHERE is_ipo = TRUE),
            COALESCE(SUM(total_volume) FILTER (WHERE is_ipo = FALSE), 0),
            COUNT(*) FILTER (WHERE is_ipo = FALSE)
        FROM offer
        WHERE registered_at BETWEEN %s AND %s
          AND status NOT IN ('cancelled')
    """, (start, end)).fetchone()
    return IpoVsFollowOn(
        period=period,
        ipo_volume=float(row[0]), ipo_count=int(row[1]),
        follow_on_volume=float(row[2]), follow_on_count=int(row[3]),
    )


@router.get("/top-new-offers", response_model=list[TopNewOffer])
def get_top_new_offers(db: DbConn, limit: int = Query(5)):
    today = date.today()
    rows = db.execute("""
        SELECT
            o.id, COALESCE(v.name, 'Desconhecido'), v.ticker,
            CASE WHEN o.is_ipo THEN 'ipo' ELSE 'follow_on' END,
            o.total_volume, p.name, o.registered_at, o.distribution_rite
        FROM offer o
        LEFT JOIN vehicle v ON v.id = o.vehicle_id
        LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
        LEFT JOIN participant p ON p.id = pr.participant_id
        WHERE o.registered_at = %s
        ORDER BY o.total_volume DESC NULLS LAST
        LIMIT %s
    """, (today, limit)).fetchall()
    return [
        TopNewOffer(id=r[0], name=r[1], ticker=r[2], offer_type=r[3],
                    total_volume=r[4] and float(r[4]), coordinator=r[5],
                    registered_at=r[6], distribution_rite=r[7])
        for r in rows
    ]


@router.get("/pipeline-health", response_model=PipelineHealth)
def get_pipeline_health(db: DbConn):
    from datetime import datetime, timezone
    rows = db.execute("""
        SELECT
            s.code, s.name,
            MAX(er.finished_at)  AS last_run,
            (SELECT er2.status FROM extraction_run er2
             WHERE er2.source_id = s.id ORDER BY er2.started_at DESC LIMIT 1) AS last_status
        FROM source s
        LEFT JOIN extraction_run er ON er.source_id = s.id
        GROUP BY s.id, s.code, s.name
        ORDER BY s.code
    """).fetchall()

    now = datetime.now(timezone.utc)
    sources = []
    failed_today = 0
    stale = 0

    for r in rows:
        last_run = r[2]
        hours = None
        is_stale = False
        if last_run:
            hours = (now - last_run.replace(tzinfo=timezone.utc) if last_run.tzinfo is None
                     else now - last_run).total_seconds() / 3600
            is_stale = hours > 26  # more than 1 day + buffer
        else:
            is_stale = True

        if r[3] == "failed":
            failed_today += 1
        if is_stale:
            stale += 1

        sources.append(PipelineSourceStatus(
            source_code=r[0], source_name=r[1],
            last_run_at=last_run, last_status=r[3],
            hours_since_update=round(hours, 1) if hours else None,
            is_stale=is_stale,
        ))

    return PipelineHealth(sources=sources, failed_today=failed_today, stale_sources=stale)
