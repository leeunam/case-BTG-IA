"""
Shared fixtures for all tests.

FastAPI uses Depends(get_db) for DB injection. We override the dependency
via app.dependency_overrides — the canonical FastAPI pattern for test mocking.
"""
from contextlib import contextmanager
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient


# ── Fake DB layer ─────────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, rows: list = (), cols: list[str] | None = None):
        self._rows = list(rows)
        self._cols = cols or []
        self.description = [type("Col", (), {"name": c})() for c in self._cols]

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConn:
    """Minimal psycopg3-like connection mock with keyword-matching dispatch."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self._responses = responses or {}

    def execute(self, sql: str, params=None) -> FakeCursor:
        sql_lower = sql.lower().strip()
        # Sort by key length descending so more specific keys match before generic ones
        # e.g. "short_name" (10) matches before "select" (6)
        for key, value in sorted(self._responses.items(), key=lambda x: -len(x[0])):
            if key.lower() in sql_lower:
                if isinstance(value, FakeCursor):
                    return value
                if isinstance(value, (list, tuple)) and value:
                    if isinstance(value[0], tuple):
                        return FakeCursor(value)
                    return FakeCursor([value])
                return FakeCursor()
        return FakeCursor()

    def commit(self):
        pass

    def cursor(self):
        from unittest.mock import MagicMock
        cur = MagicMock()
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        cur.executemany = MagicMock()
        return cur

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ── Dependency override helpers ───────────────────────────────────────────────

@contextmanager
def db_mock(responses: dict | None = None):
    """
    Override the FastAPI get_db dependency with a FakeConn.
    Must be used inside a test that has access to the `client` fixture,
    OR used directly via app.dependency_overrides.
    """
    from src.api.main import app
    from src.api.deps import get_db

    fake = FakeConn(responses or {})

    def override() -> Generator:
        yield fake

    app.dependency_overrides[get_db] = override
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from src.api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
