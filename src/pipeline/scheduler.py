"""
Daily pipeline scheduler. Runs the full pipeline every day at 06:30.

Usage:
    python -m src.pipeline.scheduler
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.pipeline.run import run_pipeline


def start() -> None:
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")

    @scheduler.scheduled_job(CronTrigger(hour=6, minute=30), id="daily_pipeline")
    def daily_job() -> None:
        run_pipeline()

    print("Scheduler started. Daily pipeline runs at 06:30 (America/Sao_Paulo).")
    print("Press Ctrl+C to stop.\n")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")


if __name__ == "__main__":
    start()
