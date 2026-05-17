"""
B3 FII Listings collector.
Uses an undocumented but stable XHR endpoint that returns JSON.
No authentication required. No Playwright needed.
"""
import httpx
import pandas as pd

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

_B3_FII_URL = (
    "https://sistemaswebb3-listados.b3.com.br"
    "/fundsProxy/fundsCall/GetListedFundsSummary/FII"
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.b3.com.br/",
}


class B3Collector(BaseCollector):
    source_code = "b3_listings"
    source_name = "B3 FII Listings"

    def _run(self) -> dict:
        funds = self._fetch()
        print(f"  B3 returned {len(funds)} FIIs")

        if not funds:
            return {"collected": 0, "new": 0, "updated": 0}

        df = pd.DataFrame(funds)
        self._save_raw(df)

        new, updated = self._upsert_vehicles(df)
        return {"collected": len(funds), "new": new, "updated": updated}

    def _fetch(self) -> list[dict]:
        resp = httpx.get(_B3_FII_URL, headers=_HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()

        data = resp.json()

        if isinstance(data, list):
            return data

        # Defensive: handle wrapped responses
        for key in ("results", "data", "funds", "content"):
            if isinstance(data, dict) and key in data:
                return data[key]

        print(f"  Warning: unexpected B3 response format. Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        return []

    def _upsert_vehicles(self, df: pd.DataFrame) -> tuple[int, int]:
        fii_asset_class_id = self._get_fii_asset_class_id()
        source_id = self._get_source_id()

        # Normalize column names (B3 returns camelCase)
        col_map = {
            "acronym": "acronym",
            "companyName": "name",
            "cnpj": "cnpj",
            "codeCVM": "cvm_code",
            "typeFund": "segment",
            "fundAdministrator": "administrator",
        }
        available = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=available)

        rows_before = self._count_vehicles(fii_asset_class_id)
        new_count = updated_count = 0

        with get_conn() as conn:
            for _, row in df.iterrows():
                ticker = self._build_ticker(row)
                cvm_code = str(row.get("cvm_code", "") or "").strip() or None
                name = str(row.get("name", "") or "").strip()
                segment = str(row.get("segment", "") or "").strip() or None
                cnpj = str(row.get("cnpj", "") or "").strip() or None
                admin = str(row.get("administrator", "") or "").strip() or None

                if not name:
                    continue

                # Upsert issuer (administrator as issuer for B3 data)
                issuer_id = None
                if cnpj:
                    conn.execute(
                        "INSERT INTO issuer (cnpj, name, type) VALUES (%s, %s, 'administradora') "
                        "ON CONFLICT (cnpj) DO UPDATE SET name = EXCLUDED.name",
                        (cnpj, admin or name),
                    )
                    row_id = conn.execute(
                        "SELECT id FROM issuer WHERE cnpj = %s", (cnpj,)
                    ).fetchone()
                    issuer_id = row_id[0] if row_id else None

                extra = {"b3_segment": segment, "administrator": admin}

                conn.execute(
                    """
                    INSERT INTO vehicle (issuer_id, asset_class_id, ticker, cvm_code, name, segment, extra)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker) WHERE ticker IS NOT NULL
                    DO UPDATE SET
                        cvm_code   = COALESCE(EXCLUDED.cvm_code, vehicle.cvm_code),
                        name       = EXCLUDED.name,
                        segment    = COALESCE(EXCLUDED.segment, vehicle.segment),
                        extra      = vehicle.extra || EXCLUDED.extra,
                        updated_at = NOW()
                    """,
                    (
                        issuer_id,
                        fii_asset_class_id,
                        ticker,
                        cvm_code,
                        name,
                        segment,
                        extra,
                    ),
                )

            conn.commit()

        rows_after = self._count_vehicles(fii_asset_class_id)
        new_count = rows_after - rows_before
        updated_count = len(df) - new_count
        return max(new_count, 0), max(updated_count, 0)

    @staticmethod
    def _build_ticker(row: pd.Series) -> str | None:
        acronym = str(row.get("acronym", "") or "").strip()
        if not acronym:
            return None
        # B3 returns "XPML" without the "11" suffix for most FIIs
        if len(acronym) == 4 and acronym.isalpha():
            return f"{acronym}11"
        return acronym

    def _get_fii_asset_class_id(self) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM asset_class WHERE code = 'FII'"
            ).fetchone()
        return row[0]

    def _count_vehicles(self, asset_class_id: int) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM vehicle WHERE asset_class_id = %s", (asset_class_id,)
            ).fetchone()
        return row[0]
