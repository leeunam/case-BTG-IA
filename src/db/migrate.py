#!/usr/bin/env python3
"""Apply SQL migrations in order. Safe to run multiple times (idempotent DDL)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.db.connection import get_conn


def run() -> None:
    migrations_dir = Path(__file__).parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    if not sql_files:
        print("No migrations found.")
        return

    with get_conn() as conn:
        for sql_file in sql_files:
            print(f"  Applying {sql_file.name}...", end=" ", flush=True)
            conn.execute(sql_file.read_text(encoding="utf-8"))
            conn.commit()
            print("OK")

    print(f"\n{len(sql_files)} migration(s) applied.")


if __name__ == "__main__":
    run()
