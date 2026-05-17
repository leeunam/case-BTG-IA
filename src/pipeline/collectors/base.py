from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

import pandas as pd

from src.db.connection import get_conn

RAW_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"


class BaseCollector(ABC):
    source_code: str
    source_name: str

    def collect(self) -> dict:
        run_id = self._start_run()
        try:
            result = self._run()
            self._finish_run(run_id, "success", result)
            return result
        except Exception as exc:
            self._finish_run(run_id, "failed", error=str(exc))
            raise

    @abstractmethod
    def _run(self) -> dict:
        ...

    def _save_raw(self, df: pd.DataFrame) -> Path:
        today = date.today().isoformat()
        dest = RAW_DATA_DIR / today
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"{self.source_code}.parquet"
        df.to_parquet(path, index=False, engine="pyarrow")
        print(f"  Raw saved: {path}")
        return path

    def _get_source_id(self) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM source WHERE code = %s", (self.source_code,)
            ).fetchone()
        if not row:
            raise RuntimeError(f"Source '{self.source_code}' not found in DB. Run migrate.py first.")
        return row[0]

    def _start_run(self) -> int:
        source_id = self._get_source_id()
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO extraction_run (source_id, started_at, status) VALUES (%s, NOW(), 'running') RETURNING id",
                (source_id,),
            ).fetchone()
            conn.commit()
        return row[0]

    def _finish_run(
        self,
        run_id: int,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        result = result or {}
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE extraction_run
                SET finished_at = NOW(), status = %s,
                    records_collected = %s, records_new = %s,
                    records_updated = %s, error_log = %s
                WHERE id = %s
                """,
                (
                    status,
                    result.get("collected", 0),
                    result.get("new", 0),
                    result.get("updated", 0),
                    error,
                    run_id,
                ),
            )
            conn.commit()
