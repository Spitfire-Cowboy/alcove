from __future__ import annotations

import json
from pathlib import Path

import pytest

from alcove.govdata.mirrulations import (
    MIRRULATIONS_COLLECTION,
    ingest_mirrulations,
    index_mirrulations_records,
    load_mirrulations_records,
)


def test_load_mirrulations_records_normalizes_text_tree(tmp_path):
    text_dir = _make_text_tree(tmp_path, agency="EPA", docket_id="EPA-HQ-OAR-2023-0534")

    records = load_mirrulations_records(text_dir.parent.parent)

    assert len(records) == 5
    ids = {record["id"] for record in records}
    assert "docket-EPA-HQ-OAR-2023-0534" in ids
    assert "document-EPA-HQ-OAR-2023-0534-0001" in ids
    assert "comment-EPA-HQ-OAR-2023-0534-0002" in ids
    assert "attachment-document-EPA-HQ-OAR-2023-0534-0001_content_extracted" in ids
    assert "attachment-comment-EPA-HQ-OAR-2023-0534-0002_attachment_1_extracted" in ids

    comment = next(record for record in records if record["metadata"]["entry_type"] == "comment")
    assert "This proposal improves public health." in comment["document"]
    assert "<p>" not in comment["document"]
    assert comment["metadata"]["agency"] == "EPA"
    assert comment["metadata"]["docket_id"] == "EPA-HQ-OAR-2023-0534"
    assert comment["metadata"]["url"] == "https://www.regulations.gov/document/EPA-HQ-OAR-2023-0534-0002"


def test_load_mirrulations_records_filters_agencies(tmp_path):
    _make_text_tree(tmp_path, agency="EPA", docket_id="EPA-HQ-OAR-2023-0534")
    _make_text_tree(tmp_path, agency="SEC", docket_id="SEC-2024-0007")

    records = load_mirrulations_records(tmp_path, agencies=["epa"])

    assert records
    assert all(record["metadata"]["agency"] == "EPA" for record in records)


def test_load_mirrulations_records_handles_source_errors_and_direct_text_dir(tmp_path):
    with pytest.raises(ValueError, match="Provide"):
        load_mirrulations_records()
    with pytest.raises(FileNotFoundError):
        load_mirrulations_records(tmp_path / "missing")

    text_dir = _make_text_tree(tmp_path, agency="EPA", docket_id="EPA-HQ-OAR-2023-0534")
    records = load_mirrulations_records(text_dir)

    assert len(records) == 5


def test_load_mirrulations_records_skips_missing_text(tmp_path):
    text_dir = tmp_path / "EPA" / "EPA-HQ-OAR-2023-0534" / "text-EPA-HQ-OAR-2023-0534"
    (text_dir / "documents").mkdir(parents=True)
    (text_dir / "comments").mkdir()
    _write_json(
        text_dir / "documents" / "empty.json",
        {"data": {"id": "empty-doc", "attributes": {"title": "Empty"}}},
    )
    _write_json(
        text_dir / "comments" / "empty.json",
        {"data": {"id": "empty-comment", "attributes": {"organization": "Public Org"}}},
    )

    assert load_mirrulations_records(tmp_path) == []


def test_index_mirrulations_records_tags_requested_collection(monkeypatch):
    captured = {}

    class DummyEmbedder:
        def embed(self, texts):
            captured["embedded"] = list(texts)
            return [[0.125, 0.25] for _ in texts]

    class DummyBackend:
        def add(self, ids, embeddings, documents, metadatas):
            captured["ids"] = ids
            captured["embeddings"] = embeddings
            captured["documents"] = documents
            captured["metadatas"] = metadatas

    monkeypatch.setattr(
        "alcove.govdata.mirrulations._load_indexing_dependencies",
        lambda: (lambda: DummyEmbedder(), lambda embedder: DummyBackend()),
    )

    records = [
        {
            "id": "comment-EPA-HQ-OAR-2023-0534-0002",
            "document": "EPA comment\n\nThis proposal improves public health.",
            "metadata": {
                "collection": MIRRULATIONS_COLLECTION,
                "source": "comment.json",
                "entry_type": "comment",
            },
        }
    ]
    indexed = index_mirrulations_records(records, collection_name="regulatory_test_docs")

    assert indexed == 1
    assert captured["ids"] == ["comment-EPA-HQ-OAR-2023-0534-0002"]
    assert captured["embedded"] == ["EPA comment\n\nThis proposal improves public health."]
    assert captured["metadatas"][0]["collection"] == "regulatory_test_docs"


def test_index_mirrulations_records_empty_returns_zero():
    assert index_mirrulations_records([]) == 0


def test_mirrulations_loader_handles_alternate_payload_shapes(tmp_path):
    text_dir = tmp_path / "EPA" / "EPA-HQ-OAR-2023-0534" / "text-EPA-HQ-OAR-2023-0534"
    (text_dir / "docket").mkdir(parents=True)
    (text_dir / "documents").mkdir()
    (text_dir / "comments").mkdir()
    (text_dir / "documents_extracted_text" / "pikepdf").mkdir(parents=True)

    _write_json(
        text_dir / "docket" / "EPA-HQ-OAR-2023-0534.json",
        {"attributes": {"description": "Fallback docket description.", "modifyDate": "2024-02-03"}},
    )
    _write_json(
        text_dir / "documents" / "doc.json",
        {"id": "EPA-HQ-OAR-2023-0534-0003", "attributes": {"abstract": "Fallback abstract body."}},
    )
    _write_json(
        text_dir / "comments" / "comment.json",
        {"attributes": {"commentText": "Fallback public comment body.", "title": "Fallback Comment"}},
    )
    (text_dir / "documents_extracted_text" / "pikepdf" / "EPA-HQ-OAR-2023-0534-0003_content.txt").write_text(
        "Content suffix attachment text.",
        encoding="utf-8",
    )
    (text_dir / "documents_extracted_text" / "pikepdf" / "empty.txt").write_text("", encoding="utf-8")

    records = load_mirrulations_records(tmp_path)

    assert {record["metadata"]["entry_type"] for record in records} == {"docket", "document", "comment", "attachment"}
    assert any(record["metadata"]["posted_date"] == "2024-02-03" for record in records)
    attachment = next(record for record in records if record["metadata"]["entry_type"] == "attachment")
    assert attachment["metadata"]["parent_id"] == "EPA-HQ-OAR-2023-0534-0003"


def test_mirrulations_helpers_cover_fallbacks():
    from alcove.govdata import mirrulations

    assert mirrulations._load_indexing_dependencies()[0].__name__ == "get_embedder"
    assert mirrulations._extract_attributes({"data": []}) == {}
    assert mirrulations._extract_entity_id({"data": {"id": ""}, "id": ""}, fallback="fallback-id") == "fallback-id"
    assert mirrulations._agency_for_text_dir(Path("text-ORPHAN")) == "UNKNOWN"
    assert mirrulations._parent_id_for_attachment("plain_content") == "plain"
    assert mirrulations._compose_record_text("Same", "Same") == "Same"


def test_ingest_mirrulations_writes_requested_collection_to_jsonl(tmp_path, monkeypatch):
    text_dir = _make_text_tree(tmp_path, agency="EPA", docket_id="EPA-HQ-OAR-2023-0534")
    output_path = tmp_path / "mirrulations.jsonl"

    monkeypatch.setattr(
        "alcove.govdata.mirrulations.index_mirrulations_records",
        lambda records, collection_name: len(list(records)),
    )
    indexed = ingest_mirrulations(
        source=text_dir.parent.parent,
        collection_name="regulatory_test_docs",
        jsonl_out=output_path,
    )

    payload = output_path.read_text(encoding="utf-8")
    assert indexed == 5
    assert "regulatory_test_docs" in payload
    assert "EPA-HQ-OAR-2023-0534" in payload


def _make_text_tree(root, *, agency: str, docket_id: str):
    text_dir = root / agency / docket_id / f"text-{docket_id}"
    (text_dir / "docket").mkdir(parents=True)
    (text_dir / "documents").mkdir(parents=True)
    (text_dir / "comments").mkdir(parents=True)
    (text_dir / "documents_extracted_text" / "pikepdf").mkdir(parents=True)
    (text_dir / "comments_extracted_text" / "pikepdf").mkdir(parents=True)

    _write_json(
        text_dir / "docket" / f"{docket_id}.json",
        {
            "data": {
                "id": docket_id,
                "attributes": {
                    "title": "Power Plant Emissions Rule",
                    "summary": "Proposal to reduce sulfur dioxide and particulate emissions.",
                },
            }
        },
    )
    _write_json(
        text_dir / "documents" / f"{docket_id}-0001.json",
        {
            "data": {
                "id": f"{docket_id}-0001",
                "attributes": {
                    "title": "Draft Rule Text",
                    "category": "Rule",
                    "postedDate": "2023-10-01",
                },
            }
        },
    )
    (text_dir / "documents" / f"{docket_id}-0001_content.htm").write_text(
        "<html><body><p>The proposed rule lowers emissions limits for coal plants.</p></body></html>",
        encoding="utf-8",
    )
    _write_json(
        text_dir / "comments" / f"{docket_id}-0002.json",
        {
            "data": {
                "id": f"{docket_id}-0002",
                "attributes": {
                    "organization": "Clean Air Alliance",
                    "comment": "<p>This proposal improves public health.</p>",
                    "modifyDate": "2023-10-12T14:17:51Z",
                },
            }
        },
    )
    (text_dir / "documents_extracted_text" / "pikepdf" / f"{docket_id}-0001_content_extracted.txt").write_text(
        "Attachment appendix with emissions tables.",
        encoding="utf-8",
    )
    (text_dir / "comments_extracted_text" / "pikepdf" / f"{docket_id}-0002_attachment_1_extracted.txt").write_text(
        "Attached epidemiology study supporting tighter particulate controls.",
        encoding="utf-8",
    )
    return text_dir


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
