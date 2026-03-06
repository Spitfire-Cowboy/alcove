"""Tests for empty/whitespace-only file skipping during ingest."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _read_chunks(out_file: Path) -> list[dict]:
    if not out_file.exists():
        return []
    records = []
    for line in out_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def test_empty_file_is_skipped(tmp_path):
    """Pipeline should skip files with no extractable text."""
    from alcove.ingest.pipeline import run

    empty = tmp_path / "empty.txt"
    empty.write_text("")

    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))

    assert n == 0, f"Expected 0 chunks, got {n}"
    assert _read_chunks(out) == [], "Expected no chunk records in output"


def test_whitespace_only_file_is_skipped(tmp_path):
    """Pipeline should skip files containing only whitespace."""
    from alcove.ingest.pipeline import run

    ws = tmp_path / "blank.txt"
    ws.write_text("   \n\t\n   ")

    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))

    assert n == 0, f"Expected 0 chunks, got {n}"
    assert _read_chunks(out) == [], "Expected no chunk records in output"


def test_empty_file_logs_warning(tmp_path, caplog):
    """Pipeline should emit a warning when skipping an empty file."""
    import logging
    from alcove.ingest.pipeline import run

    empty = tmp_path / "empty.txt"
    empty.write_text("")

    out = tmp_path / "chunks.jsonl"
    with caplog.at_level(logging.WARNING, logger="alcove.ingest.pipeline"):
        run(raw_dir=str(tmp_path), out_file=str(out))

    assert any("empty" in rec.message.lower() for rec in caplog.records), (
        f"Expected a warning about skipping empty file; got: {[r.message for r in caplog.records]}"
    )


def test_nonempty_file_is_not_skipped(tmp_path):
    """Pipeline should still index files that have real content."""
    from alcove.ingest.pipeline import run

    content = tmp_path / "content.txt"
    content.write_text("This is a real document with actual content worth indexing.")

    out = tmp_path / "chunks.jsonl"
    n = run(raw_dir=str(tmp_path), out_file=str(out))

    assert n > 0, "Expected at least one chunk for a non-empty file"
