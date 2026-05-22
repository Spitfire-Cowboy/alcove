"""Plugin discovery via Python entry points."""

from __future__ import annotations

import os
import sys
from importlib import metadata as importlib_metadata
from typing import Dict, List

if sys.version_info >= (3, 12):
    from importlib.metadata import entry_points
else:
    # 3.9-3.11: entry_points() returns a dict (3.9) or SelectableGroups.
    # The `group` kwarg works from 3.9.17 / 3.10+ but for safety we
    # filter manually.
    from importlib.metadata import entry_points as _ep

    def entry_points(*, group: str):  # type: ignore[misc]
        all_eps = _ep()
        if isinstance(all_eps, dict):
            return all_eps.get(group, [])
        return all_eps.select(group=group)


# -- Well-known entry point groups ------------------------------------------

EXTRACTORS_GROUP = "alcove.extractors"
BACKENDS_GROUP = "alcove.backends"
EMBEDDERS_GROUP = "alcove.embedders"
ENRICHERS_GROUP = "alcove.enrichers"
_PLUGIN_GROUPS = [
    (EXTRACTORS_GROUP, "extractor"),
    (BACKENDS_GROUP, "backend"),
    (EMBEDDERS_GROUP, "embedder"),
    (ENRICHERS_GROUP, "enricher"),
]

_ACTIVATION_INSTRUCTIONS: Dict[str, str] = {
    "extractor": "Install the package and restart Alcove. Supported files are processed automatically during ingest.",
    "backend": "Set VECTOR_BACKEND to this plugin name, then restart Alcove to use this backend.",
    "embedder": "Set EMBEDDER to this plugin name, then restart Alcove to use this embedder.",
    "enricher": "Install the package and restart Alcove. Enrichers run automatically during ingest before indexing.",
}


def _allowed_tokens() -> set[str]:
    raw = os.getenv("ALCOVE_PLUGIN_ALLOWLIST", "")
    return {token.strip().lower() for token in raw.split(",") if token.strip()}


def _plugin_allowed(ep, tokens: set[str]) -> bool:
    module_path = ep.value.split(":", 1)[0]
    module_root = module_path.split(".", 1)[0].lower()
    package_root = module_root.replace("_", "-")
    return (
        ep.name.lower() in tokens
        or module_path.lower() in tokens
        or module_root in tokens
        or package_root in tokens
    )


def _entry_points_for(group: str):
    tokens = _allowed_tokens()
    discovered = entry_points(group=group)
    if not tokens:
        return discovered
    return [ep for ep in discovered if _plugin_allowed(ep, tokens)]


def _distribution_version(module_path: str) -> str | None:
    module_root = module_path.split(":", 1)[0].split(".", 1)[0].replace("_", "-")
    try:
        return importlib_metadata.version(module_root)
    except importlib_metadata.PackageNotFoundError:
        return None


def discover_extractors() -> Dict[str, callable]:
    """Return {".ext": callable} from installed plugins."""
    found = {}
    for ep in _entry_points_for(EXTRACTORS_GROUP):
        ext = f".{ep.name}" if not ep.name.startswith(".") else ep.name
        found[ext] = ep.load()
    return found


def discover_backends() -> Dict[str, type]:
    """Return {"name": BackendClass} from installed plugins."""
    return {ep.name: ep.load() for ep in _entry_points_for(BACKENDS_GROUP)}


def discover_embedders() -> Dict[str, type]:
    """Return {"name": EmbedderClass} from installed plugins."""
    return {ep.name: ep.load() for ep in _entry_points_for(EMBEDDERS_GROUP)}


def discover_enrichers() -> Dict[str, callable]:
    """Return {"name": callable} from installed plugins."""
    return {ep.name: ep.load() for ep in _entry_points_for(ENRICHERS_GROUP)}


def list_plugins() -> List[dict]:
    """List all discovered Alcove plugins across all groups."""
    plugins = []
    for group, label in _PLUGIN_GROUPS:
        for ep in _entry_points_for(group):
            plugins.append({
                "name": ep.name,
                "type": label,
                "module": ep.value,
                "group": group,
                "distribution_version": _distribution_version(ep.value),
            })
    return plugins


def _plugin_package_meta(ep) -> dict:
    result = {"description": "", "version": "", "package": ""}
    try:
        dist = getattr(ep, "dist", None)
        if dist is None:
            return result
        meta = dist.metadata
        result["description"] = meta.get("Summary", "") or ""
        result["version"] = meta.get("Version", "") or ""
        result["package"] = meta.get("Name", "") or ""
    except Exception:
        return result
    return result


def get_plugin_detail(name: str) -> dict | None:
    for group, label in _PLUGIN_GROUPS:
        for ep in _entry_points_for(group):
            if ep.name != name:
                continue
            pkg = _plugin_package_meta(ep)
            return {
                "name": ep.name,
                "type": label,
                "module": ep.value,
                "group": group,
                "description": pkg["description"],
                "version": pkg["version"],
                "package": pkg["package"],
                "activation": _ACTIVATION_INSTRUCTIONS.get(label, ""),
                "distribution_version": _distribution_version(ep.value),
            }
    return None
