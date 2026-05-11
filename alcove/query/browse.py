from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


EMPTY_BROWSE_STATS = {
    "collections": [],
    "filetypes": [],
    "authors": [],
    "years": [],
    "recent": [],
}


def backend_metadata_records() -> list[dict[str, Any]]:
    """Return indexed metadata records through the backend browse interface."""
    from alcove.index.backend import get_backend
    from alcove.index.embedder import get_embedder

    try:
        backend = get_backend(get_embedder())
        records = backend.iter_metadata_records()
    except Exception:
        return []
    return [dict(meta) for meta in records if isinstance(meta, dict)]


def browse_corpus_stats(records: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Aggregate read-only browse stats from local index metadata."""
    records = backend_metadata_records() if records is None else records
    if not records:
        return dict(EMPTY_BROWSE_STATS)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for meta in records:
        grouped.setdefault(source_key(meta), []).append(meta)

    collections: Counter[str] = Counter()
    filetypes: Counter[str] = Counter()
    authors: Counter[str] = Counter()
    years: Counter[str] = Counter()
    recent: list[dict[str, Any]] = []

    for source, metas in grouped.items():
        first = metas[0]
        label = source_label(source)
        collection = collection_label(first, source)
        collections[collection] += 1

        ext = Path(label).suffix.lower().lstrip(".")
        if ext:
            filetypes[ext.upper()] += 1

        for author in metadata_authors(first):
            authors[author] += 1

        year = str(first.get("year") or "").strip()
        if re.fullmatch(r"\d{4}", year):
            years[year] += 1

        recent.append({
            "label": label,
            "collection": collection,
            "chunk_count": len(metas),
            "sort_time": document_sort_time(source, metas),
        })

    return {
        "collections": counted_items(collections, "name"),
        "filetypes": counted_items(filetypes, "ext"),
        "authors": counted_items(authors, "name")[:50],
        "years": [
            {"year": year, "doc_count": count}
            for year, count in sorted(years.items(), key=lambda item: item[0], reverse=True)
        ],
        "recent": sorted(recent, key=lambda item: (-item["sort_time"], item["label"].lower()))[:12],
    }


def counted_items(counter: Counter[str], key: str) -> list[dict[str, Any]]:
    return [
        {key: name, "doc_count": count}
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
    ]


def source_key(meta: dict[str, Any]) -> str:
    source = str(meta.get("source") or meta.get("path") or meta.get("filename") or "").strip()
    if source:
        return source
    title = str(meta.get("title") or "").strip()
    return title or "(unknown)"


def source_label(source: str) -> str:
    """Return a display label without exposing absolute local paths."""
    if not source or source == "(unknown)":
        return "Unknown source"

    source_path = Path(source)
    raw_dir = Path(os.getenv("RAW_DIR", "data/raw")).expanduser()
    try:
        return source_path.expanduser().resolve().relative_to(raw_dir.resolve()).as_posix()
    except (OSError, ValueError):
        pass

    parts = [part for part in re.split(r"[\\/]+", source) if part]
    if len(parts) >= 2 and parts[-2] not in {"raw", "data"}:
        return f"{parts[-2]}/{parts[-1]}"
    return parts[-1] if parts else source


def collection_label(meta: dict[str, Any], source: str) -> str:
    collection = str(meta.get("collection") or "").strip()
    if collection:
        return collection

    raw_dir = Path(os.getenv("RAW_DIR", "data/raw")).expanduser()
    try:
        rel = Path(source).expanduser().resolve().relative_to(raw_dir.resolve())
    except (OSError, ValueError):
        return "default"
    if len(rel.parts) > 1:
        return rel.parts[0]
    return "default"


def metadata_authors(meta: dict[str, Any]) -> list[str]:
    authors_raw = str(meta.get("authors") or meta.get("author") or "").strip()
    return [author.strip() for author in re.split(r"[;|]+", authors_raw) if author.strip()]


def document_sort_time(source: str, metas: list[dict[str, Any]]) -> float:
    for key in ("uploaded_at", "indexed_at", "modified_at", "created_at"):
        values = [str(meta.get(key) or "").strip() for meta in metas]
        for value in values:
            if not value:
                continue
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue

    try:
        return Path(source).expanduser().stat().st_mtime
    except OSError:
        return 0.0
