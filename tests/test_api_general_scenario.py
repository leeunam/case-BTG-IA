"""Tests for /api/general-scenario/* endpoints."""
from tests.conftest import FakeCursor, db_mock


class TestMacroKpis:
    def test_returns_list(self, client):
        with db_mock({"market_metric": FakeCursor([(13.75, "2026-05-22")])}):
            r = client.get("/api/general-scenario/macro-kpis")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_unavailable_code_shows_nd(self, client):
        with db_mock({"market_metric": FakeCursor([])}):
            r = client.get("/api/general-scenario/macro-kpis")
        assert r.status_code == 200
        kpis = r.json()
        for kpi in kpis:
            if kpi["value"] is None:
                assert kpi["display_value"] == "N/D"


class TestIpcaMonthly:
    def test_returns_time_series(self, client):
        with db_mock({"market_metric": FakeCursor([
            ("2026-05", 0.43),
            ("2026-04", 0.38),
        ])}):
            r = client.get("/api/general-scenario/ipca-monthly")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestPlayers:
    def test_returns_players(self, client):
        with db_mock({"select": FakeCursor([
            ("BTG Pactual", 10, 5_000_000_000.0, 8, "2026-05-01"),
        ])}):
            r = client.get("/api/general-scenario/players?period=1m")
        assert r.status_code == 200
        players = r.json()
        assert isinstance(players, list)
        if players:
            assert "share_vol_pct" in players[0]
            assert "share_qty_pct" in players[0]

    def test_shares_sum_to_100(self, client):
        with db_mock({"select": FakeCursor([
            ("BTG", 6, 3_000_000_000.0, 5, "2026-05-01"),
            ("XP",  4, 2_000_000_000.0, 3, "2026-04-20"),
        ])}):
            r = client.get("/api/general-scenario/players?period=1m")
        assert r.status_code == 200
        players = r.json()
        if len(players) >= 2:
            total_vol = sum(p["share_vol_pct"] for p in players)
            assert abs(total_vol - 100.0) < 0.1

    def test_rejects_invalid_period(self, client):
        r = client.get("/api/general-scenario/players?period=bad")
        assert r.status_code == 400


class TestTopFundsVolume:
    def test_returns_funds(self, client):
        with db_mock({"select": FakeCursor([("HGLG11 FUNDO", "HGLG11", 500_000_000.0)])}):
            r = client.get("/api/general-scenario/top-funds-volume?period=1m")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestOffersByCoordinator:
    def test_returns_list(self, client):
        with db_mock({"select": FakeCursor([("BTG Pactual", 5, 1_000_000_000.0)])}):
            r = client.get("/api/general-scenario/offers-by-coordinator?period=1m")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
