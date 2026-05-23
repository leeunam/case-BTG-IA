"""
CVM FII Monthly Informe collector.

Downloads CVM open data monthly reports (inf_mensal_fii) for FII funds.
Three CSVs per year: geral (identity), complemento (PL/DY/cotistas), ativo_passivo.
Joins them, filters to known vehicles, stores references in document table.

Source: https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/
"""
import io
import zipfile
from datetime import date

import httpx
import pandas as pd
from psycopg.types.json import Jsonb

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

_BASE_URL = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS"
_YEARS = [date.today().year]  # current year only — informes from last month are sufficient


class CVMDocsCollector(BaseCollector):
    source_code = "cvm_dados_abertos"
    source_name = "CVM Informes Mensais FII"

    def _run(self) -> dict:
        df = self.get_informe_dataframe()
        if df.empty:
            return {"collected": 0, "new": 0, "updated": 0}

        known_cnpjs = self._get_known_cnpjs()
        if known_cnpjs:
            df = df[df["CNPJ_Fundo_Classe"].isin(known_cnpjs)].copy()

        print(f"  {len(df):,} fund-months for known vehicles")
        self._save_raw(df)

        new, updated = self._register_documents(df)
        return {"collected": len(df), "new": new, "updated": updated}

    # ─── Public: fetch joined informe ─────────────────────────────────────────

    def get_informe_dataframe(self) -> pd.DataFrame:
        frames = []
        for year in _YEARS:
            url = f"{_BASE_URL}/inf_mensal_fii_{year}.zip"
            print(f"  Downloading {year} informe...")
            try:
                frames.append(self._download_year(url))
                print(f"    OK")
            except Exception as exc:
                print(f"    Warning: {exc}")
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        combined.sort_values(
            ["CNPJ_Fundo_Classe", "Data_Referencia"],
            ascending=[True, False],
            inplace=True,
        )
        return combined

    # ─── Download ─────────────────────────────────────────────────────────────

    def _download_year(self, url: str) -> pd.DataFrame:
        resp = httpx.get(url, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))

        def read(keyword: str) -> pd.DataFrame:
            name = next(n for n in zf.namelist() if keyword in n)
            with zf.open(name) as f:
                return pd.read_csv(
                    f, sep=";", encoding="latin-1",
                    engine="python", on_bad_lines="skip",
                )

        df_g = read("geral")
        df_c = read("complemento")
        df_a = read("ativo_passivo")

        key = ["CNPJ_Fundo_Classe", "Data_Referencia"]
        for df in (df_g, df_c, df_a):
            df.sort_values("Versao", ascending=False, inplace=True)
            df.drop_duplicates(key, inplace=True)

        df = df_g.merge(df_c, on=key, how="left", suffixes=("", "_c"))
        df = df.merge(df_a, on=key, how="left", suffixes=("", "_a"))
        return df

    # ─── DB helpers ───────────────────────────────────────────────────────────

    def _get_known_cnpjs(self) -> set[str]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT cnpj FROM issuer WHERE cnpj IS NOT NULL"
            ).fetchall()
        return {r[0] for r in rows}

    def _register_documents(self, df: pd.DataFrame) -> tuple[int, int]:
        """Store a doc record per fund-month for later embedding."""
        new_count = upd_count = 0
        with get_conn() as conn:
            for _, row in df.iterrows():
                cnpj   = str(row.get("CNPJ_Fundo_Classe", "") or "").strip()
                period = str(row.get("Data_Referencia",   "") or "").strip()
                if not cnpj or not period:
                    continue

                v_row = conn.execute("""
                    SELECT v.id FROM vehicle v
                    JOIN issuer i ON i.id = v.issuer_id
                    WHERE i.cnpj = %s LIMIT 1
                """, (cnpj,)).fetchone()
                if not v_row:
                    continue
                vehicle_id = v_row[0]

                existing = conn.execute("""
                    SELECT id FROM document
                    WHERE vehicle_id = %s AND type = 'inf_mensal'
                      AND extra->>'period' = %s
                """, (vehicle_id, period)).fetchone()

                if not existing:
                    year = period[:4]
                    conn.execute("""
                        INSERT INTO document
                            (vehicle_id, type, source_url, extracted_at,
                             extraction_status, extra)
                        VALUES (%s, 'inf_mensal', %s, NOW(), 'pending', %s)
                    """, (
                        vehicle_id,
                        f"{_BASE_URL}/inf_mensal_fii_{year}.zip",
                        Jsonb({"period": period, "cnpj": cnpj}),
                    ))
                    new_count += 1
                else:
                    upd_count += 1

            conn.commit()

        return new_count, upd_count
