from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest

from alcove.govdata.congress import (
    CONGRESS_SUMMARIES_COLLECTION,
    ingest_billsum,
    index_billsum_records,
    load_billsum_records,
    parse_billsum_xml,
    write_jsonl,
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


def test_load_billsum_records_handles_source_errors_and_directories(tmp_path):
    with pytest.raises(ValueError, match="Provide"):
        load_billsum_records()
    with pytest.raises(FileNotFoundError):
        load_billsum_records(tmp_path / "missing.xml")
    unsupported = tmp_path / "billsum.txt"
    unsupported.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_billsum_records(unsupported)

    directory = tmp_path / "source"
    directory.mkdir()
    (directory / "subdir").mkdir()
    (directory / "ignore.txt").write_text("ignored", encoding="utf-8")
    (directory / "sample.xml").write_text(GOVINFO_BILLSUM_XML, encoding="utf-8")
    archive_path = directory / "nested.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("sample.xml", GOVINFO_BILLSUM_XML)

    records = load_billsum_records(directory)
    assert len(records) == 2


def test_billsum_download_file(monkeypatch, tmp_path):
    from alcove.govdata import congress

    class FakeResponse:
        def __enter__(self):
            return BytesIO(b"downloaded")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(congress.urllib.request, "urlopen", lambda url: FakeResponse())
    destination = tmp_path / "nested" / "file.xml"

    assert congress.download_file("https://www.govinfo.gov/example.xml", destination) == destination
    assert destination.read_bytes() == b"downloaded"


def test_load_billsum_records_source_url_uses_download(tmp_path, monkeypatch):
    from alcove.govdata import congress

    def fake_download(_url, destination):
        destination.write_text(GOVINFO_BILLSUM_XML, encoding="utf-8")
        return destination

    monkeypatch.setattr(congress, "download_file", fake_download)

    records = load_billsum_records(source_url="https://www.govinfo.gov/example/billsum.xml")

    assert len(records) == 1


def test_load_billsum_jsonl_skips_invalid_rows(tmp_path):
    jsonl_path = tmp_path / "summaries.jsonl"
    valid = {
        "id": "ok",
        "document": "text",
        "metadata": {"source": "x.xml"},
    }
    jsonl_path.write_text(
        "\n".join([
            "",
            "[]",
            json.dumps({"id": "", "document": "text", "metadata": {}}),
            json.dumps({"id": "missing-doc", "metadata": {}}),
            json.dumps({"id": "missing-meta", "document": "text"}),
            json.dumps(valid),
        ]),
        encoding="utf-8",
    )

    assert load_billsum_records(jsonl_path) == [valid]


def test_parse_billsum_xml_handles_legacy_summary_nodes():
    xml = """
    <root>
      <congress>117</congress>
      <summary>
        <billType>sjres</billType>
        <billNumber>9</billNumber>
        <title>Legacy Summary</title>
        <version>v2</version>
        <actionDate>2023-01-01</actionDate>
        <text><![CDATA[<p>Legacy summary text.</p>]]></text>
      </summary>
      <summary>
        <billType>hr</billType>
        <billNumber>10</billNumber>
      </summary>
    </root>
    """

    records = parse_billsum_xml(xml, source="legacy.xml")

    assert len(records) == 1
    assert records[0]["id"] == "bill-117-sjres-9-summary-v2"
    assert records[0]["metadata"]["date_issued"] == "2023-01-01"


def test_parse_billsum_xml_handles_legacy_summary_without_title_and_missing_text():
    xml = """
    <root>
      <summary>
        <congress>117</congress>
        <billType>hr</billType>
        <billNumber>12</billNumber>
        <summaryText>Summary without a title.</summaryText>
      </summary>
      <summary>
        <congress>117</congress>
        <billType>hr</billType>
        <billNumber>13</billNumber>
      </summary>
    </root>
    """

    records = parse_billsum_xml(xml, source="legacy.xml")

    assert len(records) == 1
    assert records[0]["document"] == "Summary without a title."
    assert records[0]["metadata"]["version"] == "legacy-1"


def test_parse_billsum_xml_skips_invalid_items_and_uses_fallbacks():
    xml = """
    <billSummaries>
      <item congress="" measure-type="hr" measure-number="1">
        <summary><summary-text>missing congress</summary-text></summary>
      </item>
      <item congress="118" measure-type="s" measure-number="7">
        <summary summary-id="summary-v5"><summary-text>Fallback title summary.</summary-text></summary>
        <summary><summary-text></summary-text></summary>
      </item>
    </billSummaries>
    """

    records = parse_billsum_xml(xml, source="fallback.xml")

    assert len(records) == 1
    assert records[0]["id"] == "bill-118-s-7-summary-v5"
    assert records[0]["metadata"]["title"] == "S 7"


def test_billsum_helper_branches():
    from defusedxml import ElementTree as ET
    from alcove.govdata import congress

    summary = ET.fromstring("<summary><version>Version 10!</version></summary>")
    assert congress._extract_summary_version(summary, fallback_index=3) == "version10"
    assert congress._extract_summary_text(summary) == ""
    assert congress._normalize_bill_type(None) == ""
    assert congress._normalize_version("!!!") == "v00"
    assert congress._coerce_int("abc") is None
    assert congress._load_indexing_dependencies()[0].__name__ == "get_embedder"


def test_index_billsum_records_empty_returns_zero():
    assert index_billsum_records([]) == 0


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


def test_write_jsonl_creates_parent_directory(tmp_path):
    output = tmp_path / "nested" / "records.jsonl"
    records = [{"id": "a", "document": "text", "metadata": {"source": "x"}}]

    assert write_jsonl(records, output) == output
    assert output.exists()
