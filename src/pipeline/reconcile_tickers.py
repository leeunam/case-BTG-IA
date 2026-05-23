"""
Reconcile CVM vehicle records (no ticker) with Fundamentus vehicles (ticker only).

Strategy:
1. Fetch Fundamentus HTML → extract {ticker: full_legal_name} from tooltips
2. Normalize both CVM vehicle names and Fundamentus full names
3. Match by normalized name (exact, then prefix)
4. Update CVM vehicle: set ticker
5. Re-link daily_snapshot rows to the CVM vehicle
6. Report match rate
"""
import re
import unicodedata

import httpx
from bs4 import BeautifulSoup

from src.db.connection import get_conn

_URL = "https://www.fundamentus.com.br/fii_resultado.php"

# Words to strip before comparing
_STRIP_RE = re.compile(r"""(?ix)
    \b(
      responsabilidade | limitada | ltda\.? | s\.a\.? |
      fundo\s+de\s+investimento\s+imobili[aá]rio |
      fundo\s+imobili[aá]rio |
      fundo\s+de\s+investimento |
      investimento\s+imobili[aá]rio |
      imobili[aá]rio | imobili[aá]rios |
      fundo | fundos | fiagro |
      responsabilidade | limitada |
      de | do | da | dos | das | e | em | com | na | nas | no | nos
    )\b
    | [^a-z0-9\s]
""")
_MULTI_SPACE = re.compile(r"\s{2,}")


def _normalize(name: str) -> str:
    """Lowercase, remove accents, strip FII boilerplate, collapse spaces."""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    n = _STRIP_RE.sub(" ", n)
    return _MULTI_SPACE.sub(" ", n).strip()


def fetch_ticker_to_name() -> dict[str, str]:
    """Returns {ticker: full_legal_name} from Fundamentus HTML tooltips."""
    r = httpx.get(_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20, follow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "lxml", from_encoding="iso-8859-1")
    result: dict[str, str] = {}
    for span in soup.find_all("span", class_="tips"):
        a = span.find("a")
        title = span.get("title", "").strip()
        if a and title:
            result[a.text.strip()] = title
    return result


def reconcile(dry_run: bool = False) -> dict:
    print("  Fetching Fundamentus ticker→name map...")
    ticker_names = fetch_ticker_to_name()
    print(f"  Got {len(ticker_names)} tickers with full names")

    # Build: normalized_name → ticker
    norm_to_ticker: dict[str, str] = {}
    for ticker, full_name in ticker_names.items():
        norm = _normalize(full_name)
        if len(norm) >= 4:
            norm_to_ticker[norm] = ticker

    # Get CVM vehicles without tickers
    with get_conn() as conn:
        cvm_rows = conn.execute("""
            SELECT v.id, v.name
            FROM vehicle v
            WHERE v.ticker IS NULL
              AND v.asset_class_id = (SELECT id FROM asset_class WHERE code = 'FII')
        """).fetchall()

        # Get Fundamentus vehicles (ticker = name, no issuer)
        fund_rows = conn.execute("""
            SELECT v.id, v.ticker
            FROM vehicle v
            WHERE v.ticker IS NOT NULL
              AND v.issuer_id IS NULL
              AND v.asset_class_id = (SELECT id FROM asset_class WHERE code = 'FII')
        """).fetchall()

    fundamentus_ticker_to_id = {r[1]: r[0] for r in fund_rows}

    print(f"  CVM vehicles without ticker: {len(cvm_rows)}")
    print(f"  Fundamentus-only vehicles:   {len(fund_rows)}")

    matched: list[tuple[int, str, int | None]] = []  # (cvm_id, ticker, fundamentus_vehicle_id)
    no_match: list[str] = []

    for cvm_id, cvm_name in cvm_rows:
        norm_cvm = _normalize(cvm_name)
        if len(norm_cvm) < 4:
            continue

        ticker = None

        # 1. Exact match
        ticker = norm_to_ticker.get(norm_cvm)

        # 2. Prefix match: CVM name starts with Fundamentus normalized name
        if not ticker:
            for norm_fund, t in norm_to_ticker.items():
                if len(norm_fund) >= 5 and (
                    norm_cvm.startswith(norm_fund) or norm_fund.startswith(norm_cvm)
                ):
                    ticker = t
                    break

        # 3. Token intersection: require ≥ 3 matching tokens of length ≥ 4
        if not ticker:
            tokens_cvm = set(w for w in norm_cvm.split() if len(w) >= 4)
            if len(tokens_cvm) >= 2:
                for norm_fund, t in norm_to_ticker.items():
                    tokens_fund = set(w for w in norm_fund.split() if len(w) >= 4)
                    common = tokens_cvm & tokens_fund
                    if len(common) >= 2 and len(common) >= min(len(tokens_cvm), len(tokens_fund)) * 0.6:
                        ticker = t
                        break

        if ticker:
            fund_vid = fundamentus_ticker_to_id.get(ticker)
            matched.append((cvm_id, ticker, fund_vid))
        else:
            no_match.append(cvm_name)

    print(f"  Matched: {len(matched)}  |  Unmatched: {len(no_match)}")

    if dry_run:
        print("  [dry_run] No changes written.")
        for cvm_id, ticker, _ in matched[:10]:
            print(f"    vehicle {cvm_id} → {ticker}")
        return {"matched": len(matched), "unmatched": len(no_match)}

    # Apply updates — single transaction per vehicle to avoid constraint violations.
    # For each pair: clear ticker from any current holder → re-link snapshots → assign ticker.
    with get_conn() as conn:
        snapshot_relinked = 0

        for cvm_id, ticker, fund_vid in matched:
            # 1. Clear ticker from any vehicle currently holding it (Fundamentus-only)
            conn.execute(
                "UPDATE vehicle SET ticker = NULL WHERE ticker = %s AND id != %s",
                (ticker, cvm_id),
            )

            # 2. Re-link daily_snapshot: if we know the old holder, re-link explicitly
            if fund_vid and fund_vid != cvm_id:
                rows = conn.execute(
                    "UPDATE daily_snapshot SET vehicle_id = %s WHERE vehicle_id = %s",
                    (cvm_id, fund_vid),
                ).rowcount
                snapshot_relinked += rows

            # 3. Assign ticker to CVM vehicle
            conn.execute(
                "UPDATE vehicle SET ticker = %s WHERE id = %s",
                (ticker, cvm_id),
            )

        conn.commit()

    print(f"  Tickers written: {len(matched)}")
    print(f"  Snapshots re-linked: {snapshot_relinked}")
    return {
        "matched": len(matched),
        "unmatched": len(no_match),
        "snapshots_relinked": snapshot_relinked,
    }


if __name__ == "__main__":
    import sys
    dry = "--dry" in sys.argv
    reconcile(dry_run=dry)
