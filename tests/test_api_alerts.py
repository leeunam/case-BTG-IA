"""Tests for /api/alerts/* endpoints."""
from tests.conftest import FakeCursor, db_mock


class TestAlertSummary:
    def test_returns_counts(self, client):
        with db_mock({"count": FakeCursor([(47, 39, 8)])}):
            r = client.get("/api/alerts/summary?period=1m")
        assert r.status_code == 200
        d = r.json()
        assert "total" in d
        assert "seen" in d
        assert "unseen" in d

    def test_rejects_invalid_period(self, client):
        r = client.get("/api/alerts/summary?period=99y")
        assert r.status_code == 400


class TestListAlerts:
    def test_returns_paginated(self, client):
        with db_mock({
            "count": FakeCursor([(5,)]),
            "select": FakeCursor([(
                1, "new_offer", 10, "FUNDO A", "FDA11", "ipo",
                False, "2026-05-22T10:00:00", {"total_volume": 100_000_000},
            )]),
        }):
            r = client.get("/api/alerts?period=1m")
        assert r.status_code == 200
        d = r.json()
        assert "items" in d
        assert "total_count" in d

    def test_rejects_invalid_period(self, client):
        r = client.get("/api/alerts?period=xyz")
        assert r.status_code == 400

    def test_empty_alerts(self, client):
        with db_mock({
            "select count(*)": FakeCursor([(0,)]),
            "from alert_log": FakeCursor([]),
        }):
            r = client.get("/api/alerts?period=1m")
        assert r.status_code == 200
        assert r.json()["items"] == []
        assert r.json()["total_count"] == 0


class TestMarkSeen:
    def test_marks_alert_seen(self, client):
        with db_mock({"update": FakeCursor([(1,)])}):
            r = client.patch("/api/alerts/1/seen", json={"seen": True})
        assert r.status_code == 200
        assert r.json()["seen"] is True

    def test_returns_404_for_unknown_alert(self, client):
        with db_mock({"update": FakeCursor([])}):
            r = client.patch("/api/alerts/9999/seen", json={"seen": True})
        assert r.status_code == 404

    def test_requires_seen_field(self, client):
        r = client.patch("/api/alerts/1/seen", json={})
        assert r.status_code == 422
