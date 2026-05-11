from __future__ import annotations

import json
import os
from pathlib import Path

from .backend import get_backend
from .embedder import get_embedder
from .language import get_language_detector


def run(chunks_file: str | None = None, collection: str = "default") -> int:
    chunks_file = chunks_file or os.getenv("CHUNKS_FILE", "data/processed/chunks.jsonl")

    embedder = get_embedder()
    backend = get_backend(embedder)
    language_detector = None

    ids, docs, metas = [], [], []
    with Path(chunks_file).open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            chunk = rec["chunk"]
            language = rec.get("language")
            if not language:
                if language_detector is None:
                    language_detector = get_language_detector()
                language = language_detector.detect(chunk).language
            ids.append(rec["id"])
            docs.append(chunk)
            metas.append({
                "source": rec["source"],
                "collection": collection,
                "language": str(language).lower(),
            })

    if not ids:
        return 0

    embeddings = embedder.embed(docs)
    backend.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
    return len(ids)


if __name__ == "__main__":
    n = run()
    print(f"indexed {n} chunks")
