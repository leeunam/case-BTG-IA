"""Tests for frontend formatter utilities (Python-equivalent logic)."""


class TestAsciiSafe:
    """The _ascii_safe function in reports router must sanitize Unicode."""

    def test_em_dash_replaced(self):
        from src.api.routers.reports import _ascii_safe
        assert _ascii_safe("FUNDO—NOME") == "FUNDO-NOME"

    def test_curly_quotes_replaced(self):
        from src.api.routers.reports import _ascii_safe
        assert _ascii_safe("“Texto”") == '"Texto"'

    def test_accented_chars_normalized(self):
        from src.api.routers.reports import _ascii_safe
        result = _ascii_safe("ção")
        # Should not raise UnicodeEncodeError when encoded to latin-1
        result.encode("latin-1")  # no exception expected

    def test_plain_ascii_unchanged(self):
        from src.api.routers.reports import _ascii_safe
        text = "Hello World 1234"
        assert _ascii_safe(text) == text


class TestRollingStart:
    """BCB rolling_start must produce a date 365 days back."""

    def test_returns_string_date(self):
        from src.pipeline.collectors.bcb import _rolling_start
        from datetime import datetime, timedelta
        result = _rolling_start()
        dt = datetime.strptime(result, "%Y-%m-%d")
        from datetime import date
        diff = (date.today() - dt.date()).days
        # Should be approximately 365 days (allow ±1 for timezone edge cases)
        assert 364 <= diff <= 366

    def test_cutoff_date_is_30_days_back(self):
        from src.pipeline.collectors.cvm import _cutoff_date
        from datetime import date, timedelta
        result = _cutoff_date()
        expected = date.today() - timedelta(days=30)
        assert result == expected
