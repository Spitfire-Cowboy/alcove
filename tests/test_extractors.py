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


def _write_sample_pptx(path: Path, lines: list[str]) -> None:
    pptx = pytest.importorskip("pptx", reason="python-pptx not installed")
    from pptx.util import Inches

    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    textbox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
    text_frame = textbox.text_frame
    for index, line in enumerate(lines):
        paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        paragraph.text = line
    presentation.save(str(path))


def test_extract_pptx_returns_slide_text(tmp_path):
    from alcove.ingest.extractors import extract_pptx

    f = tmp_path / "sample.pptx"
    _write_sample_pptx(f, ["Alcove slide title", "Semantic search for local docs"])
    result = extract_pptx(f)
    assert "Alcove slide title" in result
    assert "Semantic search for local docs" in result


def test_extract_pptx_raises_helpful_import_error(tmp_path, monkeypatch):
    from alcove.ingest import extractors

    f = tmp_path / "sample.pptx"
    f.write_bytes(b"not-a-real-pptx")

    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "pptx":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked_import)
    with pytest.raises(ImportError, match="python-pptx is required"):
        extractors.extract_pptx(f)


def test_extract_rtf_returns_plain_text(tmp_path):
    pytest.importorskip("striprtf.striprtf", reason="striprtf not installed")
    from alcove.ingest.extractors import extract_rtf

    f = tmp_path / "sample.rtf"
    f.write_text(r"{\rtf1\ansi Alcove {\b RTF} extractor test.\par Second paragraph.}")

    result = extract_rtf(f)
    assert "Alcove" in result
    assert "RTF" in result
    assert "Second paragraph." in result
    assert "\\b" not in result


def test_extract_rtf_requires_striprtf(tmp_path, monkeypatch):
    from alcove.ingest import extractors

    f = tmp_path / "sample.rtf"
    f.write_text(r"{\rtf1\ansi missing dependency test}")

    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name in {"striprtf", "striprtf.striprtf"}:
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked_import)
    with pytest.raises(ImportError, match=r"striprtf is required.*alcove-search\[rtf\]"):
        extractors.extract_rtf(f)


def test_pipeline_dispatch_includes_html(tmp_path):
    """Pipeline routes .html files through the extractor without error."""
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
    from alcove.ingest.pipeline import run

    f = tmp_path / "notes.md"
    f.write_text("# Notes\n\nLocal retrieval is fast.")
    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))
    assert n >= 1
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert any("Local retrieval is fast." in r["chunk"] for r in records)


def test_pipeline_dispatch_includes_pptx(tmp_path):
    """Pipeline routes .pptx files through the extractor without error."""
    from alcove.ingest.pipeline import run

    f = tmp_path / "deck.pptx"
    _write_sample_pptx(f, ["Deck heading", "Deck body text"])
    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))
    assert n >= 1
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert any("Deck heading" in r["chunk"] for r in records)


def test_pipeline_dispatch_includes_rtf(tmp_path):
    pytest.importorskip("striprtf.striprtf", reason="striprtf not installed")
    from alcove.ingest.pipeline import run

    f = tmp_path / "sample.rtf"
    f.write_text(r"{\rtf1\ansi Pipeline {\b RTF} content.}")
    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))

    assert n >= 1
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert any("Pipeline RTF content." in r["chunk"] for r in records)


def test_extract_tsv_tab_separated(tmp_path):
    """extract_tsv correctly parses tab-delimited files."""
    f = tmp_path / "data.tsv"
    f.write_text("name\tvalue\nalice\t42\nbob\t100\n")
    from alcove.ingest.extractors import extract_tsv
    result = extract_tsv(f)
    assert "alice" in result
    assert "42" in result
    assert "bob" in result


def test_extract_docx_raises_helpful_import_error(tmp_path):
    """extract_docx raises an ImportError with install instructions when python-docx is absent."""
    import sys
    from unittest.mock import patch
    f = tmp_path / "test.docx"
    f.write_bytes(b"fake content")
    # Simulate python-docx not being installed by hiding it from the import system
    with patch.dict(sys.modules, {"docx": None}):
        from alcove.ingest.extractors import extract_docx
        with pytest.raises(ImportError, match="python-docx is required"):
            extract_docx(f)
