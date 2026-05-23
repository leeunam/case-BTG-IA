"""
BCB collector — CDI, IPCA, Selic (séries históricas) + Focus (projeções).
Uses python-bcb library which wraps BCB's public REST API.
"""
from datetime import date, timedelta

import pandas as pd

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

# SGS series codes
# Source attribution for display/tooltips:
#   SELIC_META / SELIC → BCB (set by COPOM)
#   CDI                → B3/CETIP primary; BCB/SGS série 12 mirrors it
#   IPCA               → IBGE primary; BCB/SGS série 433 mirrors it
#   IGPM               → FGV primary; BCB/SGS série 189 mirrors it
_SGS_SERIES = {
    "SELIC_META": 13521,  # Meta Selic definida pelo COPOM (% a.a.) — preferred for dashboard display
    "SELIC":      11,     # Taxa Selic efetiva diária (% a.a.)
    "CDI":        12,     # Taxa CDI diária (% a.a.) — primary source: B3/CETIP
    "IPCA":       433,    # IPCA mensal (%) — primary source: IBGE
    "IGPM":       189,    # IGP-M mensal (%) — primary source: FGV
}

def _rolling_start() -> str:
    """1 year back from today — covers the 12-month IPCA/Selic/CDI charts.
    Macro indicators need 1 year of history; offers/FII data uses 30 days."""
    from datetime import date, timedelta
    return (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")


class BCBCollector(BaseCollector):
    source_code = "bcb_sgs"
    source_name = "BCB SGS"

    def _run(self) -> dict:
        from bcb import sgs

        start = _rolling_start()
        total_new = total_updated = 0

        all_frames = []

        for code, series_id in _SGS_SERIES.items():
            print(f"  Fetching {code} (series {series_id})...")
            try:
                df = sgs.get({code: series_id}, start=start)
                df = df.reset_index()
                df.columns = ["metric_date", "value"]
                df["code"] = code
                df = df.dropna(subset=["value"])
                all_frames.append(df)
                print(f"    → {len(df):,} records")
            except Exception as exc:
                print(f"    Warning: {code} failed — {exc}")

        if all_frames:
            raw = pd.concat(all_frames, ignore_index=True)
            self._save_raw(raw)
            n, u = self._upsert_metrics(raw)
            total_new += n
            total_updated += u

        # Focus projections (separate source code)
        focus_new, focus_updated = self._collect_focus()
        total_new += focus_new
        total_updated += focus_updated

        return {
            "collected": total_new + total_updated,
            "new": total_new,
            "updated": total_updated,
        }

    def _collect_focus(self) -> tuple[int, int]:
        focus_source_id = self._get_focus_source_id()
        try:
            from bcb import Expectativas
            em = Expectativas()
            ep = em.get_endpoint("ExpectativasMercadoAnuais")

            frames = []
            for indicador, code in [("IPCA", "IPCA_PROJ"), ("Selic", "CDI_PROJ")]:
                df = (
                    ep.query()
                    .filter(ep.Indicador == indicador)
                    .filter(ep.Data >= _rolling_start())
                    .orderby(ep.Data.desc())
                    .limit(250)
                    .collect()
                )
                if df is not None and not df.empty:
                    df = df.rename(columns={"Data": "metric_date", "Media": "value"})
                    df["code"] = code
                    frames.append(df[["metric_date", "value", "code"]])

            if not frames:
                return 0, 0

            all_df = pd.concat(frames, ignore_index=True).dropna(subset=["value"])
            return self._upsert_metrics(all_df, source_id=focus_source_id)
        except Exception as exc:
            print(f"  Warning: Focus projections failed — {exc}")
            return 0, 0

    def _upsert_metrics(self, df: pd.DataFrame, source_id: int | None = None) -> tuple[int, int]:
        if source_id is None:
            source_id = self._get_source_id()

        rows = [
            (row["code"], pd.Timestamp(row["metric_date"]).date(), float(row["value"]), source_id)
            for _, row in df.iterrows()
            if pd.notna(row["value"])
        ]

        if not rows:
            return 0, 0

        with get_conn() as conn:
            # Count existing before upsert
            existing = conn.execute(
                "SELECT COUNT(*) FROM market_metric WHERE source_id = %s", (source_id,)
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
                "SELECT COUNT(*) FROM market_metric WHERE source_id = %s", (source_id,)
            ).fetchone()[0]

        new = after - existing
        updated = len(rows) - new
        return max(new, 0), max(updated, 0)

    def _get_focus_source_id(self) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM source WHERE code = 'bcb_focus'"
            ).fetchone()
        if not row:
            raise RuntimeError("Source 'bcb_focus' not found in DB.")
        return row[0]
