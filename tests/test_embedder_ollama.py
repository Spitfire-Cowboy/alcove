import json
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from alcove.index.embedder import OllamaEmbedder


class _FakeResponse:
    def __init__(self, payload):
        self._buffer = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, *args, **kwargs):
        return self._buffer.read(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ollama_embedder_uses_batch_endpoint(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(
            {
                "url": req.full_url,
                "payload": json.loads(req.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        return _FakeResponse({"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(
        base_url="http://127.0.0.1:11434",
        model_name="nomic-embed-text",
        timeout=12,
    )

    assert embedder.embed(["hello", "world"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert calls == [
        {
            "url": "http://127.0.0.1:11434/api/embed",
            "payload": {"model": "nomic-embed-text", "input": ["hello", "world"]},
            "timeout": 12,
        }
    ]


def test_ollama_embedder_falls_back_to_legacy_endpoint(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if req.full_url.endswith("/api/embed"):
            raise HTTPError(
                req.full_url,
                404,
                "not found",
                hdrs=None,
                fp=BytesIO(b'{"error":"not found"}'),
            )

        payload = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"embedding": [len(payload["prompt"]), 1.0]})

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(
        base_url="http://127.0.0.1:11434",
        model_name="nomic-embed-text",
        timeout=5,
    )

    assert embedder.embed(["hi", "there"]) == [[2, 1.0], [5, 1.0]]
    assert calls == [
        "http://127.0.0.1:11434/api/embed",
        "http://127.0.0.1:11434/api/embeddings",
        "http://127.0.0.1:11434/api/embeddings",
    ]


def test_ollama_embedder_empty_input_does_not_call_api(monkeypatch):
    def fake_urlopen(req, timeout):
        raise AssertionError("urlopen should not be called for empty input")

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder()

    assert embedder.embed([]) == []


def test_ollama_embedder_reports_unreachable_server(monkeypatch):
    def fake_urlopen(req, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(base_url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError, match="Could not reach Ollama"):
        embedder.embed(["hello"])


def test_ollama_embedder_rejects_batch_response_without_embeddings(monkeypatch):
    def fake_urlopen(req, timeout):
        return _FakeResponse({"ok": True})

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(base_url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError, match="/api/embed response did not include embeddings"):
        embedder.embed(["hello"])


def test_ollama_embedder_reports_batch_http_errors(monkeypatch):
    def fake_urlopen(req, timeout):
        raise HTTPError(req.full_url, 500, "server error", hdrs=None, fp=BytesIO(b""))

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(base_url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        embedder.embed(["hello"])


def test_ollama_embedder_reports_legacy_http_errors(monkeypatch):
    def fake_urlopen(req, timeout):
        if req.full_url.endswith("/api/embed"):
            raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=BytesIO(b""))
        raise HTTPError(req.full_url, 500, "server error", hdrs=None, fp=BytesIO(b""))

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(base_url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        embedder.embed(["hello"])


def test_ollama_embedder_reports_legacy_url_errors(monkeypatch):
    def fake_urlopen(req, timeout):
        if req.full_url.endswith("/api/embed"):
            raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=BytesIO(b""))
        raise URLError("connection refused")

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(base_url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError, match="Could not reach Ollama"):
        embedder.embed(["hello"])


def test_ollama_embedder_rejects_legacy_response_without_embedding(monkeypatch):
    def fake_urlopen(req, timeout):
        if req.full_url.endswith("/api/embed"):
            raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=BytesIO(b""))
        return _FakeResponse({"ok": True})

    monkeypatch.setattr("alcove.index.embedder.urllib.request.urlopen", fake_urlopen)

    embedder = OllamaEmbedder(base_url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError, match="/api/embeddings response did not include an embedding"):
        embedder.embed(["hello"])
