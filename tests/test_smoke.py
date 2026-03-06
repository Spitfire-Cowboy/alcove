import json
from pathlib import Path

import pytest

from alcove.ingest.pipeline import chunk_text
from alcove.index.embedder import HashEmbedder


def test_chunk_text_nonempty():
    chunks = list(chunk_text("hello world " * 200, 100, 10))
    assert len(chunks) > 1


def test_embedder_dim():
    emb = HashEmbedder(dim=64).embed(["abc"])
    assert len(emb) == 1
    assert len(emb[0]) == 64


def test_embedder_deterministic():
    e = HashEmbedder(dim=16)
    a = e.embed(["same text"])[0]
    b = e.embed(["same text"])[0]
    assert a == b


def test_seed_index_exists_after_demo_run():
    idx = Path("data/processed/seed_index.json")
    if not idx.exists():
        pytest.skip("seed_index.json not found; run 'make seed-demo' first")
    payload = json.loads(idx.read_text())
    assert payload["total_chunks"] >= 1
