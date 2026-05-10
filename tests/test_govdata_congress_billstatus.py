from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest

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


def test_load_billstatus_records_handles_source_errors_and_limits(tmp_path):
    with pytest.raises(ValueError, match="Provide"):
        load_billstatus_records()
    with pytest.raises(FileNotFoundError):
        load_billstatus_records(source=tmp_path / "missing.xml")
    unsupported = tmp_path / "billstatus.txt"
    unsupported.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_billstatus_records(source=unsupported)

    directory = tmp_path / "source"
    directory.mkdir()
    (directory / "subdir").mkdir()
    (directory / "ignore.txt").write_text("ignored", encoding="utf-8")
    (directory / "one.xml").write_text(SAMPLE_BILLSTATUS_XML, encoding="utf-8")
    archive_path = directory / "two.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("BILLSTATUS-118hr43.xml", SAMPLE_BILLSTATUS_XML)

    records = load_billstatus_records(source=directory, limit=1)
    assert len(records) == 1


def test_billstatus_download_file(monkeypatch, tmp_path):
    from alcove.govdata import congress_billstatus

    class FakeResponse:
        def __enter__(self):
            return BytesIO(b"downloaded")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(congress_billstatus.urllib.request, "urlopen", lambda url: FakeResponse())
    destination = tmp_path / "nested" / "file.xml"

    assert congress_billstatus.download_file("https://www.govinfo.gov/example.xml", destination) == destination
    assert destination.read_bytes() == b"downloaded"


def test_load_billstatus_records_source_url_uses_download(tmp_path, monkeypatch):
    from alcove.govdata import congress_billstatus

    def fake_download(_url, destination):
        destination.write_text(SAMPLE_BILLSTATUS_XML, encoding="utf-8")
        return destination

    monkeypatch.setattr(congress_billstatus, "download_file", fake_download)

    records = load_billstatus_records(source_url="https://www.govinfo.gov/example/billstatus.xml")

    assert len(records) == 1


def test_load_billstatus_jsonl_skips_invalid_rows_and_limits(tmp_path):
    jsonl_path = tmp_path / "billstatus.jsonl"
    valid = {"id": "ok", "document": "text", "metadata": {"source": "x.xml"}}
    second = {"id": "ok-2", "document": "text 2", "metadata": {"source": "y.xml"}}
    jsonl_path.write_text(
        "\n".join([
            "",
            "[]",
            json.dumps({"id": "", "document": "text", "metadata": {}}),
            json.dumps({"id": "missing-doc", "metadata": {}}),
            json.dumps(valid),
            json.dumps(second),
        ]),
        encoding="utf-8",
    )

    assert load_billstatus_records(source=jsonl_path, limit=1) == [valid]


def test_billstatus_zip_skips_non_xml_and_honors_limit(tmp_path):
    archive_path = tmp_path / "billstatus.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("README.txt", "ignore")
        archive.writestr("BILLSTATUS-118hr42.xml", SAMPLE_BILLSTATUS_XML)
        archive.writestr("BILLSTATUS-118hr43.xml", SAMPLE_BILLSTATUS_XML)

    records = load_billstatus_records(source=archive_path, limit=1)

    assert len(records) == 1


def test_parse_billstatus_xml_handles_empty_and_fallback_title():
    assert parse_billstatus_xml("<root />") == []
    xml = """
    <billStatus>
      <bill>
        <number>44</number>
        <type>S.</type>
        <congress>118</congress>
        <title>Fallback Senate Bill</title>
        <originChamber>Senate</originChamber>
      </bill>
    </billStatus>
    """

    records = parse_billstatus_xml(xml, source="fallback.xml")

    assert len(records) == 1
    assert records[0]["metadata"]["title"] == "Fallback Senate Bill"
    assert records[0]["metadata"]["url"].endswith("/senate-bill/44")
    assert records[0]["metadata"]["status"] == "unknown"


def test_parse_billstatus_xml_handles_title_item_fallback_and_missing_required():
    invalid = """
    <billStatus>
      <bill>
        <number>45</number>
        <type>HR</type>
      </bill>
    </billStatus>
    """
    assert parse_billstatus_xml(invalid) == []

    xml = """
    <billStatus>
      <bill>
        <number>46</number>
        <type>HR</type>
        <congress>118</congress>
        <titles>
          <note>ignored</note>
          <item><titleType>Short Title</titleType><title>Short title fallback</title></item>
        </titles>
        <actions>
          <item><text>Action without date.</text></item>
        </actions>
      </bill>
    </billStatus>
    """

    records = parse_billstatus_xml(xml, source="fallback.xml")

    assert len(records) == 1
    assert records[0]["metadata"]["title"] == "Short title fallback"
    assert "Action without date." in records[0]["document"]


def test_billstatus_sitemap_loader(monkeypatch):
    from alcove.govdata import congress_billstatus

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    sitemap = """
    <urlset>
      <url><loc>https://www.govinfo.gov/bulkdata/BILLSTATUS/118/hr/BILLSTATUS-118hr42.xml</loc></url>
      <url><loc>https://www.govinfo.gov/bulkdata/BILLSTATUS/118/hr/readme.txt</loc></url>
      <url><loc>https://www.govinfo.gov/bulkdata/BILLSTATUS/118/hr/BILLSTATUS-118hr43.xml</loc></url>
    </urlset>
    """
    calls = []

    def fake_urlopen(url, timeout=30):
        calls.append(url)
        if url.endswith("sitemap.xml"):
            return FakeResponse(sitemap)
        if url.endswith("43.xml"):
            raise OSError("skip this one")
        return FakeResponse(SAMPLE_BILLSTATUS_XML)

    monkeypatch.setattr(congress_billstatus.urllib.request, "urlopen", fake_urlopen)

    records = load_billstatus_records(congress=118, bill_type="HR", limit=1)

    assert len(records) == 1
    assert calls[0].endswith("/118hr/sitemap.xml")


def test_index_billstatus_records_empty_returns_zero():
    assert index_billstatus_records([]) == 0


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


def test_status_derivation_branches():
    from alcove.govdata import congress_billstatus

    assert congress_billstatus._derive_status("Became Public Law", []) == "enacted"
    assert congress_billstatus._derive_status("Passed Senate", []) == "passed-senate"
    assert congress_billstatus._derive_status("Passed House", []) == "passed-house"
    assert congress_billstatus._derive_status("Failed passage", []) == "failed"
    assert congress_billstatus._derive_status("Vetoed by President", []) == "vetoed"
    assert congress_billstatus._derive_status("Referred to committee", []) == "referred"


def test_billstatus_helper_branches():
    from defusedxml import ElementTree as ET
    from alcove.govdata import congress_billstatus

    assert congress_billstatus._build_congress_url("118", "hjres", "1", "Unknown").endswith("/house-bill/1")
    assert congress_billstatus._find_all(None, "item") == []
    assert congress_billstatus._first_node(None, "bill") is None
    assert congress_billstatus._first_child_node(None, "item") is None
    assert congress_billstatus._direct_child(None, "latestAction") is None
    assert congress_billstatus._text(None, "title") is None
    assert congress_billstatus._text_nested(None, "policyArea", "name") is None
    assert congress_billstatus._normalize_bill_type(None) == ""
    assert congress_billstatus._load_indexing_dependencies()[0].__name__ == "get_embedder"
    assert congress_billstatus._extract_display_title(ET.fromstring("<bill><titles><note /></titles></bill>")) is None
