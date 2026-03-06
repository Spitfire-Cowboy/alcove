import pytest

st = pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")

from alcove.index.embedder import SentenceTransformerEmbedder


def test_st_embed_shape():
    emb = SentenceTransformerEmbedder()
    result = emb.embed(["hello world"])
    assert len(result) == 1
    assert len(result[0]) == 384


def test_st_embed_batch():
    emb = SentenceTransformerEmbedder()
    result = emb.embed(["hello", "world"])
    assert len(result) == 2
    assert all(len(v) == 384 for v in result)


def test_st_embed_deterministic():
    emb = SentenceTransformerEmbedder()
    a = emb.embed(["same text"])[0]
    b = emb.embed(["same text"])[0]
    assert a == b


def test_st_semantic_similarity():
    """Vectors for semantically similar words should be closer than dissimilar ones."""
    emb = SentenceTransformerEmbedder()
    vecs = emb.embed(["king", "queen", "bicycle"])
    king, queen, bicycle = vecs

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b)

    sim_king_queen = cosine(king, queen)
    sim_king_bicycle = cosine(king, bicycle)
    assert sim_king_queen > sim_king_bicycle
