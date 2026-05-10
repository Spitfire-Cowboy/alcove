from __future__ import annotations

import json
import zipfile

from alcove.govdata.congress import (
    CONGRESS_SUMMARIES_COLLECTION,
    ingest_billsum,
    index_billsum_records,
    load_billsum_records,
    parse_billsum_xml,
)

GOVINFO_BILLSUM_XML = """
<billSummaries>
  <item congress="118" measure-type="hr" measure-number="42" originChamber="House" orig-publish-date="2024-01-10" update-date="2024-01-12">
    <title>Open Archives Act</title>
    <summary summary-id="id118hr42v10" currentChamber="HOUSE">
      <action-date>2024-01-12</action-date>
      <action-desc>Reported by committee</action-desc>
      <summary-text><![CDATA[<p>To improve public access to legislative records.</p>]]></summary-text>
    </summary>
  </item>
</billSummaries>
""".strip()


def test_parse_billsum_xml_handles_govinfo_items():
    records = parse_billsum_xml(GOVINFO_BILLSUM_XML, source="govinfo.xml")

    assert len(records) == 1
    record = records[0]
    assert record["id"] == "bill-118-hr-42-summary-v10"
    assert record["metadata"]["collection"] == CONGRESS_SUMMARIES_COLLECTION
    assert record["metadata"]["bill_type"] == "hr"
    assert record["metadata"]["action_desc"] == "Reported by committee"
    assert record["metadata"]["source_format"] == "govinfo-billsum-xml"
    assert "public access to legislative records" in record["document"]


def test_load_billsum_records_reads_zip_and_jsonl(tmp_path):
    archive_path = tmp_path / "billsum.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("BILLSUM/sample.xml", GOVINFO_BILLSUM_XML)

    zipped = load_billsum_records(archive_path)
    assert len(zipped) == 1
    assert zipped[0]["metadata"]["source"].endswith("sample.xml")

    jsonl_path = tmp_path / "summaries.jsonl"
    jsonl_path.write_text(json.dumps(zipped[0]) + "\n", encoding="utf-8")
    loaded = load_billsum_records(jsonl_path)
    assert loaded == zipped


def test_index_billsum_records_uses_requested_collection(monkeypatch):
    captured = {}

    class DummyEmbedder:
        def embed(self, texts):
            captured["embedded"] = list(texts)
            return [[0.25, 0.5] for _ in texts]

    class DummyBackend:
        def add(self, ids, embeddings, documents, metadatas):
            captured["ids"] = ids
            captured["embeddings"] = embeddings
            captured["documents"] = documents
            captured["metadatas"] = metadatas

    monkeypatch.setattr(
        "alcove.govdata.congress._load_indexing_dependencies",
        lambda: (lambda: DummyEmbedder(), lambda _embedder: DummyBackend()),
    )

    records = parse_billsum_xml(GOVINFO_BILLSUM_XML, source="sample.xml")
    indexed = index_billsum_records(records, collection_name="public_congress")

    assert indexed == 1
    assert captured["ids"] == ["bill-118-hr-42-summary-v10"]
    assert captured["metadatas"][0]["collection"] == "public_congress"


def test_ingest_billsum_writes_normalized_jsonl(tmp_path, monkeypatch):
    source_path = tmp_path / "sample.xml"
    output_path = tmp_path / "summaries.jsonl"
    source_path.write_text(GOVINFO_BILLSUM_XML, encoding="utf-8")

    monkeypatch.setattr(
        "alcove.govdata.congress.index_billsum_records",
        lambda records, collection_name: len(list(records)),
    )

    indexed = ingest_billsum(
        source=source_path,
        collection_name="public_congress",
        jsonl_out=output_path,
    )

    payload = output_path.read_text(encoding="utf-8")
    assert indexed == 1
    assert "public_congress" in payload
