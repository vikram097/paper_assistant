from app.services import ingestion_service


def test_ingest_pdf_skips_empty_text_documents(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%")

    mock_client = type(
        "MockClient",
        (),
        {
            "scroll": lambda *args, **kwargs: ([], None),
            "upsert": lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("upsert should not run for empty chunks")
            ),
        },
    )()

    monkeypatch.setattr(ingestion_service, "get_qdrant_client", lambda: mock_client)
    monkeypatch.setattr(ingestion_service, "load_pdf", lambda _: ["fake-document"])
    monkeypatch.setattr(ingestion_service, "split_documents", lambda _: [])

    ingestion_service.ingest_pdf(str(pdf_path), owner_id=42)

    assert True
