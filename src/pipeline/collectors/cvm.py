"""
CVM Dados Abertos collector.
Downloads the official primary-offers ZIP, filters FII offers from both CSVs,
normalizes, and upserts into the canonical schema.

Sources:
  oferta_distribuicao.csv   — full history (1988–today), ICVM 400 / ICVM 476 / RCVM 160
  oferta_resolucao_160.csv  — automatic rite (2023–today), CVM Resolution 160
"""
import io
import re
import zipfile
from datetime import date

import pandas as pd
from psycopg.types.json import Jsonb
import requests

from src.db.connection import get_conn
from src.pipeline.collectors.base import BaseCollector

_ZIP_URL = "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip"
# "QUOTAS DE FUNDO IMOBILIÁRIO" (oferta_distribuicao) or "fundo imobiliário" variants
# Does NOT match CRI ("recebíveis imobiliários") — uses "fundo imobili" prefix
_FII_RE_DIST = re.compile(r"(?i)fundo imobili|FII")
_FII_RE_R160 = re.compile(r"(?i)imobili|FII")
_BACKFILL_YEAR = 2022

# Status mapping for oferta_resolucao_160 Status_Requerimento values
_STATUS_MAP = {
    "DEFERIDO":    "active",
    "ENCERRADO":   "closed",
    "CANCELADO":   "cancelled",
    "INDEFERIDO":  "cancelled",
    "PENDENTE":    "pending",
    "EM ANÁLISE":  "pending",
    "EM ANALISE":  "pending",
}


def _clean_cnpj(val) -> str | None:
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


def _clean_str(val) -> str | None:
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


def _to_date(val) -> date | None:
    if pd.isna(val):
        return None
    try:
        return pd.to_datetime(val, dayfirst=False, errors="coerce").date()
    except Exception:
        return None


def _to_numeric(val):
    if pd.isna(val):
        return None
    try:
        s = str(val).replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return None


def _derive_status(row: pd.Series) -> str:
    today = date.today()
    end = _to_date(row.get("Data_Encerramento_Oferta"))
    start = _to_date(row.get("Data_Inicio_Oferta"))
    if end and end < today:
        return "closed"
    if start:
        return "active"
    return "unknown"


def _derive_status_160(raw_status: str | None) -> str:
    if not raw_status:
        return "unknown"
    normalized = raw_status.strip().upper()
    for key, val in _STATUS_MAP.items():
        if key in normalized:
            return val
    return "unknown"


def _is_restricted(rito: str | None) -> bool:
    if not rito:
        return False
    return bool(re.search(r"(?i)restri|476", rito))


class CVMCollector(BaseCollector):
    source_code = "cvm_dados_abertos"
    source_name = "CVM Dados Abertos"

    def _run(self) -> dict:
        print("  Downloading CVM ZIP...")
        df_dist, df_res = self._download()

        # Filter FIIs — different column and pattern per dataset
        # oferta_distribuicao uses "QUOTAS DE FUNDO IMOBILIÁRIO" in Tipo_Ativo
        # oferta_resolucao_160 uses varied strings in Valor_Mobiliario
        mask_dist = df_dist.get("Tipo_Ativo", pd.Series(dtype=str)).str.contains(_FII_RE_DIST, na=False)
        mask_res  = df_res.get("Valor_Mobiliario", pd.Series(dtype=str)).str.contains(_FII_RE_R160, na=False)

        df_fii_dist = df_dist[mask_dist].copy()
        df_fii_res  = df_res[mask_res].copy()

        # Apply backfill year filter
        df_fii_dist = self._filter_by_year(df_fii_dist, "Data_Registro_Oferta")
        # oferta_resolucao_160 starts at 2023 already, no filter needed

        print(f"  FII offers: {len(df_fii_dist):,} (distribuição) + {len(df_fii_res):,} (resolução 160)")

        raw = pd.concat(
            [
                df_fii_dist.assign(_csv="oferta_distribuicao"),
                df_fii_res.assign(_csv="oferta_resolucao_160"),
            ],
            ignore_index=True,
        )
        self._save_raw(raw)

        new_dist,  upd_dist,  alerts_dist = self._upsert_distribuicao(df_fii_dist)
        new_res,   upd_res,   alerts_res  = self._upsert_resolucao160(df_fii_res)

        all_alerts = alerts_dist + alerts_res
        if all_alerts:
            self._write_alerts(all_alerts)
            print(f"  Alerts written: {len(all_alerts)}")

        total_new = new_dist + new_res
        total_upd = upd_dist + upd_res
        return {"collected": len(raw), "new": total_new, "updated": total_upd}

    # ─── Download ─────────────────────────────────────────────────────────────

    def _download(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        resp = requests.get(_ZIP_URL, timeout=180)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        csv_names = sorted(n for n in zf.namelist() if n.endswith(".csv"))

        def read(name: str) -> pd.DataFrame:
            with zf.open(name) as f:
                return pd.read_csv(
                    f, sep=";", encoding="latin-1",
                    engine="python", on_bad_lines="skip",
                )

        return read(csv_names[0]), read(csv_names[1])

    @staticmethod
    def _filter_by_year(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        if date_col not in df.columns:
            return df
        years = pd.to_datetime(df[date_col], errors="coerce").dt.year
        return df[years >= _BACKFILL_YEAR].copy()

    # ─── Alert helpers ────────────────────────────────────────────────────────

    def _write_alerts(self, alerts: list[dict]) -> None:
        rows = [
            (a["type"], a.get("offer_id"), a.get("vehicle_id"), Jsonb(a.get("detail", {})))
            for a in alerts
        ]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO alert_log (type, offer_id, vehicle_id, detail) VALUES (%s,%s,%s,%s)",
                    rows,
                )
            conn.commit()

    # ─── Lookup helpers ───────────────────────────────────────────────────────

    def _get_asset_class_id(self) -> int:
        with get_conn() as conn:
            return conn.execute("SELECT id FROM asset_class WHERE code='FII'").fetchone()[0]

    def _get_security_type_id(self, code: str) -> int | None:
        with get_conn() as conn:
            row = conn.execute("SELECT id FROM security_type WHERE code=%s", (code,)).fetchone()
        return row[0] if row else None

    # ─── Batch upsert helpers ─────────────────────────────────────────────────

    def _upsert_issuers(self, conn, pairs: list[tuple[str | None, str]]) -> dict[str, int]:
        """Batch upsert (cnpj, name) pairs. Returns {cnpj: id}."""
        clean = [(c, n) for c, n in pairs if c and n]
        if not clean:
            return {}
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO issuer (cnpj, name, type) VALUES (%s, %s, 'emissor_direto') "
                "ON CONFLICT (cnpj) DO UPDATE SET name = EXCLUDED.name",
                clean,
            )
        cnpjs = [c for c, _ in clean]
        rows = conn.execute("SELECT cnpj, id FROM issuer WHERE cnpj = ANY(%s)", (cnpjs,)).fetchall()
        return {r[0]: r[1] for r in rows}

    def _upsert_participants(self, conn, pairs: list[tuple[str | None, str]]) -> dict[str, int]:
        """Batch upsert (cnpj, name) participants. Returns {cnpj: id}."""
        clean = [(c, n) for c, n in pairs if n]
        if not clean:
            return {}
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO participant (cnpj, name) VALUES (%s, %s) "
                "ON CONFLICT (cnpj) WHERE cnpj IS NOT NULL DO UPDATE SET name = EXCLUDED.name",
                clean,
            )
        cnpjs = [c for c, _ in clean if c]
        if not cnpjs:
            return {}
        rows = conn.execute("SELECT cnpj, id FROM participant WHERE cnpj = ANY(%s)", (cnpjs,)).fetchall()
        return {r[0]: r[1] for r in rows}

    def _get_or_create_vehicle(self, conn, issuer_id: int | None, name: str, ac_id: int) -> int:
        row = conn.execute(
            "SELECT id FROM vehicle WHERE issuer_id = %s AND asset_class_id = %s LIMIT 1",
            (issuer_id, ac_id),
        ).fetchone()
        if row:
            return row[0]
        row = conn.execute(
            "INSERT INTO vehicle (issuer_id, asset_class_id, name) VALUES (%s, %s, %s) RETURNING id",
            (issuer_id, ac_id, name),
        ).fetchone()
        return row[0]

    # ─── oferta_distribuicao ──────────────────────────────────────────────────

    def _upsert_distribuicao(self, df: pd.DataFrame) -> tuple[int, int, list]:
        if df.empty:
            return 0, 0, []

        ac_id = self._get_asset_class_id()
        st_follow = self._get_security_type_id("fii_follow_on")
        st_restricted = self._get_security_type_id("fii_restricted")

        # Collect unique issuers and leaders
        issuer_pairs  = list({
            (_clean_cnpj(r.get("CNPJ_Emissor")), _clean_str(r.get("Nome_Emissor")) or "")
            for _, r in df.iterrows()
        })
        leader_pairs = list({
            (_clean_cnpj(r.get("CNPJ_Lider")), _clean_str(r.get("Nome_Lider")) or "")
            for _, r in df.iterrows()
            if _clean_str(r.get("Nome_Lider"))
        })

        new_count = upd_count = 0
        alerts: list[dict] = []

        with get_conn() as conn:
            issuer_map  = self._upsert_issuers(conn, issuer_pairs)
            leader_map  = self._upsert_participants(conn, leader_pairs)

            for _, row in df.iterrows():
                cnpj_e = _clean_cnpj(row.get("CNPJ_Emissor"))
                name_e = _clean_str(row.get("Nome_Emissor")) or "Desconhecido"
                issuer_id = issuer_map.get(cnpj_e)

                vehicle_id = self._get_or_create_vehicle(conn, issuer_id, name_e, ac_id)

                rito = _clean_str(row.get("Rito_Oferta"))
                st_id = st_restricted if _is_restricted(rito) else st_follow

                cvm_reg = _clean_str(row.get("Numero_Registro_Oferta"))
                if not cvm_reg:
                    continue

                status = _derive_status(row)

                existing = conn.execute(
                    "SELECT id, status FROM offer WHERE cvm_registration = %s", (cvm_reg,)
                ).fetchone()

                offer_data = (
                    vehicle_id, st_id, cvm_reg,
                    _clean_str(row.get("Numero_Processo")),
                    status,
                    _to_date(row.get("Data_Inicio_Oferta")),
                    _to_date(row.get("Data_Encerramento_Oferta")),
                    _to_date(row.get("Data_Registro_Oferta")),
                    _to_numeric(row.get("Valor_Total")),
                    _to_numeric(row.get("Preco_Unitario")),
                    _to_numeric(row.get("Quantidade_Total")),
                    _clean_str(row.get("Modalidade_Oferta")),
                    Jsonb({
                        "tipo_oferta": _clean_str(row.get("Tipo_Oferta")),
                        "rito_oferta": rito,
                        "tipo_ativo":  _clean_str(row.get("Tipo_Ativo")),
                    }),
                )

                if not existing:
                    result = conn.execute(
                        """
                        INSERT INTO offer
                            (vehicle_id, security_type_id, cvm_registration,
                             cvm_process_number, status, started_at, ends_at, registered_at,
                             total_volume, unit_price, total_units, distribution_regime,
                             financial_terms_available, extra)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, TRUE, %s)
                        RETURNING id
                        """,
                        offer_data,
                    ).fetchone()
                    offer_id = result[0]
                    new_count += 1
                    alerts.append({"type": "new_offer", "offer_id": offer_id,
                                   "vehicle_id": vehicle_id,
                                   "detail": {"source": "oferta_distribuicao", "fund": name_e}})
                else:
                    conn.execute(
                        """
                        UPDATE offer SET
                            status = %s, ends_at = %s, total_volume = %s,
                            unit_price = %s, total_units = %s, updated_at = NOW()
                        WHERE cvm_registration = %s
                        """,
                        (status, _to_date(row.get("Data_Encerramento_Oferta")),
                         _to_numeric(row.get("Valor_Total")),
                         _to_numeric(row.get("Preco_Unitario")),
                         _to_numeric(row.get("Quantidade_Total")),
                         cvm_reg),
                    )
                    old_status = existing[1]
                    offer_id = existing[0]
                    upd_count += 1
                    if old_status != status and status != "unknown":
                        alerts.append({"type": "status_change", "offer_id": offer_id,
                                       "vehicle_id": vehicle_id,
                                       "detail": {"from": old_status, "to": status, "source": "oferta_distribuicao"}})

                # Participant role (coordinator leader)
                cnpj_l = _clean_cnpj(row.get("CNPJ_Lider"))
                p_id = leader_map.get(cnpj_l)
                if p_id:
                    conn.execute(
                        "INSERT INTO participant_role (offer_id, participant_id, role) "
                        "VALUES (%s, %s, 'coordinator_leader') ON CONFLICT DO NOTHING",
                        (offer_id, p_id),
                    )

            conn.commit()

        return new_count, upd_count, alerts

    # ─── oferta_resolucao_160 ─────────────────────────────────────────────────

    def _upsert_resolucao160(self, df: pd.DataFrame) -> tuple[int, int, list]:
        if df.empty:
            return 0, 0, []

        ac_id = self._get_asset_class_id()
        st_follow = self._get_security_type_id("fii_follow_on")
        st_restricted = self._get_security_type_id("fii_restricted")

        issuer_pairs = list({
            (_clean_cnpj(r.get("CNPJ_Emissor")), _clean_str(r.get("Nome_Emissor")) or "")
            for _, r in df.iterrows()
        })
        leader_pairs = list({
            (_clean_cnpj(r.get("CNPJ_Lider")), _clean_str(r.get("Nome_Lider")) or "")
            for _, r in df.iterrows()
            if _clean_str(r.get("Nome_Lider"))
        })

        new_count = upd_count = 0
        alerts: list[dict] = []

        with get_conn() as conn:
            issuer_map = self._upsert_issuers(conn, issuer_pairs)
            leader_map = self._upsert_participants(conn, leader_pairs)

            for _, row in df.iterrows():
                cnpj_e = _clean_cnpj(row.get("CNPJ_Emissor"))
                name_e = _clean_str(row.get("Nome_Emissor")) or "Desconhecido"
                issuer_id = issuer_map.get(cnpj_e)

                vehicle_id = self._get_or_create_vehicle(conn, issuer_id, name_e, ac_id)

                # Resolução 160 does not distinguish restricted by rito column —
                # it is a full-rite offering. Restricted offers use a separate process.
                st_id = st_follow

                cvm_reg = _clean_str(row.get("Numero_Requerimento"))
                if not cvm_reg:
                    continue

                raw_status = _clean_str(row.get("Status_Requerimento"))
                status = _derive_status_160(raw_status)

                bookbuilding_raw = _clean_str(row.get("Bookbuilding"))
                bookbuilding = (bookbuilding_raw == "S") if bookbuilding_raw else None

                audience_raw = _clean_str(row.get("Publico_alvo")) or ""
                if "profissional" in audience_raw.lower():
                    audience = "profissional"
                elif "qualificado" in audience_raw.lower():
                    audience = "qualificado"
                else:
                    audience = "geral"

                existing = conn.execute(
                    "SELECT id, status FROM offer WHERE cvm_registration = %s", (cvm_reg,)
                ).fetchone()

                offer_data = (
                    vehicle_id, st_id, cvm_reg,
                    _clean_str(row.get("Numero_Processo")),
                    status,
                    _to_date(row.get("Data_Registro")),
                    _to_date(row.get("Data_Encerramento")),
                    _to_date(row.get("Data_requerimento")),
                    _to_numeric(row.get("Valor_Total_Registrado")),
                    None,
                    _to_numeric(row.get("Qtde_Total_Registrada")),
                    _clean_str(row.get("Regime_distribuicao")),
                    bookbuilding,
                    audience,
                    Jsonb({
                        "tipo_requerimento": _clean_str(row.get("Tipo_requerimento")),
                        "valor_mobiliario":  _clean_str(row.get("Valor_Mobiliario")),
                        "raw_status":        raw_status,
                        "grupo_coordenador": _clean_str(row.get("Grupo_Coordenador")),
                    }),
                )

                if not existing:
                    result = conn.execute(
                        """
                        INSERT INTO offer
                            (vehicle_id, security_type_id, cvm_registration,
                             cvm_process_number, status, started_at, ends_at, registered_at,
                             total_volume, unit_price, total_units, distribution_regime,
                             bookbuilding, target_audience,
                             financial_terms_available, extra)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, TRUE, %s)
                        RETURNING id
                        """,
                        offer_data,
                    ).fetchone()
                    offer_id = result[0]
                    new_count += 1
                else:
                    conn.execute(
                        """
                        UPDATE offer SET
                            status = %s, ends_at = %s, total_volume = %s,
                            bookbuilding = %s, target_audience = %s,
                            updated_at = NOW()
                        WHERE cvm_registration = %s
                        """,
                        (
                            status,
                            _to_date(row.get("Data_Encerramento")),
                            _to_numeric(row.get("Valor_Total_Registrado")),
                            bookbuilding, audience, cvm_reg,
                        ),
                    )
                    old_status = existing[1]
                    offer_id = existing[0]
                    upd_count += 1
                    if old_status != status and status != "unknown":
                        alerts.append({"type": "status_change", "offer_id": offer_id,
                                       "vehicle_id": vehicle_id,
                                       "detail": {"from": old_status, "to": status, "source": "oferta_resolucao_160"}})

                cnpj_l = _clean_cnpj(row.get("CNPJ_Lider"))
                p_id = leader_map.get(cnpj_l)
                if p_id:
                    conn.execute(
                        "INSERT INTO participant_role (offer_id, participant_id, role) "
                        "VALUES (%s, %s, 'coordinator_leader') ON CONFLICT DO NOTHING",
                        (offer_id, p_id),
                    )

            conn.commit()

        return new_count, upd_count, alerts
