"""
Status Invest FII collector — dividend payment history.

For each known FII ticker, fetches the complete history of individual
dividend payments (rendimentos, amortizações) from Status Invest's
internal JSON API. Stores one row per payment in dividend_payment.

API endpoint (no authentication required):
    GET /fii/companytickerprovents?ticker={TICKER}&chartProventsType=2

Response fields:
    ed  — ex-dividend date (DD/MM/YYYY)
    pd  — payment date (DD/MM/YYYY)
    v   — value per unit (float)
    et  — dividend type string (e.g. "Rendimento", "Amortização")
    adj — adjusted flag (bool)
"""
import time
from datetime import date, datetime

import httpx
import pandas as pd

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

_PROVENTS_URL = "https://statusinvest.com.br/fii/companytickerprovents"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://statusinvest.com.br/fundos-imobiliarios/",
}
_REQUEST_DELAY = 0.35   # seconds between requests (polite rate limiting)
_TIMEOUT       = 12     # seconds per request

# Normalize dividend type strings to canonical codes
_TYPE_MAP = {
    "rendimento":   "rendimento",
    "amortização":  "amortizacao",
    "amortizacao":  "amortizacao",
    "jcp":          "juros_capital_proprio",
    "juros":        "juros_capital_proprio",
    "dividendo":    "dividendo",
    "rendimento tributável": "rendimento_tributavel",
    "tributável":   "rendimento_tributavel",
}


def _normalize_type(raw: str) -> str:
    s = raw.lower().strip()
    for key, val in _TYPE_MAP.items():
        if key in s:
            return val
    return "rendimento"


def _parse_date(s: str) -> date | None:
    if not s or s.strip() in ("-", ""):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


class StatusInvestCollector(BaseCollector):
    source_code = "status_invest"
    source_name = "Status Invest"

    def _run(self) -> dict:
        source_id = self._get_source_id()
        tickers   = self._get_known_tickers()
        print(f"  Collecting dividends for {len(tickers)} tickers...")

        all_rows: list[dict] = []
        skipped = 0

        for i, (ticker, vehicle_id) in enumerate(tickers):
            payments = self._fetch_provents(ticker, vehicle_id, source_id)
            if payments is None:
                skipped += 1
            else:
                all_rows.extend(payments)

            if (i + 1) % 50 == 0:
                print(f"    {i + 1}/{len(tickers)} tickers processed...")
            time.sleep(_REQUEST_DELAY)

        if all_rows:
            df = pd.DataFrame(all_rows)
            self._save_raw(df)

        new, updated = self._upsert_payments(all_rows, source_id)
        print(f"  Skipped (no data / error): {skipped}")
        return {"collected": len(all_rows), "new": new, "updated": updated}

    # ─── Fetch ────────────────────────────────────────────────────────────────

    def _fetch_provents(
        self,
        ticker: str,
        vehicle_id: int,
        source_id: int,
    ) -> list[dict] | None:
        try:
            r = httpx.get(
                _PROVENTS_URL,
                params={"ticker": ticker, "chartProventsType": 2},
                headers={**_HEADERS, "Referer": f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"},
                timeout=_TIMEOUT,
                follow_redirects=True,
            )
        except httpx.RequestError:
            return None

        if r.status_code != 200:
            return None

        try:
            data = r.json()
        except Exception:
            return None

        if not data or not isinstance(data, dict):
            return []

        models = data.get("assetEarningsModels") or []
        if not models:
            return []

        rows = []
        for m in models:
            ex_date = _parse_date(m.get("ed", ""))
            if ex_date is None or m.get("v") is None:
                continue
            value = float(m["v"])
            # Sanity check: FII dividends are typically R$0.01–R$100/cota.
            # Values > 10000 indicate data quality issues; skip them.
            if value < 0 or value > 10_000:
                continue
            rows.append({
                "vehicle_id":     vehicle_id,
                "ex_date":        ex_date,
                "payment_date":   _parse_date(m.get("pd", "")),
                "value_per_unit": value,
                "dividend_type":  _normalize_type(m.get("et", "rendimento")),
                "source_id":      source_id,
            })
        return rows

    # ─── DB helpers ───────────────────────────────────────────────────────────

    def _get_known_tickers(self) -> list[tuple[str, int]]:
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT ticker, id FROM vehicle
                WHERE ticker IS NOT NULL
                  AND asset_class_id = (SELECT id FROM asset_class WHERE code = 'FII')
                ORDER BY ticker
            """).fetchall()
        return [(r[0], r[1]) for r in rows]

    def _upsert_payments(self, rows: list[dict], source_id: int) -> tuple[int, int]:
        if not rows:
            return 0, 0

        with get_conn() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM dividend_payment WHERE source_id = %s", (source_id,)
            ).fetchone()[0]

            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO dividend_payment
                        (vehicle_id, ex_date, payment_date, value_per_unit, dividend_type, source_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_id, ex_date, source_id)
                    DO UPDATE SET
                        payment_date   = EXCLUDED.payment_date,
                        value_per_unit = EXCLUDED.value_per_unit,
                        dividend_type  = EXCLUDED.dividend_type
                    """,
                    [
                        (
                            r["vehicle_id"],
                            r["ex_date"],
                            r["payment_date"],
                            r["value_per_unit"],
                            r["dividend_type"],
                            r["source_id"],
                        )
                        for r in rows
                    ],
                )
            conn.commit()

            after = conn.execute(
                "SELECT COUNT(*) FROM dividend_payment WHERE source_id = %s", (source_id,)
            ).fetchone()[0]

        new     = max(after - existing, 0)
        updated = max(len(rows) - new, 0)
        return new, updated
