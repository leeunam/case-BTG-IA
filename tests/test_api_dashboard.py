"""Tests for /api/dashboard/* endpoints."""
from datetime import date
from tests.conftest import FakeCursor, db_mock


class TestDailyInsight:
    def test_not_generated_when_no_row(self, client):
        with db_mock({"daily_insight": FakeCursor([])}):
            r = client.get("/api/dashboard/daily-insight")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "not_generated"
        assert d["text"] is None

    def test_returns_generated_insight(self, client):
        today = date.today().isoformat()
        with db_mock({"daily_insight": FakeCursor(
            [(today, "2026-01-01T07:00:00", "generated", "Panorama do dia.")],
            ["insight_date", "generated_at", "status", "text"],
        )}):
            r = client.get("/api/dashboard/daily-insight")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "generated"
        assert d["text"] == "Panorama do dia."


class TestVolume:
    def test_returns_volume_structure(self, client):
        with db_mock({"select": FakeCursor(
            [(1_000_000_000.0, 10, 200_000_000.0, 800_000_000.0)]
        )}):
            r = client.get("/api/dashboard/volume?period=1m")
        assert r.status_code == 200
        d = r.json()
        assert "total_volume" in d
        assert "offer_count" in d
        assert "ipo_volume" in d
        assert "follow_on_volume" in d

    def test_rejects_invalid_period(self, client):
        r = client.get("/api/dashboard/volume?period=2y")
        assert r.status_code == 400


class TestRanking:
    def test_returns_list(self, client):
        with db_mock({"select": FakeCursor(
            [(1, "FUNDO XPTO", "XPTO11", "follow_on", 500_000_000.0, "BTG Pactual")]
        )}):
            r = client.get("/api/dashboard/ranking?period=1m")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_empty_returns_empty_list(self, client):
        with db_mock({"select": FakeCursor([])}):
            r = client.get("/api/dashboard/ranking?period=1m")
        assert r.status_code == 200
        assert r.json() == []


class TestIpoVsFollowOn:
    def test_returns_comparison(self, client):
        with db_mock({"select": FakeCursor(
            [(100_000_000.0, 2, 400_000_000.0, 5)]
        )}):
            r = client.get("/api/dashboard/ipo-vs-followon?period=1m")
        assert r.status_code == 200
        d = r.json()
        assert "ipo_volume" in d and "follow_on_volume" in d


class TestTopNewOffers:
    def test_returns_offers(self, client):
        today = date.today().isoformat()
        with db_mock({"select": FakeCursor(
            [(1, "FUNDO A", "FDA11", "ipo", 100_000_000.0, "BTG", today, "esforcos_restritos")]
        )}):
            r = client.get("/api/dashboard/top-new-offers")
        assert r.status_code == 200
        offers = r.json()
        assert isinstance(offers, list)
        if offers:
            assert "name" in offers[0]
            assert "offer_type" in offers[0]

    def test_returns_empty_when_no_new_offers(self, client):
        with db_mock({"select": FakeCursor([])}):
            r = client.get("/api/dashboard/top-new-offers")
        assert r.status_code == 200
        assert r.json() == []


class TestPipelineHealth:
    def test_returns_health_structure(self, client):
        with db_mock({"select": FakeCursor(
            [("cvm_dados_abertos", "CVM Dados Abertos", None, "success")]
        )}):
            r = client.get("/api/dashboard/pipeline-health")
        assert r.status_code == 200
        d = r.json()
        assert "sources" in d
        assert "failed_today" in d
        assert "stale_sources" in d
