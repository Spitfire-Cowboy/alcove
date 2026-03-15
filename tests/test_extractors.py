"""Tests for new ingest extractors — RED before GREEN.

Covers issues #23 (HTML) and #24 (.md, .csv, .json, .jsonl, .docx).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_extract_html_strips_tags(tmp_path):
    f = tmp_path / "sample.html"
    f.write_text("<html><body><h1>Hello</h1><p>World</p></body></html>")
    from alcove.ingest.extractors import extract_html
    result = extract_html(f)
    assert "Hello" in result
    assert "World" in result
    assert "<" not in result


def test_extract_html_htm_extension(tmp_path):
    f = tmp_path / "sample.htm"
    f.write_text("<p>HTM file works too</p>")
    from alcove.ingest.extractors import extract_html
    result = extract_html(f)
    assert "HTM file works too" in result


def test_extract_md_returns_raw_text(tmp_path):
    f = tmp_path / "sample.md"
    f.write_text("# Heading\n\nSome paragraph text.")
    from alcove.ingest.extractors import extract_md
    result = extract_md(f)
    assert "Heading" in result
    assert "Some paragraph text." in result


def test_extract_rst_returns_raw_text(tmp_path):
    f = tmp_path / "sample.rst"
    f.write_text("Section Title\n=============\n\nBody text here.")
    from alcove.ingest.extractors import extract_rst
    result = extract_rst(f)
    assert "Section Title" in result
    assert "Body text here." in result


def test_extract_csv_returns_all_fields(tmp_path):
    f = tmp_path / "sample.csv"
    f.write_text("name,role\nAlice,engineer\nBob,designer\n")
    from alcove.ingest.extractors import extract_csv
    result = extract_csv(f)
    assert "Alice" in result
    assert "engineer" in result
    assert "Bob" in result


def test_extract_json_object(tmp_path):
    f = tmp_path / "sample.json"
    f.write_text(json.dumps({"title": "Alcove", "description": "local retrieval"}))
    from alcove.ingest.extractors import extract_json
    result = extract_json(f)
    assert "Alcove" in result
    assert "local retrieval" in result


def test_extract_jsonl_multiple_records(tmp_path):
    f = tmp_path / "sample.jsonl"
    lines = [json.dumps({"text": f"record {i}"}) for i in range(3)]
    f.write_text("\n".join(lines))
    from alcove.ingest.extractors import extract_jsonl
    result = extract_jsonl(f)
    assert "record 0" in result
    assert "record 2" in result


def test_extract_docx_returns_paragraph_text(tmp_path):
    docx = pytest.importorskip("docx", reason="python-docx not installed")
    from alcove.ingest.extractors import extract_docx
    doc = docx.Document()
    doc.add_paragraph("Alcove document extraction test.")
    f = tmp_path / "sample.docx"
    doc.save(str(f))
    result = extract_docx(f)
    assert "Alcove document extraction test." in result


def test_pipeline_dispatch_includes_html(tmp_path):
    """Pipeline routes .html files through the extractor without error."""
    import json
    from alcove.ingest.pipeline import run
    f = tmp_path / "doc.html"
    f.write_text("<p>Semantic search content</p>")
    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))
    assert n >= 1
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert any("Semantic search content" in r["chunk"] for r in records)


def test_pipeline_dispatch_includes_md(tmp_path):
    """Pipeline routes .md files through the extractor without error."""
    import json
    from alcove.ingest.pipeline import run
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n\nLocal retrieval is fast.")
    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))
    assert n >= 1
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert any("Local retrieval is fast." in r["chunk"] for r in records)


# ---------------------------------------------------------------------------
# USLM XML extractor tests
# ---------------------------------------------------------------------------

USLM_NS = "http://xml.house.gov/schemas/uslm/1.0"
DC_NS = "http://purl.org/dc/elements/1.1/"

_USLM_BILL_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<bill xmlns="{uslm}" xmlns:dc="{dc}">
  <meta>
    <dc:title>A Bill to Promote Local Document Retrieval</dc:title>
  </meta>
  <preamble>
    <recital>Whereas local search matters;</recital>
  </preamble>
  <legis-body>
    <section>
      <enum>1.</enum>
      <heading>Short Title</heading>
      <text>This Act may be cited as the "Alcove Act".</text>
    </section>
    <section>
      <enum>2.</enum>
      <heading>Definitions</heading>
      <subsection>
        <enum>(a)</enum>
        <text>The term "document" means any file stored locally.</text>
      </subsection>
    </section>
  </legis-body>
</bill>
""".format(uslm=USLM_NS, dc=DC_NS)

_USLM_BILL_WITH_SPONSOR_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<bill xmlns="{uslm}" xmlns:dc="{dc}">
  <meta>
    <dc:title>Sponsor Test Act</dc:title>
  </meta>
  <legis-body>
    <section>
      <enum>1.</enum>
      <heading>Findings</heading>
      <text>Congress finds that retrieval is important.</text>
      <sponsor>Rep. Jane Smith</sponsor>
      <cosponsor>Rep. John Doe</cosponsor>
    </section>
  </legis-body>
</bill>
""".format(uslm=USLM_NS, dc=DC_NS)

_GENERIC_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <title>Generic Document</title>
  <body>
    <para>First paragraph of generic content.</para>
    <para>Second paragraph.</para>
  </body>
</root>
"""

_EMPTY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<root/>
"""


def test_extract_xml_uslm_bill(tmp_path):
    """USLM bill XML: title and section text are extracted."""
    from alcove.ingest.extractors import extract_xml
    f = tmp_path / "bill.xml"
    f.write_text(_USLM_BILL_XML, encoding="utf-8")
    result = extract_xml(f)
    assert "A Bill to Promote Local Document Retrieval" in result
    assert "Alcove Act" in result
    assert "<" not in result, "XML tags should not appear in output"


def test_extract_xml_uslm_preserves_headings(tmp_path):
    """USLM bill XML: section headings appear in extracted output."""
    from alcove.ingest.extractors import extract_xml
    f = tmp_path / "bill_headings.xml"
    f.write_text(_USLM_BILL_XML, encoding="utf-8")
    result = extract_xml(f)
    assert "Short Title" in result
    assert "Definitions" in result


def test_extract_xml_uslm_sponsor_metadata(tmp_path):
    """USLM bill XML: sponsor and cosponsor text is included."""
    from alcove.ingest.extractors import extract_xml
    f = tmp_path / "bill_sponsor.xml"
    f.write_text(_USLM_BILL_WITH_SPONSOR_XML, encoding="utf-8")
    result = extract_xml(f)
    assert "Rep. Jane Smith" in result
    assert "Rep. John Doe" in result


def test_extract_xml_generic_fallback(tmp_path):
    """Non-USLM XML falls back to plain tag-stripped text."""
    from alcove.ingest.extractors import extract_xml
    f = tmp_path / "generic.xml"
    f.write_text(_GENERIC_XML, encoding="utf-8")
    result = extract_xml(f)
    assert "Generic Document" in result
    assert "First paragraph of generic content." in result
    assert "<" not in result, "XML tags should not appear in fallback output"


def test_extract_xml_empty_elements_skipped(tmp_path):
    """Empty XML document produces empty or whitespace-only output."""
    from alcove.ingest.extractors import extract_xml
    f = tmp_path / "empty.xml"
    f.write_text(_EMPTY_XML, encoding="utf-8")
    result = extract_xml(f)
    assert result.strip() == ""


def test_pipeline_dispatches_xml(tmp_path):
    """Pipeline routes .xml files through extract_xml and writes chunks."""
    import json
    from alcove.ingest.pipeline import run
    f = tmp_path / "bill.xml"
    f.write_text(_USLM_BILL_XML, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))
    assert n >= 1
    records = [json.loads(line) for line in out.read_text().splitlines()]
    combined = " ".join(r["chunk"] for r in records)
    assert "Alcove Act" in combined
    assert "Short Title" in combined
    # Verify required chunk fields are present
    for r in records:
        assert "id" in r
        assert "source" in r
        assert "chunk" in r
