"""
Funds Explorer FII collector — additional market metrics and fund administration.

Scrapes each FII's detail page from fundsexplorer.com.br (server-rendered HTML,
no JavaScript / Playwright required). Adds to daily_snapshot:
  - volume_daily   — average daily trading volume (BRL)
  - nav_per_unit   — valor patrimonial da cota
  - monthly_return — rentabilidade no mês (%)

Also updates vehicle.administrador_id from the administration section when the
administrador CNPJ is available and matches a known participant.

Page URL pattern: https://www.fundsexplorer.com.br/funds/{ticker_lower}

HTML structure (stable across funds):
  div.indicators__box  — each metric card (label in first <p>, value in <b>)
  section.carbon_fields_fiis_administration — administrador info
  div.basicInformation__grid__box           — fund registration data
"""
import re
import time
from datetime import date

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

_BASE_URL      = "https://www.fundsexplorer.com.br/funds/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_REQUEST_DELAY = 0.5    # seconds between requests
_TIMEOUT       = 18     # seconds per request

# Indicator box label → internal field name
_INDICATOR_MAP = {
    "liquidez média diária":  "volume_daily",
    "dividend yield":         "dy_12m",
    "patrimônio líquido":     "pl_total",
    "valor patrimonial":      "nav_per_unit",
    "rentab. no mês":         "monthly_return",
    "p/vp":                   "pvp",
    "último rendimento":      "last_dividend",
}


def _parse_br_number(text: str) -> float | None:
    """Parse Brazilian number formats: '9,7 M' → 9_700_000, '166,49' → 166.49"""
    if not text:
        return None
    text = text.strip().replace("R$", "").replace("%", "").strip()
    multiplier = 1.0
    if text.upper().endswith("B"):
        multiplier = 1e9
        text = text[:-1].strip()
    elif text.upper().endswith("M"):
        multiplier = 1e6
        text = text[:-1].strip()
    elif text.upper().endswith("K"):
        multiplier = 1e3
        text = text[:-1].strip()
    # Handle Brazilian decimal: 1.234,56 → 1234.56  |  1234,56 → 1234.56
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _extract_indicators(soup: BeautifulSoup) -> dict:
    result: dict[str, float | None] = {}
    for box in soup.find_all(class_="indicators__box"):
        paras = box.find_all("p")
        if not paras:
            continue
        label = paras[0].get_text(strip=True).lower()
        value_el = box.find("b")
        if not value_el:
            continue
        # Remove <small> unit text from the value
        for small in value_el.find_all("small"):
            small.decompose()
        raw_value = value_el.get_text(strip=True)
        field = _INDICATOR_MAP.get(label)
        if field:
            result[field] = _parse_br_number(raw_value)
    return result


def _extract_admin(soup: BeautifulSoup) -> dict:
    """Extract administrador name and CNPJ from the administration section."""
    section = soup.find(class_="carbon_fields_fiis_administration")
    if not section:
        return {}
    name_el = section.find(class_="informations__adm__name")
    cnpj_el = section.find(class_="informations__adm__doc")
    return {
        "admin_name": name_el.get_text(strip=True) if name_el else None,
        "admin_cnpj": cnpj_el.get_text(strip=True) if cnpj_el else None,
    }


def _extract_basic_info(soup: BeautifulSoup) -> dict:
    """Extract fund registration data from the basicInformation grid."""
    result: dict = {}
    label_map = {
        "cnpj":                  "cnpj",
        "segmento anbima":       "segment_anbima",
        "tipo de gestão":        "fund_management_type",
        "cotas emitidas":        "units_issued",
        "número de cotistas":    "num_shareholders",
        "taxa de administração": "admin_fee",
    }
    for box in soup.find_all(class_="basicInformation__grid__box"):
        text = box.get_text(" ", strip=True)
        for label, key in label_map.items():
            if text.lower().startswith(label):
                value = text[len(label):].strip()
                result[key] = value
                break
    return result


class FundsExplorerCollector(BaseCollector):
    source_code = "funds_explorer"
    source_name = "Funds Explorer"

    def _run(self) -> dict:
        source_id = self._get_source_id()
        tickers   = self._get_known_tickers()
        print(f"  Collecting metrics for {len(tickers)} tickers...")

        today        = date.today()
        snapshot_rows: list[tuple] = []
        raw_records:   list[dict]  = []
        skipped = 0

        for i, (ticker, vehicle_id) in enumerate(tickers):
            data = self._fetch_fund(ticker)
            if data is None:
                skipped += 1
                time.sleep(_REQUEST_DELAY)
                continue

            indicators = data["indicators"]
            admin      = data["admin"]
            raw_records.append({"ticker": ticker, **indicators, **admin})

            # Build snapshot row — only include fields that exist in the schema
            snapshot_rows.append((
                vehicle_id,
                today,
                indicators.get("dy_12m"),
                None,                               # dy_6m (not available)
                None,                               # dy_3m (not available)
                indicators.get("pvp"),
                None,                               # price (not available)
                indicators.get("pl_total"),
                None,                               # vacancy_rate (not available)
                source_id,
                indicators.get("volume_daily"),
                indicators.get("nav_per_unit"),
                indicators.get("monthly_return"),
            ))

            # Update administrador_id on vehicle when CNPJ is available
            if admin.get("admin_cnpj"):
                self._update_administrador(vehicle_id, admin["admin_cnpj"], admin.get("admin_name", ""))

            if (i + 1) % 50 == 0:
                print(f"    {i + 1}/{len(tickers)} tickers processed...")
            time.sleep(_REQUEST_DELAY)

        if raw_records:
            self._save_raw(pd.DataFrame(raw_records))

        new, updated = self._upsert_snapshots(snapshot_rows)
        print(f"  Skipped (no data / error): {skipped}")
        return {"collected": len(snapshot_rows), "new": new, "updated": updated}

    # ─── Fetch ────────────────────────────────────────────────────────────────

    def _fetch_fund(self, ticker: str) -> dict | None:
        url = f"{_BASE_URL}{ticker.lower()}"
        try:
            r = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True)
        except httpx.RequestError:
            return None

        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.content, "lxml")
        indicators = _extract_indicators(soup)
        if not indicators:
            return None

        return {
            "indicators": indicators,
            "admin":      _extract_admin(soup),
            "basic":      _extract_basic_info(soup),
        }

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

    def _upsert_snapshots(self, rows: list[tuple]) -> tuple[int, int]:
        if not rows:
            return 0, 0

        with get_conn() as conn:
            source_id = rows[0][9]  # source_id is index 9 in the tuple
            existing  = conn.execute(
                "SELECT COUNT(*) FROM daily_snapshot WHERE source_id = %s AND snapshot_date = CURRENT_DATE",
                (source_id,),
            ).fetchone()[0]

            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO daily_snapshot
                        (vehicle_id, snapshot_date,
                         dy_12m, dy_6m, dy_3m, pvp, price, pl_total,
                         vacancy_rate, source_id,
                         volume_daily, nav_per_unit, monthly_return)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_id, snapshot_date, source_id)
                    DO UPDATE SET
                        dy_12m        = COALESCE(EXCLUDED.dy_12m,        daily_snapshot.dy_12m),
                        pvp           = COALESCE(EXCLUDED.pvp,           daily_snapshot.pvp),
                        pl_total      = COALESCE(EXCLUDED.pl_total,      daily_snapshot.pl_total),
                        volume_daily  = COALESCE(EXCLUDED.volume_daily,  daily_snapshot.volume_daily),
                        nav_per_unit  = COALESCE(EXCLUDED.nav_per_unit,  daily_snapshot.nav_per_unit),
                        monthly_return= COALESCE(EXCLUDED.monthly_return,daily_snapshot.monthly_return)
                    """,
                    rows,
                )
            conn.commit()

            after = conn.execute(
                "SELECT COUNT(*) FROM daily_snapshot WHERE source_id = %s AND snapshot_date = CURRENT_DATE",
                (source_id,),
            ).fetchone()[0]

        new     = max(after - existing, 0)
        updated = max(len(rows) - new, 0)
        return new, updated

    def _update_administrador(self, vehicle_id: int, cnpj: str, name: str) -> None:
        """Upsert participant and link as administrador_id on vehicle."""
        cnpj_clean = re.sub(r"[^\d]", "", cnpj)
        if len(cnpj_clean) != 14:
            return
        formatted = f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:]}"
        try:
            with get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO participant (cnpj, name, short_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cnpj) DO UPDATE SET name = EXCLUDED.name
                    """,
                    (formatted, name, name[:60] if name else None),
                )
                participant_id = conn.execute(
                    "SELECT id FROM participant WHERE cnpj = %s", (formatted,)
                ).fetchone()
                if participant_id:
                    conn.execute(
                        """
                        UPDATE vehicle SET administrador_id = %s
                        WHERE id = %s AND administrador_id IS NULL
                        """,
                        (participant_id[0], vehicle_id),
                    )
                conn.commit()
        except Exception:
            pass  # Non-critical enrichment — don't fail the pipeline
