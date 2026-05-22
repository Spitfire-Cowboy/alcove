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


def test_load_index_provenance_handles_missing_and_invalid_files(tmp_path, monkeypatch):
    from alcove import provenance

    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    assert provenance.load_index_provenance() == {"version": 1, "collections": {}}

    manifest = tmp_path / "chroma" / "alcove_provenance.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{not-json", encoding="utf-8")
    assert provenance.load_index_provenance() == {"version": 1, "collections": {}}


def test_provenance_for_zvec_and_ollama(tmp_path, monkeypatch):
    from alcove import provenance

    versions = {"zvec": "0.3.1"}
    monkeypatch.setenv("VECTOR_BACKEND", "zvec")
    monkeypatch.setenv("ZVEC_PATH", str(tmp_path / "zvec"))
    monkeypatch.setenv("EMBEDDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "custom-embed")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(provenance.importlib_metadata, "version", lambda name: versions[name])
    monkeypatch.setattr(provenance, "entry_points", lambda *, group: [])

    record = provenance.record_index_provenance(
        collection="docs",
        chunk_count=2,
        embedding_dimension=768,
    )

    assert record["backend"]["name"] == "zvec"
    assert record["backend"]["package_version"] == "0.3.1"
    assert record["embedder"]["model"]["identifier"] == "custom-embed"
    assert record["runtime"]["library_versions"]["ollama_base_url"] == "http://localhost:11434"


def test_provenance_plugin_helpers(monkeypatch):
    from alcove import provenance

    class DummyEp:
        name = "custom"
        value = "acme_plugin.embedder:CustomEmbedder"

    monkeypatch.setattr(
        provenance,
        "entry_points",
        lambda *, group: [DummyEp()] if group == provenance.EMBEDDERS_GROUP else [],
    )

    assert provenance._plugin_target(provenance.EMBEDDERS_GROUP, "custom") == "acme_plugin.embedder:CustomEmbedder"
    assert provenance._plugin_target(provenance.EMBEDDERS_GROUP, "missing") is None
    assert provenance._plugin_package_name("custom") == "acme-plugin"
    assert provenance._plugin_package_name("missing") is None


def test_provenance_helper_fallbacks(monkeypatch, tmp_path):
    from alcove import provenance

    monkeypatch.setattr(
        provenance.importlib_metadata,
        "version",
        lambda name: (_ for _ in ()).throw(provenance.importlib_metadata.PackageNotFoundError(name)),
    )
    assert provenance._package_version("missing-package") is None

    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    hf_home = tmp_path / "hf-home"
    monkeypatch.setenv("HF_HOME", str(hf_home))
    assert provenance._huggingface_model_cache("sentence-transformers/missing-model") == {
        "local_path": None,
        "revision": None,
    }

    repo_dir = hf_home / "hub" / "models--sentence-transformers--custom-model"
    (repo_dir / "snapshots").mkdir(parents=True)
    cache = provenance._huggingface_model_cache("sentence-transformers/custom-model")
    assert cache["local_path"] == str(repo_dir)
    assert cache["revision"] is None

    monkeypatch.setenv("EMBEDDER", "hash")
    monkeypatch.setenv("VECTOR_BACKEND", "chromadb")
    monkeypatch.setattr(provenance.importlib_metadata, "version", lambda name: "1.0.0")
    record = provenance.record_index_provenance(collection="docs", chunk_count=1, embedding_dimension=32)
    assert "model" not in record["embedder"]
