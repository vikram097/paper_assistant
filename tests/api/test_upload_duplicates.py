from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import documents as documents_api
from app.services import document_service


class FakeDatabase:
    def __init__(self, document):
        self.document = document

    def scalar(self, statement):
        return self.document

    def add(self, document):
        self.document = document

    def commit(self):
        pass

    def refresh(self, document):
        pass

    def rollback(self):
        pass


class FakeQdrantClient:
    def __init__(self, indexed):
        self.indexed = indexed

    def scroll(self, **kwargs):
        return ([object()] if self.indexed else [], None)


def _create_client(monkeypatch, tmp_path, existing_document, indexed, ingested_paths):
    database = FakeDatabase(existing_document)
    app = FastAPI()
    app.include_router(documents_api.router)

    def override_db():
        yield database

    app.dependency_overrides[documents_api.get_db] = override_db
    app.dependency_overrides[documents_api.get_current_user] = lambda: (
        SimpleNamespace(id=1)
    )
    app.dependency_overrides[documents_api.get_ingestion_service] = lambda: (
        lambda path, owner_id: ingested_paths.append((path, owner_id))
    )

    monkeypatch.setattr(document_service, "get_qdrant_client", lambda: (
        FakeQdrantClient(indexed)
    ))
    monkeypatch.chdir(tmp_path)

    return TestClient(app), database


def test_upload_retries_database_record_missing_from_qdrant(
    monkeypatch,
    tmp_path,
):
    document = SimpleNamespace(
        id=7,
        filename="test_upload.pdf",
        file_hash="old-hash",
        owner_id=1,
    )
    ingested_paths = []
    client, database = _create_client(
        monkeypatch,
        tmp_path,
        document,
        indexed=False,
        ingested_paths=ingested_paths,
    )

    response = client.post(
        "/upload",
        files={"file": ("test_upload.pdf", b"retry this PDF", "application/pdf")},
    )

    assert response.status_code == 201
    assert database.document.filename == "test_upload.pdf"
    assert len(ingested_paths) == 1
    assert (tmp_path / ingested_paths[0][0]).read_bytes() == b"retry this PDF"


def test_duplicate_indexed_upload_preserves_stored_pdf(
    monkeypatch,
    tmp_path,
):
    document = SimpleNamespace(
        id=7,
        filename="test_upload.pdf",
        file_hash="old-hash",
        owner_id=1,
    )
    ingested_paths = []
    client, _ = _create_client(
        monkeypatch,
        tmp_path,
        document,
        indexed=True,
        ingested_paths=ingested_paths,
    )
    stored_pdf = tmp_path / "data/raw/1/test_upload.pdf"
    stored_pdf.parent.mkdir(parents=True)
    stored_pdf.write_bytes(b"stored PDF")

    response = client.post(
        "/upload",
        files={"file": ("test_upload.pdf", b"stored PDF", "application/pdf")},
    )

    assert response.status_code == 409
    assert stored_pdf.read_bytes() == b"stored PDF"
    assert not ingested_paths