"""Security-focused tests."""
from tests.conftest import FakeCursor, db_mock


class TestPathTraversal:
    def test_absolute_etc_passwd_blocked(self, client):
        with db_mock({"select": FakeCursor([("completed", "/etc/passwd")])}):
            r = client.get("/api/reports/jobs/x/download")
        assert r.status_code == 400

    def test_dotdot_env_blocked(self, client):
        with db_mock({"select": FakeCursor([("completed", "data/reports/../../../.env")])}):
            r = client.get("/api/reports/jobs/x/download")
        assert r.status_code == 400

    def test_absolute_var_blocked(self, client):
        with db_mock({"select": FakeCursor([("completed", "/var/secret.pdf")])}):
            r = client.get("/api/reports/jobs/x/download")
        assert r.status_code == 400


class TestInputValidation:
    def test_invalid_period_volume(self, client):
        assert client.get("/api/dashboard/volume?period=2y").status_code == 400

    def test_invalid_period_offers(self, client):
        assert client.get("/api/offers?period=invalid").status_code == 400

    def test_invalid_period_alerts(self, client):
        assert client.get("/api/alerts?period=xyz").status_code == 400

    def test_invalid_period_players(self, client):
        assert client.get("/api/general-scenario/players?period=bad").status_code == 400

    def test_page_below_1_rejected(self, client):
        assert client.get("/api/offers?page=0").status_code == 422

    def test_page_size_above_200_rejected(self, client):
        assert client.get("/api/offers?page_size=201").status_code == 422

    def test_compare_single_id_rejected(self, client):
        assert client.get("/api/offers/compare?offer_ids=1").status_code == 400

    def test_compare_three_ids_rejected(self, client):
        assert client.get("/api/offers/compare?offer_ids=1,2,3").status_code == 400


class TestErrorMessagesSanitized:
    def test_404_body_has_no_db_string(self, client):
        with db_mock({"from offer": FakeCursor([])}):
            r = client.get("/api/offers/9999/indicators")
        assert r.status_code == 404
        body = r.text
        assert "postgresql://" not in body
        assert "gsk_" not in body
        assert "sk-proj-" not in body

    def test_400_period_error_has_no_secrets(self, client):
        r = client.get("/api/dashboard/volume?period=badvalue")
        assert r.status_code == 400
        body = r.text
        assert "postgresql://" not in body
        assert "password" not in body.lower()
        assert "gsk_" not in body


class TestParsePeriodUnit:
    def test_valid_periods(self):
        from src.api.deps import parse_period
        from datetime import date
        for p in ("1d", "7d", "15d", "1m"):
            start, end = parse_period(p)
            assert isinstance(start, date)
            assert start < end

    def test_invalid_period_raises_http_400(self):
        import pytest
        from fastapi import HTTPException
        from src.api.deps import parse_period
        with pytest.raises(HTTPException) as exc_info:
            parse_period("5y")
        assert exc_info.value.status_code == 400


class TestProductionDocs:
    def test_docs_available_in_dev(self, client):
        import os
        os.environ.setdefault("ENV", "development")
        r = client.get("/docs")
        assert r.status_code == 200
