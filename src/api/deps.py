"""FastAPI dependency injection — DB connection and period parsing."""
from datetime import date, timedelta
from typing import Annotated, Generator

from fastapi import Depends, HTTPException, Query
import psycopg

from src.db.connection import get_conn


def get_db() -> Generator:
    with get_conn() as conn:
        yield conn


DbConn = Annotated[psycopg.Connection, Depends(get_db)]


def parse_period(period: str = Query("1m")) -> tuple[date, date]:
    """Convert period string to (start_date, end_date) tuple."""
    today = date.today()
    mapping = {
        "7d":  timedelta(days=7),
        "15d": timedelta(days=15),
        "1m":  timedelta(days=30),
    }
    delta = mapping.get(period)
    if not delta:
        raise HTTPException(status_code=400, detail=f"Invalid period '{period}'. Use 7d|15d|1m")
    return today - delta, today


Period = Annotated[tuple[date, date], Depends(parse_period)]
