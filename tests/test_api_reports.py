"""Tests for /api/reports/* endpoints."""
import uuid
from tests.conftest import FakeCursor, db_mock


class TestCreateReport:
    def test_returns_202_with_job_id(self, client):
        with db_mock({
            "from offer": FakeCursor([(1,)]),
            "insert": FakeCursor([]),
        }):
            r = client.post("/api/reports/offers/1")
        assert r.status_code == 202
        d = r.json()
        assert "job_id" in d
        assert d["status"] == "queued"

    def test_returns_404_for_unknown_offer(self, client):
        with db_mock({"from offer": FakeCursor([])}):
            r = client.post("/api/reports/offers/9999")
        assert r.status_code == 404


class TestGetJobStatus:
    def test_queued_job(self, client):
        job_id = str(uuid.uuid4())
        with db_mock({"select": FakeCursor(
            [(job_id, 1, "queued", 0, None, None, "2026-05-22T10:00:00")]
        )}):
            r = client.get(f"/api/reports/jobs/{job_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "queued"
        assert d["download_url"] is None

    def test_completed_job_has_download_url(self, client):
        job_id = str(uuid.uuid4())
        with db_mock({"select": FakeCursor(
            [(job_id, 1, "completed", 100, "data/reports/file.pdf", None, "2026-05-22T10:00:00")]
        )}):
            r = client.get(f"/api/reports/jobs/{job_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "completed"
        assert d["download_url"] is not None

    def test_unknown_job_returns_404(self, client):
        with db_mock({"select": FakeCursor([])}):
            r = client.get("/api/reports/jobs/nonexistent")
        assert r.status_code == 404


class TestDownloadReport:
    def test_not_completed_returns_400(self, client):
        with db_mock({"select": FakeCursor([("processing", "data/reports/file.pdf")])}):
            r = client.get("/api/reports/jobs/some-job/download")
        assert r.status_code == 400

    def test_path_traversal_etc_passwd_blocked(self, client):
        with db_mock({"select": FakeCursor([("completed", "/etc/passwd")])}):
            r = client.get("/api/reports/jobs/some-job/download")
        assert r.status_code == 400, "Path traversal to /etc/passwd must be blocked"

    def test_path_traversal_dotdot_env_blocked(self, client):
        with db_mock({"select": FakeCursor([("completed", "data/reports/../../../.env")])}):
            r = client.get("/api/reports/jobs/some-job/download")
        assert r.status_code == 400, "Dotdot traversal to .env must be blocked"

    def test_path_traversal_absolute_var_blocked(self, client):
        with db_mock({"select": FakeCursor([("completed", "/var/secret.pdf")])}):
            r = client.get("/api/reports/jobs/some-job/download")
        assert r.status_code == 400, "Absolute path outside reports dir must be blocked"

    def test_unknown_job_returns_404(self, client):
        with db_mock({"select": FakeCursor([])}):
            r = client.get("/api/reports/jobs/unknown/download")
        assert r.status_code == 404
