from __future__ import annotations

import json
import logging


def _read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ingest_pipeline_applies_enrichers_to_chunk_records(tmp_path):
    from alcove.ingest.pipeline import run

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "memo.txt").write_text("This is a small internal memo with enough text to chunk.", encoding="utf-8")
    out = tmp_path / "chunks.jsonl"

    def fake_enricher(text, metadata):
        assert metadata["source"].endswith("memo.txt")
        return {"doc_type": "memo", "word_count": len(text.split())}

    from unittest.mock import patch

    with patch("alcove.ingest.pipeline._get_enrichers", return_value={"doctype": fake_enricher}):
        count = run(raw_dir=str(raw), out_file=str(out))

    assert count >= 1
    records = _read_records(out)
    assert records[0]["doc_type"] == "memo"
    assert records[0]["word_count"] >= 1
    assert records[0]["source"].endswith("memo.txt")


def test_ingest_pipeline_ignores_non_dict_enricher_results(tmp_path, caplog):
    from alcove.ingest.pipeline import run

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "note.txt").write_text("hello from note", encoding="utf-8")
    out = tmp_path / "chunks.jsonl"

    from unittest.mock import patch

    with caplog.at_level(logging.WARNING, logger="alcove.ingest.pipeline"):
        with patch("alcove.ingest.pipeline._get_enrichers", return_value={"bad": lambda text, metadata: "nope"}):
            run(raw_dir=str(raw), out_file=str(out))

    records = _read_records(out)
    assert "source" in records[0]
    assert "returned non-dict metadata" in caplog.text


def test_ingest_pipeline_enricher_failures_are_fail_open(tmp_path, caplog):
    from alcove.ingest.pipeline import run

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "story.txt").write_text("a simple story for offline ingest", encoding="utf-8")
    out = tmp_path / "chunks.jsonl"

    def boom(text, metadata):
        raise RuntimeError("enricher exploded")

    from unittest.mock import patch

    with caplog.at_level(logging.WARNING, logger="alcove.ingest.pipeline"):
        with patch("alcove.ingest.pipeline._get_enrichers", return_value={"boom": boom}):
            count = run(raw_dir=str(raw), out_file=str(out))

    assert count >= 1
    assert "Enricher boom failed" in caplog.text
    records = _read_records(out)
    assert records[0]["source"].endswith("story.txt")


def test_apply_enrichers_merges_multiple_results():
    from alcove.ingest.pipeline import _apply_enrichers

    enrichers = {
        "doctype": lambda text, metadata: {"doc_type": "memo"},
        "counts": lambda text, metadata: {"word_count": len(text.split())},
    }

    result = _apply_enrichers("hello there world", {"source": "note.txt"}, enrichers)

    assert result["source"] == "note.txt"
    assert result["doc_type"] == "memo"
    assert result["word_count"] == 3


def test_chunk_text_returns_empty_for_whitespace():
    from alcove.ingest.pipeline import chunk_text

    assert chunk_text("   \n\t  ", size=100, overlap=10) == []
