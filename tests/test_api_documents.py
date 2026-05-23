"""Tests for /api/offers/{id}/documents endpoint."""
from tests.conftest import FakeCursor, db_mock


class TestDocuments:
    def test_returns_documents_list(self, client):
        with db_mock({
            "from offer": FakeCursor([(1,)]),
            "from document": FakeCursor([(
                1, 1, "prospecto_definitivo",
                "https://cvm.gov.br/doc.pdf", None, "pending",
            )]),
        }):
            r = client.get("/api/offers/1/documents")
        assert r.status_code == 200
        docs = r.json()
        assert isinstance(docs, list)
        if docs:
            assert "title" in docs[0]
            assert "available" in docs[0]
            assert "type" in docs[0]

    def test_returns_404_for_unknown_offer(self, client):
        with db_mock({"from offer": FakeCursor([])}):
            r = client.get("/api/offers/9999/documents")
        assert r.status_code == 404

    def test_empty_document_list(self, client):
        with db_mock({
            "from offer": FakeCursor([(1,)]),
            "from document": FakeCursor([]),
        }):
            r = client.get("/api/offers/1/documents")
        assert r.status_code == 200
        assert r.json() == []
