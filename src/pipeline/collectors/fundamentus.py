"""
Fundamentus FII collector.
Parses the FII results table from fundamentus.com.br — server-rendered HTML, no JS needed.
Provides: ticker, segment, price, DY, P/VP, vacancy rate, market cap.
"""
import io
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

_URL = "https://www.fundamentus.com.br/fii_resultado.php"
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

_PCT_COLS = ["Dividend Yield", "FFO Yield", "Cap Rate", "Vacância Média"]
_NUM_COLS = ["Cotação", "P/VP", "Valor de Mercado", "Liquidez", "Qtd de imóveis",
             "Preço do m2", "Aluguel por m2"]


def _pct_to_float(val) -> float | None:
    """Convert Brazilian percentage string or already-parsed float to float."""
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("%", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _num_to_float(val) -> float | None:
    """Convert Brazilian number string (1.234,56) or already-parsed float to float."""
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        # pandas already parsed with thousands/decimal settings — use as-is
        return float(val)
    s = str(val).replace(".", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


class FundamentusCollector(BaseCollector):
    source_code = "fundamentus"
    source_name = "Fundamentus FII"

    def _run(self) -> dict:
        df = self._fetch()
        print(f"  {len(df)} FIIs fetched from Fundamentus")

        self._save_raw(df)
        new, updated = self._upsert(df)
        return {"collected": len(df), "new": new, "updated": updated}

    def _fetch(self) -> pd.DataFrame:
        resp = httpx.get(_URL, headers=_HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "lxml", from_encoding="iso-8859-1")
        table = soup.find("table", id="tabelaResultado")
        if table is None:
            raise RuntimeError("Table #tabelaResultado not found on Fundamentus page")

        df = pd.read_html(io.StringIO(str(table)), decimal=",", thousands=".")[0]

        # Normalize column names
        df.columns = [str(c).strip() for c in df.columns]
        return df

    def _upsert(self, df: pd.DataFrame) -> tuple[int, int]:
        fii_ac_id = self._get_fii_ac_id()
        source_id = self._get_source_id()

        ticker_col = "Papel"
        segment_col = "Segmento"
        dy_col = "Dividend Yield"
        pvp_col = "P/VP"
        price_col = "Cotação"
        vacancy_col = "Vacância Média"
        mktcap_col = "Valor de Mercado"

        rows_before = self._count_vehicles(fii_ac_id)
        snapshot_rows = []

        with get_conn() as conn:
            for _, row in df.iterrows():
                ticker = str(row.get(ticker_col, "") or "").strip()
                if not ticker:
                    continue

                segment = str(row.get(segment_col, "") or "").strip() or None

                # Upsert vehicle by ticker
                conn.execute(
                    """
                    INSERT INTO vehicle (asset_class_id, ticker, name, segment)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (ticker) WHERE ticker IS NOT NULL
                    DO UPDATE SET
                        segment    = COALESCE(EXCLUDED.segment, vehicle.segment),
                        updated_at = NOW()
                    """,
                    (fii_ac_id, ticker, ticker, segment),
                )
                v_row = conn.execute(
                    "SELECT id FROM vehicle WHERE ticker = %s", (ticker,)
                ).fetchone()
                if not v_row:
                    continue
                vehicle_id = v_row[0]

                # Build snapshot — cap outliers that indicate corrupted source data
                pvp = _num_to_float(row.get(pvp_col))
                price = _num_to_float(row.get(price_col))
                snapshot_rows.append((
                    vehicle_id,
                    pd.Timestamp.now().date(),
                    _pct_to_float(row.get(dy_col)),
                    None,   # dy_6m not available from Fundamentus
                    None,   # dy_3m
                    pvp if pvp is not None and abs(pvp) < 5000 else None,
                    price if price is not None and price < 1_000_000 else None,
                    _num_to_float(row.get(mktcap_col)),
                    _pct_to_float(row.get(vacancy_col)),
                    source_id,
                ))

            conn.commit()

            # Bulk upsert daily snapshots
            if snapshot_rows:
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO daily_snapshot
                            (vehicle_id, snapshot_date, dy_12m, dy_6m, dy_3m,
                             pvp, price, pl_total, vacancy_rate, source_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (vehicle_id, snapshot_date, source_id)
                        DO UPDATE SET
                            dy_12m       = EXCLUDED.dy_12m,
                            pvp          = EXCLUDED.pvp,
                            price        = EXCLUDED.price,
                            pl_total     = EXCLUDED.pl_total,
                            vacancy_rate = EXCLUDED.vacancy_rate
                        """,
                        snapshot_rows,
                    )
                conn.commit()

        rows_after = self._count_vehicles(fii_ac_id)
        new_count = rows_after - rows_before
        return max(new_count, 0), max(len(df) - new_count, 0)

    def _get_fii_ac_id(self) -> int:
        with get_conn() as conn:
            return conn.execute("SELECT id FROM asset_class WHERE code='FII'").fetchone()[0]

    def _count_vehicles(self, ac_id: int) -> int:
        with get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM vehicle WHERE asset_class_id = %s", (ac_id,)
            ).fetchone()[0]
