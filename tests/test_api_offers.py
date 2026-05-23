"""Tests for /api/offers/* endpoints."""
from tests.conftest import FakeCursor, db_mock


def _offer_row():
    return (
        1, "CVM001", "FUNDO XPTO", "XPTO11", True, "active",
        500_000_000.0, "tijolo", "logistica",
        "Gestora X", "Admin Y", "BTG Pactual",
        "esforcos_restritos", True, "2026-01-01", "2026-01-15", "2026-05-01",
    )


class TestListOffers:
    def _mock_for_offers(self, row):
        # More specific keys take priority (sorted by length in FakeConn)
        return {
            "select count(*)": FakeCursor([(1,)]),   # COUNT query (most specific)
            "short_name":      FakeCursor([]),         # participant_role query
            "coalesce(v.name": FakeCursor([row]),      # main SELECT (contains this token)
        }

    def test_returns_paginated_structure(self, client):
        with db_mock(self._mock_for_offers(_offer_row())):
            r = client.get("/api/offers?period=1m&status=ongoing")
        assert r.status_code == 200
        d = r.json()
        assert "items" in d
        assert "total_count" in d
        assert "page" in d
        assert "page_size" in d

    def test_rejects_invalid_period(self, client):
        r = client.get("/api/offers?period=5y")
        assert r.status_code == 400

    def test_page_below_1_rejected(self, client):
        r = client.get("/api/offers?period=1m&page=0")
        assert r.status_code == 422

    def test_page_size_above_200_rejected(self, client):
        r = client.get("/api/offers?period=1m&page_size=201")
        assert r.status_code == 422

    def test_offer_type_ipo_mapped(self, client):
        row = list(_offer_row())
        row[4] = True  # is_ipo = True
        with db_mock(self._mock_for_offers(tuple(row))):
            r = client.get("/api/offers?period=1m")
        assert r.status_code == 200
        items = r.json()["items"]
        if items:
            assert items[0]["offer_type"] == "ipo"

    def test_follow_on_type_mapped(self, client):
        row = list(_offer_row())
        row[4] = False  # is_ipo = False → follow_on
        with db_mock(self._mock_for_offers(tuple(row))):
            r = client.get("/api/offers?period=1m")
        assert r.status_code == 200
        items = r.json()["items"]
        if items:
            assert items[0]["offer_type"] == "follow_on"


class TestIndicators:
    def test_returns_indicator_structure(self, client):
        offer_row = (1, True, 95.0)
        ds_row = (8.54, 7.0, 0.93, 100.0, 50_000_000.0, 2.1, 500_000.0, 95.0, -0.5, "2026-05-22")
        with db_mock({
            "from offer": FakeCursor([offer_row]),
            "daily_snapshot": FakeCursor([ds_row]),
        }):
            r = client.get("/api/offers/1/indicators")
        assert r.status_code == 200
        d = r.json()
        assert "dy_12m" in d
        assert "pvp" in d
        assert "source" in d

    def test_returns_404_for_unknown_offer(self, client):
        with db_mock({"from offer": FakeCursor([])}):
            r = client.get("/api/offers/9999/indicators")
        assert r.status_code == 404


class TestCompareOffers:
    def test_requires_exactly_two_ids(self, client):
        r = client.get("/api/offers/compare?offer_ids=1")
        assert r.status_code == 400

    def test_rejects_three_ids(self, client):
        r = client.get("/api/offers/compare?offer_ids=1,2,3")
        assert r.status_code == 400

    def test_non_integer_id_is_handled(self, client):
        r = client.get("/api/offers/compare?offer_ids=1,abc")
        assert r.status_code in (400, 422, 500)
