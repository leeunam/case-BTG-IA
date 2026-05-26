"""
Pipeline scheduler — BTG FII Analyzer.

Schedule (America/Sao_Paulo):
  06:30 — Fontes regulatórias: CVM, BCB, B3 Listings, Status Invest
           Dados batch diários — rodar mais vezes não traz informação nova.
  10:30 — Mercado (30 min pós-abertura B3): IFIX + Fundamentus + FundsExplorer
  14:00 — Mercado (meio do pregão): IFIX + Fundamentus + FundsExplorer
  17:00 — Mercado (fechamento B3): IFIX + Fundamentus + FundsExplorer

Separação por cadência de atualização:
  Regulatório  → CVM publica lotes diários; BCB e B3 idem. Sem dados intraday.
  Mercado      → Preços, IFIX e volume atualizam durante o pregão (10:00–17:30 BRT).

Usage:
    python -m src.pipeline.scheduler
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.pipeline.run import run_pipeline

_REGULATORY_SOURCES = [
    "cvm_dados_abertos",  # CVMCollector + CVMDocsCollector (mesmo source_code)
    "b3_listings",        # B3Collector
    "bcb_sgs",            # BCBCollector (Selic, CDI, IPCA, Focus)
    "status_invest",      # StatusInvestCollector (histórico de dividendos)
]

_MARKET_SOURCES = [
    "b3_ifix",       # IFIXCollector — índice B3 via Yahoo Finance
    "fundamentus",   # FundamentusCollector — preço, DY, P/VP, vacância
    "funds_explorer", # FundsExplorerCollector — volume diário, NAV
]


def start() -> None:
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")

    @scheduler.scheduled_job(CronTrigger(hour=6, minute=30), id="regulatory_pipeline")
    def regulatory_job() -> None:
        """Fontes regulatórias e batch diárias."""
        run_pipeline(sources=_REGULATORY_SOURCES)

    @scheduler.scheduled_job(CronTrigger(hour=10, minute=30), id="market_open")
    def market_open_job() -> None:
        """30 min pós-abertura: captura preços e IFIX de abertura."""
        run_pipeline(sources=_MARKET_SOURCES)

    @scheduler.scheduled_job(CronTrigger(hour=14, minute=0), id="market_midday")
    def market_midday_job() -> None:
        """Meio do pregão: snapshot intermediário de preços e volume."""
        run_pipeline(sources=_MARKET_SOURCES)

    @scheduler.scheduled_job(CronTrigger(hour=17, minute=0), id="market_close")
    def market_close_job() -> None:
        """Fechamento B3: captura preços finais e IFIX de encerramento."""
        run_pipeline(sources=_MARKET_SOURCES)

    print("Scheduler iniciado. Agenda (America/Sao_Paulo):")
    print("  06:30 — Regulatório: CVM + BCB + B3 + Status Invest")
    print("  10:30 — Mercado: IFIX + Fundamentus + FundsExplorer (abertura)")
    print("  14:00 — Mercado: IFIX + Fundamentus + FundsExplorer (meio do pregão)")
    print("  17:00 — Mercado: IFIX + Fundamentus + FundsExplorer (fechamento)")
    print("\nPressione Ctrl+C para parar.\n")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler parado.")


if __name__ == "__main__":
    start()
