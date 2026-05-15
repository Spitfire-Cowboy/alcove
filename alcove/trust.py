from __future__ import annotations

import json
import os
import platform
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from alcove import __version__
from alcove.provenance import load_index_provenance
from alcove.plugins import list_plugins
from alcove.plugins import BACKENDS_GROUP, EMBEDDERS_GROUP, entry_points


_PACKAGE_GROUPS: list[tuple[str, str]] = [
    ("chromadb", "vector_backend"),
    ("zvec", "vector_backend"),
    ("sentence-transformers", "embedder"),
    ("transformers", "embedder_runtime"),
    ("torch", "embedder_runtime"),
    ("pypdf", "parser"),
    ("beautifulsoup4", "parser"),
    ("ebooklib", "parser"),
    ("python-docx", "parser"),
    ("python-pptx", "parser"),
    ("fastapi", "web"),
    ("uvicorn", "web"),
    ("python-multipart", "web"),
    ("rank-bm25", "search"),
    ("cryptography", "security"),
]

_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib", ".dll"}


def build_trust_report() -> dict[str, Any]:
    package_details = _collect_package_details()
    return {
        "alcove": _alcove_info(),
        "python": _python_info(),
        "runtime": _runtime_info(),
        "backend": _backend_info(),
        "embedder": _embedder_info(),
        "index_provenance": load_index_provenance(),
        "plugins": {
            "allowlist": os.getenv("ALCOVE_PLUGIN_ALLOWLIST", ""),
            "installed": list_plugins(),
        },
        "packages": {
            "native": [pkg for pkg in package_details if pkg["installed"] and pkg["has_native_extensions"]],
            "pure_python": [pkg for pkg in package_details if pkg["installed"] and not pkg["has_native_extensions"]],
            "missing": [pkg for pkg in package_details if not pkg["installed"]],
        },
    }


def print_trust_report(report: dict[str, Any]) -> None:
    python_info = report["python"]
    alcove_info = report["alcove"]
    runtime = report["runtime"]
    backend = report["backend"]
    embedder = report["embedder"]

    print("Trust Doctor")
    print()
    print("Runtime")
    print(f"  python executable:   {python_info['executable']}")
    print(f"  python version:      {python_info['version']}")
    print(f"  platform:            {python_info['platform']}")
    print(f"  virtualenv:          {_format_virtualenv(python_info)}")
    print(f"  alcove version:      {alcove_info['version']}")
    print(f"  alcove install:      {alcove_info['install_source']}")
    print(f"  alcove location:     {alcove_info['module_path']}")
    print()
    print("Configuration")
    print(f"  config path:         {runtime['config_path']}")
    print(f"  private mode:        {runtime['private_mode']}")
    print(f"  backend:             {backend['name']}")
    print(f"  backend impl:        {backend['implementation']}")
    print(f"  storage path:        {backend['storage_path']}")
    print(f"  telemetry posture:   {backend['telemetry_posture']}")
    print(f"  network posture:     {backend['network_posture']}")
    print(f"  embedder:            {embedder['name']}")
    print(f"  embedder impl:       {embedder['implementation']}")
    print(f"  embedder source:     {embedder['source']}")
    print(f"  embedder network:    {embedder['network_posture']}")
    model = embedder.get("model")
    if model:
        print(f"  model id:            {model['identifier']}")
        print(f"  model source:        {model['source']}")
        print(f"  model cache path:    {model['local_path'] or '(not found locally)'}")
        print(f"  model revision:      {model['revision'] or '(unavailable)'}")
    provenance = report.get("index_provenance", {})
    collections = provenance.get("collections", {})
    if collections:
        print()
        print("Index provenance")
        for name in sorted(collections):
            record = collections[name]
            embedder_record = record.get("embedder", {})
            model_record = embedder_record.get("model", {})
            print(f"  collection:          {name}")
            print(f"  indexed at:          {record.get('indexed_at', '(unknown)')}")
            print(f"  chunk count:         {record.get('chunk_count', '(unknown)')}")
            print(f"  embedder dimension:  {embedder_record.get('embedding_dimension', '(unknown)')}")
            if model_record:
                print(f"  model receipt:       {model_record.get('identifier')} @ {model_record.get('revision') or '(unavailable)'}")
    plugins = report.get("plugins", {})
    installed_plugins = plugins.get("installed", [])
    print()
    print("Plugins")
    print(f"  allowlist:           {plugins.get('allowlist') or '(not set)'}")
    if not installed_plugins:
        print("  installed:           none")
    else:
        for plugin in installed_plugins:
            version = plugin.get("distribution_version") or "(version unknown)"
            print(f"  {plugin['type']:18s} {plugin['name']:16s} {plugin['module']}  {version}")
    print()
    _print_package_section("Native extension packages", report["packages"]["native"])
    print()
    _print_package_section("Pure Python packages", report["packages"]["pure_python"])
    missing = report["packages"]["missing"]
    if missing:
        print()
        _print_package_section("Not installed", missing)


def _format_virtualenv(python_info: dict[str, Any]) -> str:
    if not python_info["in_virtualenv"]:
        return "no"
    prefix = python_info.get("prefix") or "(unknown)"
    return f"yes ({prefix})"


def _print_package_section(title: str, packages: list[dict[str, Any]]) -> None:
    print(title)
    if not packages:
        print("  (none)")
        return
    for package in packages:
        status = package["version"] if package["installed"] else "missing"
        print(f"  {package['name']:20s} {status:12s} {package['role']}")


def _python_info() -> dict[str, Any]:
    return {
        "executable": sys.executable,
        "version": platform.python_version(),
        "version_info": list(sys.version_info[:3]),
        "platform": platform.platform(),
        "prefix": sys.prefix,
        "base_prefix": getattr(sys, "base_prefix", sys.prefix),
        "in_virtualenv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
    }


def _alcove_info() -> dict[str, Any]:
    dist_name = "alcove-search"
    dist = _safe_distribution(dist_name)
    module_path = str(Path(__file__).resolve().parent)
    info = {
        "name": dist_name,
        "version": __version__,
        "module_path": module_path,
        "install_source": "unknown",
        "distribution_path": None,
    }
    if dist is None:
        return info
    info["distribution_path"] = str(dist.locate_file(""))
    info["install_source"] = _detect_install_source(dist)
    return info


def _runtime_info() -> dict[str, Any]:
    from alcove.config import load_config

    config_path = Path(os.getenv("ALCOVE_CONFIG_PATH", "alcove.toml"))
    config = load_config()
    return {
        "config_path": str(config_path),
        "config_exists": config_path.is_file(),
        "private_mode": config.private_mode,
        "deployment_mode": config.deployment.mode,
        "instance_name": config.deployment.instance_name,
    }


def _backend_info() -> dict[str, Any]:
    backend_name = os.getenv("VECTOR_BACKEND", "chromadb").lower()
    implementation = _builtin_backend_impl(backend_name) or _plugin_target(BACKENDS_GROUP, backend_name)
    if backend_name == "zvec":
        storage_path = os.getenv("ZVEC_PATH", "./data/zvec")
    else:
        storage_path = os.getenv("CHROMA_PATH", "./data/chroma")

    telemetry_posture = "unknown"
    if backend_name == "chromadb":
        telemetry_posture = "disabled (ANONYMIZED_TELEMETRY=False)"
    elif os.getenv("ANONYMIZED_TELEMETRY", "").lower() in {"0", "false", "no"}:
        telemetry_posture = "disabled"

    return {
        "name": backend_name,
        "implementation": implementation or "(unknown)",
        "storage_path": storage_path,
        "telemetry_posture": telemetry_posture,
        "network_posture": "local disk only by default",
    }


def _embedder_info() -> dict[str, Any]:
    embedder_name = os.getenv("EMBEDDER", "hash")
    implementation = _builtin_embedder_impl(embedder_name) or _plugin_target(EMBEDDERS_GROUP, embedder_name)
    info: dict[str, Any] = {
        "name": embedder_name,
        "implementation": implementation or "(unknown)",
        "source": "builtin" if _builtin_embedder_impl(embedder_name) else "plugin",
        "network_posture": _embedder_network_posture(embedder_name),
    }
    model = _embedder_model_info(embedder_name)
    if model is not None:
        info["model"] = model
    return info


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


def _embedder_network_posture(name: str) -> str:
    if name == "hash":
        return "offline"
    if name == "sentence-transformers":
        return "offline after optional one-time model download"
    if name == "ollama":
        return "local HTTP to Ollama by default; remote if OLLAMA_BASE_URL points elsewhere"
    return "depends on plugin implementation"


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
    root = Path(
        os.getenv("HUGGINGFACE_HUB_CACHE")
        or os.getenv("HF_HOME", "") and str(Path(os.getenv("HF_HOME", "")) / "hub")
        or str(Path.home() / ".cache" / "huggingface" / "hub")
    )
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


def _collect_package_details() -> list[dict[str, Any]]:
    seen: set[str] = set()
    details: list[dict[str, Any]] = []
    for package_name, role in _PACKAGE_GROUPS:
        normalized = package_name.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        details.append(_package_detail(package_name, role))
    return details


def _package_detail(package_name: str, role: str) -> dict[str, Any]:
    dist = _safe_distribution(package_name)
    if dist is None:
        return {
            "name": package_name,
            "role": role,
            "installed": False,
            "version": None,
            "location": None,
            "has_native_extensions": False,
        }

    return {
        "name": package_name,
        "role": role,
        "installed": True,
        "version": dist.version,
        "location": str(dist.locate_file("")),
        "has_native_extensions": _distribution_has_native_extensions(dist),
    }


def _distribution_has_native_extensions(dist: Any) -> bool:
    files = getattr(dist, "files", None) or []
    for file in files:
        suffix = Path(str(file)).suffix.lower()
        if suffix in _NATIVE_SUFFIXES:
            return True
    return False


def _safe_distribution(name: str) -> Any | None:
    try:
        return importlib_metadata.distribution(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _detect_install_source(dist: Any) -> str:
    direct_url = None
    try:
        direct_url_text = dist.read_text("direct_url.json")
    except Exception:
        direct_url_text = None
    if direct_url_text:
        try:
            direct_url = json.loads(direct_url_text)
        except json.JSONDecodeError:
            direct_url = None

    if isinstance(direct_url, dict):
        if direct_url.get("dir_info", {}).get("editable"):
            return "editable local checkout"
        if "vcs_info" in direct_url and direct_url.get("url"):
            vcs = direct_url["vcs_info"].get("vcs", "vcs")
            return f"{vcs} checkout ({direct_url['url']})"
        if direct_url.get("url", "").startswith("file://"):
            return "local file install"
        if direct_url.get("url"):
            return direct_url["url"]

    location = str(dist.locate_file(""))
    site_packages_markers = ("site-packages", "dist-packages")
    if any(marker in location for marker in site_packages_markers):
        return "installed package"
    return "local source tree"
