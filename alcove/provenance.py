from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from alcove import __version__
from alcove.plugins import BACKENDS_GROUP, EMBEDDERS_GROUP, entry_points

PROVENANCE_VERSION = 1


def provenance_manifest_path() -> Path:
    backend_name = os.getenv("VECTOR_BACKEND", "chromadb").lower()
    if backend_name == "zvec":
        root = Path(os.getenv("ZVEC_PATH", "./data/zvec"))
    else:
        root = Path(os.getenv("CHROMA_PATH", "./data/chroma"))
    return root / "alcove_provenance.json"


def load_index_provenance() -> dict[str, Any]:
    path = provenance_manifest_path()
    if not path.is_file():
        return {"version": PROVENANCE_VERSION, "collections": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": PROVENANCE_VERSION, "collections": {}}


def record_index_provenance(
    *,
    collection: str,
    chunk_count: int,
    embedding_dimension: int | None,
) -> dict[str, Any]:
    path = provenance_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = load_index_provenance()
    payload["version"] = PROVENANCE_VERSION
    payload["updated_at"] = _now_iso()
    collections = payload.setdefault("collections", {})
    collections[collection] = _collection_provenance_record(
        collection=collection,
        chunk_count=chunk_count,
        embedding_dimension=embedding_dimension,
    )

    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return collections[collection]


def _collection_provenance_record(
    *,
    collection: str,
    chunk_count: int,
    embedding_dimension: int | None,
) -> dict[str, Any]:
    backend_name = os.getenv("VECTOR_BACKEND", "chromadb").lower()
    embedder_name = os.getenv("EMBEDDER", "hash")
    record: dict[str, Any] = {
        "collection": collection,
        "indexed_at": _now_iso(),
        "chunk_count": chunk_count,
        "backend": {
            "name": backend_name,
            "implementation": _builtin_backend_impl(backend_name) or _plugin_target(BACKENDS_GROUP, backend_name),
            "storage_path": str(provenance_manifest_path().parent),
            "package_version": _package_version("chromadb" if backend_name == "chromadb" else backend_name),
        },
        "embedder": {
            "name": embedder_name,
            "implementation": _builtin_embedder_impl(embedder_name) or _plugin_target(EMBEDDERS_GROUP, embedder_name),
            "implementation_package": "alcove-search" if _builtin_embedder_impl(embedder_name) else _plugin_package_name(embedder_name),
            "implementation_package_version": _package_version(
                "alcove-search" if _builtin_embedder_impl(embedder_name) else _plugin_package_name(embedder_name)
            ),
            "embedding_dimension": embedding_dimension,
        },
        "runtime": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "library_versions": _library_versions_for(embedder_name, backend_name),
        },
    }
    model = _embedder_model_info(embedder_name)
    if model is not None:
        record["embedder"]["model"] = model
    return record


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _builtin_backend_impl(name: str) -> str | None:
    mapping = {
        "chromadb": "alcove.index.backend.ChromaBackend",
        "zvec": "alcove.index.backend.ZvecBackend",
    }
    return mapping.get(name)


def _builtin_embedder_impl(name: str) -> str | None:
    mapping = {
        "hash": "alcove.index.embedder.HashEmbedder",
        "sentence-transformers": "alcove.index.embedder.SentenceTransformerEmbedder",
        "ollama": "alcove.index.embedder.OllamaEmbedder",
    }
    return mapping.get(name)


def _plugin_target(group: str, name: str) -> str | None:
    for ep in entry_points(group=group):
        if ep.name == name:
            return ep.value
    return None


def _plugin_package_name(name: str) -> str | None:
    target = _plugin_target(EMBEDDERS_GROUP, name)
    if not target:
        return None
    return target.split(":", 1)[0].split(".", 1)[0].replace("_", "-")


def _package_version(name: str | None) -> str | None:
    if not name:
        return None
    try:
        if name == "alcove-search":
            return __version__
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _library_versions_for(embedder_name: str, backend_name: str) -> dict[str, str]:
    libraries: dict[str, str] = {}
    backend_pkg = "chromadb" if backend_name == "chromadb" else backend_name
    backend_version = _package_version(backend_pkg)
    if backend_version:
        libraries[backend_pkg] = backend_version

    if embedder_name == "sentence-transformers":
        for pkg in ("sentence-transformers", "transformers", "torch"):
            version = _package_version(pkg)
            if version:
                libraries[pkg] = version
    elif embedder_name == "ollama":
        libraries["ollama_base_url"] = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    return libraries


def _embedder_model_info(name: str) -> dict[str, Any] | None:
    if name == "sentence-transformers":
        model_name = os.getenv("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
        repo_id = model_name if "/" in model_name else f"sentence-transformers/{model_name}"
        cache = _huggingface_model_cache(repo_id)
        return {
            "identifier": model_name,
            "source": f"huggingface:{repo_id}",
            "local_path": cache["local_path"],
            "revision": cache["revision"],
        }
    if name == "ollama":
        return {
            "identifier": os.getenv("OLLAMA_MODEL", "nomic-embed-text"),
            "source": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "local_path": None,
            "revision": None,
        }
    return None


def _huggingface_model_cache(repo_id: str) -> dict[str, str | None]:
    explicit_cache = os.getenv("HUGGINGFACE_HUB_CACHE")
    if explicit_cache:
        root = Path(explicit_cache)
    else:
        hf_home = os.getenv("HF_HOME")
        root = Path(hf_home) / "hub" if hf_home else Path.home() / ".cache" / "huggingface" / "hub"

    repo_dir = root / _hf_repo_dir(repo_id)
    if not repo_dir.exists():
        return {"local_path": None, "revision": None}

    revision = None
    ref_path = repo_dir / "refs" / "main"
    if ref_path.is_file():
        revision = ref_path.read_text(encoding="utf-8").strip() or None

    snapshot_path = None
    snapshots_dir = repo_dir / "snapshots"
    if revision:
        candidate = snapshots_dir / revision
        if candidate.exists():
            snapshot_path = candidate
    if snapshot_path is None and snapshots_dir.is_dir():
        try:
            snapshot_path = sorted(snapshots_dir.iterdir())[-1]
        except IndexError:
            snapshot_path = None

    return {
        "local_path": str(snapshot_path) if snapshot_path else str(repo_dir),
        "revision": revision or (snapshot_path.name if snapshot_path else None),
    }


def _hf_repo_dir(repo_id: str) -> str:
    namespace, name = repo_id.split("/", 1)
    return f"models--{namespace}--{name}"
