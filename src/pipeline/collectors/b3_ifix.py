"""
B3 IFIX collector.

IFIX (Índice de Fundos de Investimentos Imobiliários) is calculated and
maintained by B3.

Strategy:
  - Primary: IFIX.SA on Yahoo Finance — returns current day value only
    (Yahoo Finance does not provide historical IFIX data)
  - Historical data: not currently available from a free public source
  - The KPI card on the dashboard shows the current IFIX value (works)
  - The historical chart is skipped (shows N/D) until a better source is found

Data stored: market_metric(code='IFIX', metric_date=today, value=close)
"""
from datetime import date

import pandas as pd

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

# IFIX.SA returns current-day data only on Yahoo Finance
_IFIX_TICKER_CURRENT  = "IFIX.SA"


class IFIXCollector(BaseCollector):
    source_code = "b3_ifix"
    source_name = "B3 IFIX (via Yahoo Finance)"

    def _run(self) -> dict:
        source_id = self._get_source_id()
        df = self._fetch_ifix()
        if df.empty:
            print("  Warning: IFIX not available — KPI card will show N/D")
            return {"collected": 0, "new": 0, "updated": 0}

        self._save_raw(df)
        new, updated = self._upsert_metrics(df, source_id)
        print(f"    IFIX: {len(df)} row(s), {new} new, {updated} updated")
        return {"collected": len(df), "new": new, "updated": updated}

    def _fetch_ifix(self) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError:
            raise RuntimeError("yfinance not installed. Run: pip install yfinance")

        # IFIX.SA gives only the current trading session value
        data = yf.download(
            _IFIX_TICKER_CURRENT,
            period="5d",            # request 5 days but expect only 1 row
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return pd.DataFrame()

        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        df = close.reset_index()
        df.columns = ["metric_date", "value"]
        df["metric_date"] = pd.to_datetime(df["metric_date"]).dt.date
        df = df.dropna(subset=["value"])

        # Keep only today's value (or most recent available)
        if not df.empty:
            df = df.tail(1).reset_index(drop=True)

        return df

    def _upsert_metrics(self, df: pd.DataFrame, source_id: int) -> tuple[int, int]:
        rows = [
            ("IFIX", row["metric_date"], float(row["value"]), source_id)
            for _, row in df.iterrows()
        ]
        if not rows:
            return 0, 0

        with get_conn() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM market_metric WHERE code = 'IFIX' AND source_id = %s",
                (source_id,),
            ).fetchone()[0]

            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO market_metric (code, metric_date, value, source_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (code, metric_date, source_id) DO UPDATE SET value = EXCLUDED.value
                    """,
                    rows,
                )
            conn.commit()

            after = conn.execute(
                "SELECT COUNT(*) FROM market_metric WHERE code = 'IFIX' AND source_id = %s",
                (source_id,),
            ).fetchone()[0]

        new = max(after - existing, 0)
        updated = max(len(rows) - new, 0)
        return new, updated
