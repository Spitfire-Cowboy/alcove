"""Plugin discovery via Python entry points."""

from __future__ import annotations

import sys
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
_PLUGIN_GROUPS = [
    (EXTRACTORS_GROUP, "extractor"),
    (BACKENDS_GROUP, "backend"),
    (EMBEDDERS_GROUP, "embedder"),
]

_ACTIVATION_INSTRUCTIONS: Dict[str, str] = {
    "extractor": "Install the package and restart Alcove. Supported files are processed automatically during ingest.",
    "backend": "Set VECTOR_BACKEND to this plugin name, then restart Alcove to use this backend.",
    "embedder": "Set EMBEDDER to this plugin name, then restart Alcove to use this embedder.",
}


def discover_extractors() -> Dict[str, callable]:
    """Return {".ext": callable} from installed plugins."""
    found = {}
    for ep in entry_points(group=EXTRACTORS_GROUP):
        ext = f".{ep.name}" if not ep.name.startswith(".") else ep.name
        found[ext] = ep.load()
    return found


def discover_backends() -> Dict[str, type]:
    """Return {"name": BackendClass} from installed plugins."""
    return {ep.name: ep.load() for ep in entry_points(group=BACKENDS_GROUP)}


def discover_embedders() -> Dict[str, type]:
    """Return {"name": EmbedderClass} from installed plugins."""
    return {ep.name: ep.load() for ep in entry_points(group=EMBEDDERS_GROUP)}


def list_plugins() -> List[dict]:
    """List all discovered Alcove plugins across all groups."""
    plugins = []
    for group, label in _PLUGIN_GROUPS:
        for ep in entry_points(group=group):
            plugins.append({
                "name": ep.name,
                "type": label,
                "module": ep.value,
                "group": group,
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
        for ep in entry_points(group=group):
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
            }
    return None
