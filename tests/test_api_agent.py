"""Tests for /api/agent/* endpoints."""
from tests.conftest import FakeCursor, db_mock


class TestConversations:
    def test_list_returns_array(self, client):
        with db_mock({"select": FakeCursor([
            ("uuid-1", "thread-1", "Conversa 1",
             "2026-05-22T10:00:00", "2026-05-22T11:00:00"),
        ])}):
            r = client.get("/api/agent/conversations")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_returns_conversation(self, client):
        with db_mock({"insert": FakeCursor([
            ("uuid-new", "thread-new", "Nova conversa",
             "2026-05-22T10:00:00", "2026-05-22T10:00:00"),
        ])}):
            r = client.post("/api/agent/conversations")
        assert r.status_code == 201
        d = r.json()
        assert "thread_id" in d
        assert "id" in d

    def test_empty_list(self, client):
        with db_mock({"select": FakeCursor([])}):
            r = client.get("/api/agent/conversations")
        assert r.status_code == 200
        assert r.json() == []


class TestSendMessage:
    def test_missing_thread_id_returns_422(self, client):
        r = client.post("/api/agent/messages", json={"message": "test"})
        assert r.status_code == 422

    def test_missing_message_returns_422(self, client):
        r = client.post("/api/agent/messages", json={"thread_id": "abc"})
        assert r.status_code == 422

    def test_unknown_thread_returns_404(self, client):
        with db_mock({"select": FakeCursor([])}):
            r = client.post("/api/agent/messages", json={
                "thread_id": "nonexistent-thread",
                "message": "Olá",
            })
        assert r.status_code == 404
