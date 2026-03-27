"""Tests for runtime web theme plugin loading and fallback."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from alcove.web import TEMPLATES_DIR
import alcove.web.theme_loader as theme_loader


def _reload_api_module():
    import alcove.query.api as api_module

    return importlib.reload(api_module)


def test_default_theme_uses_builtin_templates(monkeypatch):
    monkeypatch.delenv("ALCOVE_THEME", raising=False)
    monkeypatch.setattr(theme_loader, "discover_themes", lambda: {})

    api = _reload_api_module()

    assert api.ACTIVE_THEME.name == "default"
    assert api.ACTIVE_THEME.plugin_loaded is False
    assert str(TEMPLATES_DIR) in api.templates.env.loader.searchpath
    assert not any(getattr(route, "path", None) == "/theme-static" for route in api.app.routes)


def test_theme_plugin_overrides_template_and_falls_back(tmp_path, monkeypatch):
    theme_templates = tmp_path / "templates"
    theme_static = tmp_path / "static"
    theme_templates.mkdir()
    theme_static.mkdir()
    (theme_templates / "search.html").write_text("Theme Search Override", encoding="utf-8")
    (theme_static / "theme.css").write_text("body { color: #123; }", encoding="utf-8")

    monkeypatch.setenv("ALCOVE_THEME", "congress")
    monkeypatch.setattr(
        theme_loader,
        "discover_themes",
        lambda: {
            "congress": {
                "templates_dir": str(theme_templates),
                "static_dir": str(theme_static),
            }
        },
    )

    api = _reload_api_module()
    client = TestClient(api.app)

    # Theme search template wins over built-in.
    root = client.get("/")
    assert root.status_code == 200
    assert "Theme Search Override" in root.text

    # Built-in results template is still used via fallback search path.
    with patch.object(
        api,
        "_dispatch_query",
        return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]},
    ):
        res = client.get("/search", params={"q": "alpha"})
    assert res.status_code == 200
    assert "No results found" in res.text

    # Theme static mount is available when plugin provides a static directory.
    static = client.get("/theme-static/theme.css")
    assert static.status_code == 200
    assert "color: #123" in static.text


def test_unknown_theme_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("ALCOVE_THEME", "does-not-exist")
    monkeypatch.setattr(theme_loader, "discover_themes", lambda: {})

    api = _reload_api_module()

    assert api.ACTIVE_THEME.name == "default"
    assert api.ACTIVE_THEME.plugin_loaded is False
    assert str(TEMPLATES_DIR) in api.templates.env.loader.searchpath
    assert not any(getattr(route, "path", None) == "/theme-static" for route in api.app.routes)
