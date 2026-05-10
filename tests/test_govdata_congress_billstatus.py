from __future__ import annotations

import json
import zipfile

from alcove.govdata.congress_billstatus import (
    CONGRESS_BILLSTATUS_COLLECTION,
    ingest_billstatus,
    index_billstatus_records,
    load_billstatus_records,
    parse_billstatus_xml,
    write_jsonl,
)

SAMPLE_BILLSTATUS_XML = """<?xml version="1.0" encoding="utf-8"?>
<billStatus>
  <bill>
    <number>42</number>
    <updateDate>2024-01-15T12:00:00Z</updateDate>
    <originChamber>House</originChamber>
    <type>HR</type>
    <introducedDate>2023-01-10</introducedDate>
    <congress>118</congress>
    <legislationUrl>https://www.congress.gov/bill/118th-congress/house-bill/42</legislationUrl>
    <titles>
      <item>
        <titleType>Display Title</titleType>
        <title>Open Archives Act</title>
      </item>
    </titles>
    <sponsors>
      <item>
        <bioguideId>S001176</bioguideId>
        <fullName>Rep. Smith, Jane [D-CA-1]</fullName>
        <party>D</party>
        <state>CA</state>
      </item>
    </sponsors>
    <cosponsors>
      <item>
        <fullName>Rep. Jones, Bob [R-TX-5]</fullName>
      </item>
    </cosponsors>
    <committees>
      <item>
        <name>Judiciary Committee</name>
      </item>
    </committees>
    <policyArea>
      <name>Government Operations and Politics</name>
    </policyArea>
    <actions>
      <item>
        <actionDate>2023-01-10</actionDate>
        <text>Introduced in House</text>
      </item>
      <item>
        <actionDate>2023-03-15</actionDate>
        <text>Subcommittee Hearings Held.</text>
      </item>
    </actions>
    <latestAction>
      <actionDate>2023-03-15</actionDate>
      <text>Subcommittee Hearings Held.</text>
    </latestAction>
    <relatedBills>
      <item>
        <number>100</number>
        <type>S</type>
        <congress>118</congress>
      </item>
    </relatedBills>
  </bill>
</billStatus>
""".strip()


def test_parse_billstatus_xml_extracts_retrieval_record():
    records = parse_billstatus_xml(SAMPLE_BILLSTATUS_XML, source="sample.xml")

    assert len(records) == 1
    record = records[0]
    metadata = record["metadata"]
    assert record["id"] == "billstatus-118-hr-42"
    assert metadata["collection"] == CONGRESS_BILLSTATUS_COLLECTION
    assert metadata["title"] == "Open Archives Act"
    assert metadata["sponsor_name"] == "Rep. Smith, Jane [D-CA-1]"
    assert metadata["cosponsor_count"] == "1"
    assert metadata["committees"] == "Judiciary Committee"
    assert metadata["policy_area"] == "Government Operations and Politics"
    assert metadata["status"] == "active"
    assert metadata["related_bill_count"] == "1"
    assert "Judiciary Committee" in record["document"]


def test_load_billstatus_records_reads_zip_and_jsonl(tmp_path):
    archive_path = tmp_path / "billstatus.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("BILLSTATUS-118hr42.xml", SAMPLE_BILLSTATUS_XML)

    zipped = load_billstatus_records(source=archive_path)
    assert len(zipped) == 1

    jsonl_path = tmp_path / "billstatus.jsonl"
    write_jsonl(zipped, jsonl_path)
    assert load_billstatus_records(source=jsonl_path) == zipped


def test_index_billstatus_records_uses_requested_collection(monkeypatch):
    captured = {}

    class DummyEmbedder:
        def embed(self, texts):
            captured["embedded"] = list(texts)
            return [[0.1, 0.2] for _ in texts]

    class DummyBackend:
        def add(self, ids, embeddings, documents, metadatas):
            captured["ids"] = ids
            captured["embeddings"] = embeddings
            captured["documents"] = documents
            captured["metadatas"] = metadatas

    monkeypatch.setattr(
        "alcove.govdata.congress_billstatus._load_indexing_dependencies",
        lambda: (lambda: DummyEmbedder(), lambda _embedder: DummyBackend()),
    )

    records = parse_billstatus_xml(SAMPLE_BILLSTATUS_XML, source="sample.xml")
    indexed = index_billstatus_records(records, collection_name="public_billstatus")

    assert indexed == 1
    assert captured["ids"] == ["billstatus-118-hr-42"]
    assert captured["metadatas"][0]["collection"] == "public_billstatus"


def test_ingest_billstatus_writes_normalized_jsonl(tmp_path, monkeypatch):
    source_path = tmp_path / "BILLSTATUS-118hr42.xml"
    output_path = tmp_path / "billstatus.jsonl"
    source_path.write_text(SAMPLE_BILLSTATUS_XML, encoding="utf-8")

    monkeypatch.setattr(
        "alcove.govdata.congress_billstatus.index_billstatus_records",
        lambda records, collection_name: len(list(records)),
    )

    count = ingest_billstatus(
        source=source_path,
        collection_name="public_billstatus",
        jsonl_out=output_path,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert count == 1
    assert payload["metadata"]["collection"] == "public_billstatus"
