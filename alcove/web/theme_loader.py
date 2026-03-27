"""Theme plugin resolution for the web UI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

from alcove.plugins import discover_themes

from . import TEMPLATES_DIR


@dataclass(frozen=True)
class ResolvedTheme:
    """Runtime theme configuration."""

    name: str
    template_dirs: list[str]
    static_dir: str | None
    plugin_loaded: bool


def _coerce_path(value: Any) -> Path | None:
    """Best-effort convert arbitrary theme config values into paths."""
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, (str, bytes, PathLike)):
        return Path(value)
    return None


def _extract_theme_paths(spec: Any) -> tuple[Path | None, Path | None]:
    """Extract template/static directories from a theme spec object."""
    provider = spec() if callable(spec) else spec

    if isinstance(provider, dict):
        t = provider.get("templates_dir") or provider.get("templates")
        s = provider.get("static_dir") or provider.get("static")
        return _coerce_path(t), _coerce_path(s)

    if isinstance(provider, (str, bytes, PathLike, Path)):
        return _coerce_path(provider), None

    templates_dir = (
        getattr(provider, "templates_dir", None)
        or getattr(provider, "TEMPLATES_DIR", None)
    )
    static_dir = (
        getattr(provider, "static_dir", None)
        or getattr(provider, "STATIC_DIR", None)
    )
    return _coerce_path(templates_dir), _coerce_path(static_dir)


def _theme_name() -> str:
    """Resolve desired theme name from env."""
    raw = os.getenv("ALCOVE_THEME", "default").strip()
    return raw or "default"


def resolve_theme() -> ResolvedTheme:
    """Resolve template/static directories for the active theme."""
    selected = _theme_name()
    base_templates = [str(TEMPLATES_DIR)]

    if selected == "default":
        return ResolvedTheme(
            name="default",
            template_dirs=base_templates,
            static_dir=None,
            plugin_loaded=False,
        )

    discovered = discover_themes()
    provider = discovered.get(selected)
    if provider is None:
        return ResolvedTheme(
            name="default",
            template_dirs=base_templates,
            static_dir=None,
            plugin_loaded=False,
        )

    theme_templates, theme_static = _extract_theme_paths(provider)
    if theme_templates is None or not theme_templates.is_dir():
        return ResolvedTheme(
            name="default",
            template_dirs=base_templates,
            static_dir=None,
            plugin_loaded=False,
        )

    static_dir = None
    if theme_static is not None and theme_static.is_dir():
        static_dir = str(theme_static)

    return ResolvedTheme(
        name=selected,
        template_dirs=[str(theme_templates), *base_templates],
        static_dir=static_dir,
        plugin_loaded=True,
    )
