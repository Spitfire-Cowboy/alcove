from __future__ import annotations

import json
import os
from pathlib import Path

from .backend import get_backend
from .embedder import get_embedder


def _metadata_value(value):
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, ensure_ascii=False)


def run(chunks_file: str | None = None, collection: str = "default") -> int:
    chunks_file = chunks_file or os.getenv("CHUNKS_FILE", "data/processed/chunks.jsonl")

    embedder = get_embedder()
    backend = get_backend(embedder)

    ids, docs, metas = [], [], []
    with Path(chunks_file).open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            ids.append(rec["id"])
            docs.append(rec["chunk"])
            meta = {
                key: _metadata_value(value)
                for key, value in rec.items()
                if key not in {"id", "chunk"}
            }
            meta.setdefault("source", "")
            meta.setdefault("collection", collection)
            metas.append(meta)

    if not ids:
        return 0

    embeddings = embedder.embed(docs)
    backend.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
    return len(ids)


if __name__ == "__main__":
    n = run()
    print(f"indexed {n} chunks")
