from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable

from alcove.plugins import discover_extractors

from .extractors import (
    extract_csv,
    extract_docx,
    extract_epub,
    extract_html,
    extract_json,
    extract_jsonl,
    extract_md,
    extract_pdf,
    extract_pptx,
    extract_rtf,
    extract_rst,
    extract_tsv,
    extract_txt,
)

logger = logging.getLogger(__name__)

_BUILTIN_EXTRACTORS = {
    ".txt": extract_txt,
    ".pdf": extract_pdf,
    ".epub": extract_epub,
    ".html": extract_html,
    ".htm": extract_html,
    ".md": extract_md,
    ".rst": extract_rst,
    ".csv": extract_csv,
    ".tsv": extract_tsv,
    ".json": extract_json,
    ".jsonl": extract_jsonl,
    ".docx": extract_docx,
    ".pptx": extract_pptx,
    ".rtf": extract_rtf,
}


def _get_extractors() -> dict:
    """Merge builtin extractors with any installed plugins (plugins win)."""
    extractors = dict(_BUILTIN_EXTRACTORS)
    extractors.update(discover_extractors())
    return extractors


def chunk_text(text: str, size: int, overlap: int) -> Iterable[str]:
    text = " ".join(text.split())
    if not text:
        return []
    out = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        out.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def run(raw_dir: str | None = None, out_file: str | None = None) -> int:
    chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
    overlap = int(os.getenv("CHUNK_OVERLAP", "150"))
    raw_dir = raw_dir or os.getenv("RAW_DIR", "data/raw")
    out_file = out_file or os.getenv("CHUNKS_FILE", "data/processed/chunks.jsonl")

    raw = Path(raw_dir)
    out = Path(out_file)
    out.parent.mkdir(parents=True, exist_ok=True)

    extractors = _get_extractors()

    total = 0
    with out.open("w", encoding="utf-8") as f:
        for p in raw.rglob("*"):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            extractor = extractors.get(ext)
            if extractor is None:
                continue
            try:
                text = extractor(p)
            except Exception as e:
                print(f"  skipped {p.name}: {e}")
                continue
            if not text.strip():
                logger.warning("Skipping empty file: %s", p)
                continue
            for i, chunk in enumerate(chunk_text(text, chunk_size, overlap)):
                rec = {"id": f"{p.name}:{i}", "source": str(p), "chunk": chunk}
                f.write(json.dumps(rec) + "\n")
                total += 1
    return total


if __name__ == "__main__":
    n = run()
    print(f"wrote {n} chunks")
