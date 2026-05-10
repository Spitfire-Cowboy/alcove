from __future__ import annotations

import json

from fastapi.testclient import TestClient

from alcove.index.language import detect_language
from alcove.query import api
from alcove.query.retriever import query_text


class _FakeEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class _CaptureBackend:
    def __init__(self):
        self.add_calls = []
        self.query_calls = []

    def add(self, ids, embeddings, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "embeddings": embeddings,
            "documents": documents,
            "metadatas": metadatas,
        })

    def query(self, embedding, k=3, collections=None, language_filter=None):
        self.query_calls.append({
            "embedding": embedding,
            "k": k,
            "collections": collections,
            "language_filter": language_filter,
        })
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}


def test_detect_language_empty_returns_unknown():
    assert detect_language("") == "unknown"


def test_detect_language_english_returns_en():
    text = "The harbor interviews describe family history, migration, and faith traditions in detail."
    assert detect_language(text) == "en"


def test_detect_language_spanish_returns_es():
    text = "Las entrevistas familiares describen historia, migracion, tradiciones y memoria colectiva."
    assert detect_language(text) == "es"


def test_index_pipeline_writes_language_metadata(tmp_path, monkeypatch):
    from alcove.index import pipeline

    chunks_file = tmp_path / "chunks.jsonl"
    rows = [
        {
            "id": "a:0",
            "source": "english.txt",
            "chunk": "The interview transcript discusses work, family, and local history in Minnesota.",
        },
        {
            "id": "b:0",
            "source": "spanish.txt",
            "chunk": "La entrevista habla de trabajo, familia y memoria cultural en la comunidad.",
        },
    ]
    chunks_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    backend = _CaptureBackend()
    monkeypatch.setattr(pipeline, "get_embedder", lambda: _FakeEmbedder())
    monkeypatch.setattr(pipeline, "get_backend", lambda _embedder: backend)

    total = pipeline.run(chunks_file=str(chunks_file))

    assert total == 2
    metadatas = backend.add_calls[0]["metadatas"]
    assert [meta["source"] for meta in metadatas] == ["english.txt", "spanish.txt"]
    assert [meta["language"] for meta in metadatas] == ["en", "es"]


def test_retriever_passes_language_filter(monkeypatch):
    from alcove.query import retriever

    backend = _CaptureBackend()
    monkeypatch.setattr(retriever, "get_embedder", lambda: _FakeEmbedder())
    monkeypatch.setattr(retriever, "get_backend", lambda _embedder: backend)

    result = query_text("hola mundo", n_results=4, language_filter="es")

    assert result["ids"] == [[]]
    assert backend.query_calls[0]["k"] == 4
    assert backend.query_calls[0]["language_filter"] == "es"


def test_api_query_accepts_language_filter(monkeypatch):
    called = {}

    def fake_query_text(query, n_results=3, language_filter=None, **kwargs):
        called["query"] = query
        called["k"] = n_results
        called["language_filter"] = language_filter
        called["collections"] = kwargs.get("collections")
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}

    monkeypatch.setattr(api, "query_text", fake_query_text)

    client = TestClient(api.app)
    response = client.post("/query", json={"query": "hola", "k": 2, "language_filter": "es"})

    assert response.status_code == 200
    assert called == {"query": "hola", "k": 2, "language_filter": "es", "collections": None}


def test_keyword_search_can_filter_by_language(tmp_path):
    from alcove.index.keyword import KeywordIndex

    chunks_file = tmp_path / "chunks.jsonl"
    rows = [
        {
            "id": "en:0",
            "source": "english.txt",
            "chunk": "The family interview covers community history.",
        },
        {
            "id": "es:0",
            "source": "spanish.txt",
            "chunk": "La entrevista familiar cubre historia de la comunidad.",
        },
    ]
    chunks_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = KeywordIndex(str(chunks_file)).search("historia comunidad", k=3, language_filter="es")

    assert result["ids"] == [["es:0"]]
    assert result["metadatas"][0][0]["language"] == "es"
