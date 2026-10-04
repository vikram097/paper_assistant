from types import SimpleNamespace

from frontend import backend_client


def test_get_documents_caches_within_session(monkeypatch):
    state = {"access_token": "test-token"}
    calls = []
    response = SimpleNamespace(
        status_code=200,
        headers={},
        json=lambda: {"documents": [{"filename": "guide.pdf", "chunks": 2}]},
        raise_for_status=lambda: None,
    )

    monkeypatch.setattr(
        backend_client,
        "st",
        SimpleNamespace(session_state=state, warning=lambda _: None),
    )
    monkeypatch.setattr(
        backend_client.requests,
        "get",
        lambda *args, **kwargs: calls.append(args) or response,
    )

    assert backend_client.get_documents() == response.json()["documents"]
    assert backend_client.get_documents() == response.json()["documents"]
    assert len(calls) == 1


def test_get_documents_uses_cache_when_rate_limited(monkeypatch):
    state = {"access_token": "test-token"}
    current_time = [0.0]
    warnings = []
    success_response = SimpleNamespace(
        status_code=200,
        headers={},
        json=lambda: {"documents": [{"filename": "guide.pdf", "chunks": 2}]},
        raise_for_status=lambda: None,
    )
    limited_response = SimpleNamespace(
        status_code=429,
        headers={"Retry-After": "30"},
        json=lambda: {},
        raise_for_status=lambda: None,
    )
    responses = iter([success_response, limited_response])

    monkeypatch.setattr(
        backend_client,
        "st",
        SimpleNamespace(
            session_state=state,
            warning=warnings.append,
        ),
    )
    monkeypatch.setattr(backend_client.time, "monotonic", lambda: current_time[0])
    monkeypatch.setattr(
        backend_client.requests,
        "get",
        lambda *args, **kwargs: next(responses),
    )

    cached_documents = backend_client.get_documents()
    current_time[0] = 6.0

    assert backend_client.get_documents() == cached_documents
    assert warnings