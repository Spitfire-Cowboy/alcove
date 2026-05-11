from __future__ import annotations

import importlib

import pytest

from alcove.index.embedder import HashEmbedder

_has_zvec = importlib.util.find_spec("zvec") is not None
_skip_zvec = pytest.mark.skipif(not _has_zvec, reason="zvec not available on this platform")


@pytest.fixture()
def embedder():
    return HashEmbedder(dim=32)


class TestChromaBackend:
    def test_add_and_count(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
        monkeypatch.setenv("CHROMA_COLLECTION", "test_col")
        from alcove.index.backend import ChromaBackend

        backend = ChromaBackend(embedder)
        vecs = embedder.embed(["hello world"])
        backend.add(
            ids=["doc1"],
            embeddings=vecs,
            documents=["hello world"],
            metadatas=[{"source": "test.txt"}],
        )
        assert backend.count() == 1

    def test_query_returns_chromadb_shape(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
        monkeypatch.setenv("CHROMA_COLLECTION", "test_col")
        from alcove.index.backend import ChromaBackend

        backend = ChromaBackend(embedder)
        vecs = embedder.embed(["hello world", "goodbye world"])
        backend.add(
            ids=["d1", "d2"],
            embeddings=vecs,
            documents=["hello world", "goodbye world"],
            metadatas=[{"source": "a.txt"}, {"source": "b.txt"}],
        )
        q_vec = embedder.embed(["hello world"])[0]
        result = backend.query(q_vec, k=2)
        assert "ids" in result
        assert "documents" in result
        assert "distances" in result
        assert len(result["ids"]) == 1  # ChromaDB wraps in outer list
        assert len(result["ids"][0]) == 2

    def test_upsert_overwrites(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
        monkeypatch.setenv("CHROMA_COLLECTION", "test_col")
        from alcove.index.backend import ChromaBackend

        backend = ChromaBackend(embedder)
        vecs = embedder.embed(["version one"])
        backend.add(
            ids=["doc1"],
            embeddings=vecs,
            documents=["version one"],
            metadatas=[{"source": "a.txt"}],
        )
        vecs2 = embedder.embed(["version two"])
        backend.add(
            ids=["doc1"],
            embeddings=vecs2,
            documents=["version two"],
            metadatas=[{"source": "a.txt"}],
        )
        assert backend.count() == 1

    def test_iter_metadata_records_returns_stored_metadata(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
        monkeypatch.setenv("CHROMA_COLLECTION", "test_col")
        from alcove.index.backend import ChromaBackend

        backend = ChromaBackend(embedder)
        vecs = embedder.embed(["hello world"])
        backend.add(
            ids=["doc1"],
            embeddings=vecs,
            documents=["hello world"],
            metadatas=[{"source": "a.txt", "collection": "letters", "author": "Ada"}],
        )

        assert backend.iter_metadata_records() == [
            {
                "source": "a.txt",
                "collection": "letters",
                "author": "Ada",
                "__document": "hello world",
                "__chunk_id": "doc1",
            }
        ]


class _MetadataCollection:
    def __init__(self, name="docs", metadatas=None, documents=None, ids=None, *, raises=False):
        self.name = name
        self._metadatas = metadatas or []
        self._documents = documents or []
        self._ids = ids or []
        self._raises = raises

    def get(self, include):
        assert include == ["metadatas", "documents"]
        if self._raises:
            raise RuntimeError("unavailable")
        return {"metadatas": self._metadatas, "documents": self._documents, "ids": self._ids}


def test_multi_chroma_iter_metadata_records_enriches_collection():
    from alcove.index.backend import MultiChromaBackend

    backend = MultiChromaBackend.__new__(MultiChromaBackend)
    backend._get_all_collections = lambda: [
        _MetadataCollection("science", [{"source": "paper.md"}, None], ["body"], ["chunk-1"]),
        _MetadataCollection("broken", raises=True),
    ]

    assert backend.iter_metadata_records() == [
        {"source": "paper.md", "collection": "science", "__document": "body", "__chunk_id": "chunk-1"}
    ]


def test_multi_root_iter_metadata_records_enriches_collection():
    from alcove.index.backend import MultiRootBackend

    backend = MultiRootBackend.__new__(MultiRootBackend)
    backend._cols = [
        ("letters", object(), _MetadataCollection(metadatas=[{"source": "note.txt"}], documents=["note body"])),
    ]

    assert backend.iter_metadata_records() == [
        {"source": "note.txt", "collection": "letters", "__document": "note body"}
    ]


class _ZvecMetadataDoc:
    def __init__(self, id_="doc-id", **fields):
        self.id = id_
        self._fields = fields

    def field(self, name):
        return self._fields.get(name)


class _ZvecMetadataCollection:
    def __init__(self, docs):
        self._docs = docs

    def query(self, vectors, topk, output_fields):
        assert vectors is None
        assert output_fields == ["document", "source", "collection"]
        return self._docs[:topk]


def test_zvec_iter_metadata_records_returns_source_and_collection():
    from alcove.index.backend import ZvecBackend

    backend = ZvecBackend.__new__(ZvecBackend)
    backend._collection = _ZvecMetadataCollection([
        _ZvecMetadataDoc(id_="a-1", source="a.txt", collection="letters", document="A body"),
        _ZvecMetadataDoc(id_="b-1", source="b.txt"),
    ])
    backend.count = lambda: 2

    assert backend.iter_metadata_records() == [
        {"source": "a.txt", "collection": "letters", "__document": "A body", "__chunk_id": "a-1"},
        {"source": "b.txt", "collection": "default", "__chunk_id": "b-1"},
    ]


@_skip_zvec
class TestZvecBackend:
    def test_add_and_count(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("ZVEC_PATH", str(tmp_path / "zvec"))
        from alcove.index.backend import ZvecBackend

        backend = ZvecBackend(embedder)
        vecs = embedder.embed(["hello world"])
        backend.add(
            ids=["doc1"],
            embeddings=vecs,
            documents=["hello world"],
            metadatas=[{"source": "test.txt"}],
        )
        assert backend.count() == 1

    def test_query_returns_chromadb_shape(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("ZVEC_PATH", str(tmp_path / "zvec"))
        from alcove.index.backend import ZvecBackend

        backend = ZvecBackend(embedder)
        vecs = embedder.embed(["hello world", "goodbye world"])
        backend.add(
            ids=["d1", "d2"],
            embeddings=vecs,
            documents=["hello world", "goodbye world"],
            metadatas=[{"source": "a.txt"}, {"source": "b.txt"}],
        )
        q_vec = embedder.embed(["hello world"])[0]
        result = backend.query(q_vec, k=2)
        assert "ids" in result
        assert "documents" in result
        assert "distances" in result
        assert len(result["ids"]) == 1  # outer list wrapper
        assert len(result["ids"][0]) == 2

    def test_upsert_overwrites(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("ZVEC_PATH", str(tmp_path / "zvec"))
        from alcove.index.backend import ZvecBackend

        backend = ZvecBackend(embedder)
        vecs = embedder.embed(["version one"])
        backend.add(
            ids=["doc1"],
            embeddings=vecs,
            documents=["version one"],
            metadatas=[{"source": "a.txt"}],
        )
        vecs2 = embedder.embed(["version two"])
        backend.add(
            ids=["doc1"],
            embeddings=vecs2,
            documents=["version two"],
            metadatas=[{"source": "a.txt"}],
        )
        assert backend.count() == 1


class TestGetBackend:
    def test_default_is_chromadb(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
        monkeypatch.delenv("VECTOR_BACKEND", raising=False)
        from alcove.index.backend import ChromaBackend, get_backend

        backend = get_backend(embedder)
        assert isinstance(backend, ChromaBackend)

    def test_chromadb_explicit(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
        monkeypatch.setenv("VECTOR_BACKEND", "chromadb")
        from alcove.index.backend import ChromaBackend, get_backend

        backend = get_backend(embedder)
        assert isinstance(backend, ChromaBackend)

    @_skip_zvec
    def test_zvec_explicit(self, embedder, tmp_path, monkeypatch):
        monkeypatch.setenv("ZVEC_PATH", str(tmp_path / "zvec"))
        monkeypatch.setenv("VECTOR_BACKEND", "zvec")
        from alcove.index.backend import ZvecBackend, get_backend

        backend = get_backend(embedder)
        assert isinstance(backend, ZvecBackend)

    def test_unknown_backend_raises(self, embedder, monkeypatch):
        monkeypatch.setenv("VECTOR_BACKEND", "milvus")
        from alcove.index.backend import get_backend

        with pytest.raises(ValueError, match="Unknown.*milvus"):
            get_backend(embedder)
