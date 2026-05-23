"""
Pipeline orchestrator. Run manually or via scheduler.

Usage:
    python -m src.pipeline.run                          # all collectors
    python -m src.pipeline.run cvm_dados_abertos bcb_sgs  # specific source codes only
"""
import sys
import time
from datetime import datetime

from src.pipeline.collectors.b3 import B3Collector
from src.pipeline.collectors.b3_ifix import IFIXCollector
from src.pipeline.collectors.bcb import BCBCollector
from src.pipeline.collectors.cvm import CVMCollector
from src.pipeline.collectors.cvm_docs import CVMDocsCollector
from src.pipeline.collectors.fundamentus import FundamentusCollector
from src.pipeline.collectors.status_invest import StatusInvestCollector
from src.pipeline.collectors.funds_explorer import FundsExplorerCollector

_ALL_COLLECTORS = [
    CVMCollector,           # canonical: primary offers (CVM Dados Abertos)
    CVMDocsCollector,       # canonical: FII monthly informes (CVM Dados Abertos)
    B3Collector,            # canonical: FII listings (B3)
    IFIXCollector,          # market index IFIX (B3 via Yahoo Finance)
    FundamentusCollector,   # secondary: DY, P/VP, vacância — daily snapshot
    StatusInvestCollector,  # secondary: full dividend payment history per ticker
    FundsExplorerCollector, # secondary: volume diário, NAV por cota, retorno mensal
    BCBCollector,           # macro: Selic, CDI, IPCA, Focus (BCB/IBGE/B3)
]


def run_pipeline(sources: list[str] | None = None) -> dict:
    start = datetime.now()
    print(f"\n{'═'*60}")
    print(f"  Pipeline start: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")

    results = {}
    for cls in _ALL_COLLECTORS:
        collector = cls()
        if sources and collector.source_code not in sources:
            continue

        print(f"\n[{collector.source_name}]")
        t0 = time.monotonic()
        try:
            result = collector.collect()
            elapsed = time.monotonic() - t0
            print(
                f"  ✓ {result.get('new', 0)} new  "
                f"{result.get('updated', 0)} updated  "
                f"({elapsed:.1f}s)"
            )
            results[collector.source_code] = result
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  ✗ FAILED ({elapsed:.1f}s): {exc}")
            results[collector.source_code] = {"error": str(exc)}

    elapsed_total = (datetime.now() - start).total_seconds()
    print(f"\n{'═'*60}")
    print(f"  Pipeline done in {elapsed_total:.1f}s")
    print(f"{'═'*60}\n")
    return results


if __name__ == "__main__":
    args = sys.argv[1:] or None
    run_pipeline(sources=args)
