from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import List


class HashEmbedder:
    """Offline deterministic embedder for local smoke and private-first defaults."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            vals = [(h[i % len(h)] / 255.0) for i in range(self.dim)]
            vectors.append(vals)
        return vectors


class SentenceTransformerEmbedder:
    """Semantic embedder using all-MiniLM-L6-v2. Downloads model on first use (~80MB)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [vec.tolist() for vec in embeddings]


class OllamaEmbedder:
    """Semantic embedder backed by a local Ollama model."""

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        dim: int | None = None,
    ):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "nomic-embed-text")
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.timeout = float(timeout or os.getenv("OLLAMA_TIMEOUT", "60"))
        self.dim = int(dim or os.getenv("OLLAMA_DIM", "768"))

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        try:
            payload = self._post("/api/embed", {"model": self.model_name, "input": texts})
            embeddings = payload.get("embeddings")
            if not isinstance(embeddings, list):
                raise RuntimeError("Ollama /api/embed response did not include embeddings.")
            return embeddings
        except urllib.error.HTTPError as exc:
            if exc.code not in {400, 404}:
                raise RuntimeError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(self._format_url_error(exc)) from exc

        vectors: List[List[float]] = []
        for text in texts:
            try:
                payload = self._post(
                    "/api/embeddings",
                    {"model": self.model_name, "prompt": text},
                )
            except urllib.error.HTTPError as exc:
                raise RuntimeError(self._format_http_error(exc)) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(self._format_url_error(exc)) from exc

            embedding = payload.get("embedding")
            if not isinstance(embedding, list):
                raise RuntimeError("Ollama /api/embeddings response did not include an embedding.")
            vectors.append(embedding)
        return vectors

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _format_http_error(self, exc: urllib.error.HTTPError) -> str:
        return (
            f"Ollama request failed with HTTP {exc.code} against {self.base_url} "
            f"while using model {self.model_name!r}."
        )

    def _format_url_error(self, exc: urllib.error.URLError) -> str:
        return (
            f"Could not reach Ollama at {self.base_url} while using model "
            f"{self.model_name!r}: {exc.reason}"
        )


def get_collection_name(base_name: str) -> str:
    """Append embedder-specific suffix to collection name."""
    embedder = os.getenv("EMBEDDER", "hash")
    if embedder == "sentence-transformers":
        return f"{base_name}_st"
    if embedder == "ollama":
        return f"{base_name}_ollama"
    return base_name


_BUILTIN_EMBEDDERS = {
    "hash": HashEmbedder,
    "sentence-transformers": SentenceTransformerEmbedder,
    "ollama": OllamaEmbedder,
}


def get_embedder():
    """Return embedder instance based on EMBEDDER env var."""
    from alcove.plugins import discover_embedders

    choice = os.getenv("EMBEDDER", "hash")
    embedders = dict(_BUILTIN_EMBEDDERS)
    embedders.update(discover_embedders())
    cls = embedders.get(choice)
    if cls is None:
        raise ValueError(f"Unknown embedder: {choice!r}.")
    return cls()
