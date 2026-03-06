from __future__ import annotations

import os

import chromadb
from chromadb.config import Settings

from .embedder import get_collection_name


class ChromaBackend:
    """Vector backend backed by local ChromaDB."""

    def __init__(self, embedder):
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        chroma_path = os.getenv("CHROMA_PATH", "./data/chroma")
        collection_name = get_collection_name(os.getenv("CHROMA_COLLECTION", "alcove_docs"))
        client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = client.get_or_create_collection(name=collection_name)

    def add(self, ids, embeddings, documents, metadatas):
        self._collection.upsert(
            ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings,
        )

    def query(self, embedding, k=3):
        return self._collection.query(query_embeddings=[embedding], n_results=k)

    def count(self):
        return self._collection.count()


class ZvecBackend:
    """Vector backend backed by local zvec."""

    def __init__(self, embedder):
        import zvec as _zvec
        self._zvec = _zvec

        zvec_path = os.getenv("ZVEC_PATH", "./data/zvec")
        collection_name = get_collection_name(os.getenv("CHROMA_COLLECTION", "alcove_docs"))
        self._path = os.path.join(zvec_path, collection_name)
        self._dim = embedder.dim

        try:
            self._collection = _zvec.open(
                path=self._path, option=_zvec.CollectionOption(),
            )
        except Exception:
            schema = _zvec.CollectionSchema(
                name=collection_name,
                fields=[
                    _zvec.FieldSchema("document", _zvec.DataType.STRING),
                    _zvec.FieldSchema("source", _zvec.DataType.STRING),
                ],
                vectors=_zvec.VectorSchema(
                    "embedding", _zvec.DataType.VECTOR_FP32, dimension=self._dim,
                ),
            )
            self._collection = _zvec.create_and_open(
                path=self._path, schema=schema, option=_zvec.CollectionOption(),
            )

    def add(self, ids, embeddings, documents, metadatas):
        _zvec = self._zvec
        docs = []
        for i, id_ in enumerate(ids):
            docs.append(
                _zvec.Doc(
                    id=id_,
                    vectors={"embedding": embeddings[i]},
                    fields={
                        "document": documents[i],
                        "source": metadatas[i].get("source", ""),
                    },
                )
            )
        self._collection.upsert(docs)
        self._collection.flush()

    def query(self, embedding, k=3):
        _zvec = self._zvec
        results = self._collection.query(
            vectors=_zvec.VectorQuery("embedding", vector=embedding),
            topk=k,
            output_fields=["document", "source"],
        )
        ids = []
        documents = []
        distances = []
        for doc in results:
            ids.append(doc.id)
            documents.append(doc.field("document"))
            distances.append(-doc.score)  # negate: ChromaDB uses lower=better
        return {"ids": [ids], "documents": [documents], "distances": [distances]}

    def count(self):
        return self._collection.stats.doc_count


_BUILTIN_BACKENDS = {
    "chromadb": ChromaBackend,
    "zvec": ZvecBackend,
}


def get_backend(embedder):
    """Factory: return vector backend based on VECTOR_BACKEND env var."""
    from alcove.plugins import discover_backends

    name = os.getenv("VECTOR_BACKEND", "chromadb").lower()
    backends = dict(_BUILTIN_BACKENDS)
    backends.update(discover_backends())
    cls = backends.get(name)
    if cls is None:
        raise ValueError(f"Unknown VECTOR_BACKEND: {name!r}")
    return cls(embedder)
