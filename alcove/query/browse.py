from __future__ import annotations

import hashlib
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

    groups = source_groups(records)
    documents = documents_from_groups(groups)

    collections: Counter[str] = Counter()
    filetypes: Counter[str] = Counter()
    authors: Counter[str] = Counter()
    years: Counter[str] = Counter()

    # Collection and filetype counts use grouped source documents. Author and
    # year facets below inspect raw metadata so chunks without text still count.
    for document in documents:
        collections[document["collection"]] += 1

        ext = Path(document["label"]).suffix.lower().lstrip(".")
        if ext:
            filetypes[ext.upper()] += 1

    for metas in groups.values():
        meta = metas[0]

        for author in metadata_authors(meta):
            authors[author] += 1

        year = str(meta.get("year") or "").strip()
        if re.fullmatch(r"\d{4}", year):
            years[year] += 1

    return {
        "collections": counted_items(collections, "name"),
        "filetypes": counted_items(filetypes, "ext"),
        "authors": counted_items(authors, "name")[:50],
        "years": [
            {"year": year, "doc_count": count}
            for year, count in sorted(years.items(), key=lambda item: item[0], reverse=True)
        ],
        "recent": sorted(documents, key=lambda item: (-item["sort_time"], item["label"].lower()))[:12],
    }


def browse_document_detail(
    document_id: str,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return one read-only source document entry by stable browse ID."""
    records = backend_metadata_records() if records is None else records
    for document in browse_documents(records):
        if document["id"] == document_id:
            return document
    return None


def browse_documents(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return documents_from_groups(source_groups(records))


def source_groups(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for meta in records:
        grouped.setdefault(source_key(meta), []).append(meta)
    return grouped


def documents_from_groups(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for source, metas in groups.items():
        first = metas[0]
        documents.append(
            {
                "id": browse_document_id(source),
                "label": source_label(source),
                "collection": collection_label(first, source),
                "chunk_count": len(metas),
                "sort_time": document_sort_time(source, metas),
                "chunks": document_chunks(metas),
            }
        )
    return documents


def document_chunks(metas: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "id": str(meta.get("__chunk_id") or ""),
            "text": chunk_preview(str(meta.get("__document") or "")),
        }
        for meta in metas
        if str(meta.get("__document") or "").strip()
    ][:8]


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


def browse_document_id(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def chunk_preview(text: str, *, limit: int = 360) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."
