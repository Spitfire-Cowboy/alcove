from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


def test_metadata_value_serializes_fallback_types():
    from alcove.index.pipeline import _metadata_value

    assert json.loads(_metadata_value((1, 2, 3))) == [1, 2, 3]


def _make_chunks_jsonl(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "chunks.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    return path


def _run_pipeline(chunks_file: Path, *, collection: str = "default") -> tuple[int, dict]:
    captured: dict = {}

    class FakeEmbedder:
        dim = 4

        def embed(self, docs):
            return [[0.1, 0.2, 0.3, 0.4] for _ in docs]

    class FakeBackend:
        def add(self, ids, embeddings, documents, metadatas):
            captured["ids"] = ids
            captured["embeddings"] = embeddings
            captured["documents"] = documents
            captured["metadatas"] = metadatas

    with (
        patch("alcove.index.pipeline.get_embedder", return_value=FakeEmbedder()),
        patch("alcove.index.pipeline.get_backend", return_value=FakeBackend()),
    ):
        from alcove.index.pipeline import run

        count = run(chunks_file=str(chunks_file), collection=collection)

    return count, captured


def test_pipeline_preserves_scalar_metadata_fields(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [
            {
                "id": "doc-1:0",
                "chunk": "example text",
                "source": "paper.pdf",
                "collection": "papers",
                "file_hash": "abc123",
                "added_at": "2026-05-15T12:00:00Z",
                "doi": "10.1000/example",
                "year": 2026,
                "score": 0.95,
                "peer_reviewed": True,
                "empty_value": None,
            }
        ],
    )

    count, captured = _run_pipeline(chunks_file, collection="fallback")

    assert count == 1
    meta = captured["metadatas"][0]
    assert meta["source"] == "paper.pdf"
    assert meta["collection"] == "papers"
    assert meta["file_hash"] == "abc123"
    assert meta["added_at"] == "2026-05-15T12:00:00Z"
    assert meta["doi"] == "10.1000/example"
    assert meta["year"] == 2026
    assert meta["score"] == 0.95
    assert meta["peer_reviewed"] is True
    assert meta["empty_value"] is None


def test_pipeline_serializes_complex_metadata_fields(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [
            {
                "id": "doc-1:0",
                "chunk": "example text",
                "source": "paper.pdf",
                "authors": ["Alice Smith", "Bob Jones"],
                "context": {"journal": "Alcove Studies", "issue": 4},
            }
        ],
    )

    _, captured = _run_pipeline(chunks_file)
    meta = captured["metadatas"][0]

    assert json.loads(meta["authors"]) == ["Alice Smith", "Bob Jones"]
    assert json.loads(meta["context"]) == {"journal": "Alcove Studies", "issue": 4}


def test_pipeline_serializes_other_json_compatible_metadata_fields(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [
            {
                "id": "doc-1:0",
                "chunk": "example text",
                "source": "paper.pdf",
                "coordinates": (41.8781, -87.6298),
            }
        ],
    )

    _, captured = _run_pipeline(chunks_file)
    meta = captured["metadatas"][0]

    assert json.loads(meta["coordinates"]) == [41.8781, -87.6298]


def test_pipeline_omits_id_and_chunk_from_metadata(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [{"id": "doc-1:0", "chunk": "example text", "source": "paper.pdf"}],
    )

    _, captured = _run_pipeline(chunks_file)
    meta = captured["metadatas"][0]

    assert "id" not in meta
    assert "chunk" not in meta


def test_pipeline_falls_back_to_requested_collection(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [{"id": "doc-1:0", "chunk": "example text", "source": "paper.pdf"}],
    )

    _, captured = _run_pipeline(chunks_file, collection="uploads")

    assert captured["metadatas"][0]["collection"] == "uploads"


def test_pipeline_preserves_record_collection_when_present(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [{"id": "doc-1:0", "chunk": "example text", "source": "paper.pdf", "collection": "papers"}],
    )

    _, captured = _run_pipeline(chunks_file, collection="uploads")

    assert captured["metadatas"][0]["collection"] == "papers"


def test_pipeline_defaults_missing_source_to_empty_string(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [{"id": "doc-1:0", "chunk": "example text"}],
    )

    _, captured = _run_pipeline(chunks_file)

    assert captured["metadatas"][0]["source"] == ""


def test_pipeline_keeps_multiple_records_distinct(tmp_path):
    chunks_file = _make_chunks_jsonl(
        tmp_path,
        [
            {"id": "doc-1:0", "chunk": "first", "source": "a.txt", "collection": "alpha"},
            {"id": "doc-2:0", "chunk": "second", "source": "b.txt", "collection": "beta"},
        ],
    )

    count, captured = _run_pipeline(chunks_file)

    assert count == 2
    assert captured["metadatas"][0]["collection"] == "alpha"
    assert captured["metadatas"][1]["collection"] == "beta"
    assert captured["documents"] == ["first", "second"]
