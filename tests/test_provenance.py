from __future__ import annotations

import json
from pathlib import Path


def test_record_index_provenance_for_sentence_transformers_uses_cached_metadata(tmp_path, monkeypatch):
    from alcove import provenance

    cache_root = tmp_path / "hf-cache"
    repo_dir = cache_root / "models--sentence-transformers--all-MiniLM-L6-v2"
    snapshot = repo_dir / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    refs = repo_dir / "refs"
    refs.mkdir(parents=True)
    (refs / "main").write_text("abc123\n", encoding="utf-8")

    versions = {
        "chromadb": "1.5.5",
        "sentence-transformers": "3.1.0",
        "transformers": "4.0.0",
        "torch": "2.0.0",
    }

    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("VECTOR_BACKEND", "chromadb")
    monkeypatch.setenv("EMBEDDER", "sentence-transformers")
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(cache_root))
    monkeypatch.setattr(provenance.importlib_metadata, "version", lambda name: versions[name])
    monkeypatch.setattr(provenance, "entry_points", lambda *, group: [])

    record = provenance.record_index_provenance(
        collection="docs",
        chunk_count=3,
        embedding_dimension=384,
    )

    assert record["embedder"]["name"] == "sentence-transformers"
    assert record["embedder"]["embedding_dimension"] == 384
    assert record["embedder"]["model"]["identifier"] == "all-MiniLM-L6-v2"
    assert record["embedder"]["model"]["revision"] == "abc123"
    assert record["runtime"]["library_versions"]["sentence-transformers"] == "3.1.0"


def test_index_pipeline_writes_hash_provenance_manifest(tmp_path, monkeypatch):
    from alcove.index.pipeline import run

    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text(
        json.dumps({"id": "doc.txt:0", "source": "doc.txt", "chunk": "hello world"}) + "\n",
        encoding="utf-8",
    )

    class DummyEmbedder:
        dim = 4

        def embed(self, texts):
            return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    class DummyBackend:
        def add(self, **kwargs):
            self.kwargs = kwargs

    dummy_backend = DummyBackend()
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("VECTOR_BACKEND", "chromadb")
    monkeypatch.setenv("EMBEDDER", "hash")
    monkeypatch.setattr("alcove.index.pipeline.get_embedder", lambda: DummyEmbedder())
    monkeypatch.setattr("alcove.index.pipeline.get_backend", lambda embedder: dummy_backend)

    count = run(chunks_file=str(chunks_file), collection="letters")

    assert count == 1
    manifest_path = Path(tmp_path / "chroma" / "alcove_provenance.json")
    assert manifest_path.is_file()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["collections"]["letters"]
    assert record["chunk_count"] == 1
    assert record["embedder"]["name"] == "hash"
    assert record["embedder"]["embedding_dimension"] == 4
    assert record["backend"]["name"] == "chromadb"
