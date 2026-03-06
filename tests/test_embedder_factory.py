import os
import pytest

from alcove.index.embedder import HashEmbedder


def test_get_embedder_default_is_hash():
    from alcove.index.embedder import get_embedder

    os.environ.pop("EMBEDDER", None)
    emb = get_embedder()
    assert isinstance(emb, HashEmbedder)


def test_get_embedder_explicit_hash():
    from alcove.index.embedder import get_embedder

    os.environ["EMBEDDER"] = "hash"
    try:
        emb = get_embedder()
        assert isinstance(emb, HashEmbedder)
    finally:
        os.environ.pop("EMBEDDER", None)


def test_get_embedder_unknown_raises():
    from alcove.index.embedder import get_embedder

    os.environ["EMBEDDER"] = "bogus"
    try:
        with pytest.raises(ValueError, match="Unknown embedder"):
            get_embedder()
    finally:
        os.environ.pop("EMBEDDER", None)


def test_get_collection_name_hash_no_suffix():
    from alcove.index.embedder import get_collection_name

    os.environ.pop("EMBEDDER", None)
    name = get_collection_name("alcove_docs")
    assert name == "alcove_docs"


def test_get_collection_name_hash_explicit():
    from alcove.index.embedder import get_collection_name

    os.environ["EMBEDDER"] = "hash"
    try:
        name = get_collection_name("alcove_docs")
        assert name == "alcove_docs"
    finally:
        os.environ.pop("EMBEDDER", None)


def test_get_collection_name_st_appends_suffix():
    from alcove.index.embedder import get_collection_name

    os.environ["EMBEDDER"] = "sentence-transformers"
    try:
        name = get_collection_name("alcove_docs")
        assert name == "alcove_docs_st"
    finally:
        os.environ.pop("EMBEDDER", None)
