from __future__ import annotations

from fastapi.testclient import TestClient


_FAKE_PLUGINS = [
    {"name": "pdf", "type": "extractor", "module": "alcove_pdf:extract", "group": "alcove.extractors"},
    {"name": "chroma", "type": "backend", "module": "alcove_chroma:Backend", "group": "alcove.backends"},
    {"name": "openai", "type": "embedder", "module": "alcove_openai:Embedder", "group": "alcove.embedders"},
]

_FAKE_DETAIL = {
    "name": "pdf",
    "type": "extractor",
    "module": "alcove_pdf:extract",
    "group": "alcove.extractors",
    "description": "PDF text extractor",
    "version": "1.2.3",
    "package": "alcove-pdf",
    "activation": "Install the package and restart Alcove.",
}


def _make_client(monkeypatch, *, plugins=None, detail=None):
    import alcove.query.api as api_mod

    monkeypatch.setattr(api_mod, "list_plugins", lambda: _FAKE_PLUGINS if plugins is None else plugins)
    monkeypatch.setattr(api_mod, "get_plugin_detail", lambda name: _FAKE_DETAIL if detail and name == detail["name"] else None)
    return TestClient(api_mod.app)


def test_api_plugins_detail_returns_404_for_unknown_plugin(monkeypatch):
    client = _make_client(monkeypatch, detail=None)
    response = client.get("/api/plugins/missing")
    assert response.status_code == 404
    assert "error" in response.json()


def test_api_plugins_list_returns_all_plugins(monkeypatch):
    client = _make_client(monkeypatch, detail=None)
    response = client.get("/api/plugins")
    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_api_plugins_list_filters(monkeypatch):
    client = _make_client(monkeypatch, detail=None)
    by_type = client.get("/api/plugins?type=backend")
    by_query = client.get("/api/plugins?q=openai")
    assert by_type.status_code == 200
    assert by_type.json()["plugins"][0]["name"] == "chroma"
    assert by_query.status_code == 200
    assert by_query.json()["plugins"][0]["name"] == "openai"


def test_api_plugins_detail_returns_enriched_plugin(monkeypatch):
    client = _make_client(monkeypatch, detail=_FAKE_DETAIL)
    response = client.get("/api/plugins/pdf")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "pdf"
    assert data["description"] == "PDF text extractor"
    assert data["version"] == "1.2.3"


def test_plugins_page_lists_plugins(monkeypatch):
    client = _make_client(monkeypatch, detail=None)
    response = client.get("/plugins")
    assert response.status_code == 200
    assert "Plugins" in response.text
    assert "pdf" in response.text
    assert "chroma" in response.text
    assert "openai" in response.text
    assert 'href="/plugins"' in response.text


def test_plugins_page_filters_by_type_and_query(monkeypatch):
    client = _make_client(monkeypatch, detail=None)
    by_type = client.get("/plugins?type=backend")
    by_query = client.get("/plugins?q=openai")
    assert by_type.status_code == 200
    assert "chroma" in by_type.text
    assert "pdf" not in by_type.text
    assert by_query.status_code == 200
    assert "openai" in by_query.text
    assert "chroma" not in by_query.text


def test_plugins_page_empty_state(monkeypatch):
    client = _make_client(monkeypatch, plugins=[], detail=None)
    response = client.get("/plugins")
    assert response.status_code == 200
    assert "No plugins found" in response.text


def test_plugin_detail_page_renders(monkeypatch):
    client = _make_client(monkeypatch, detail=_FAKE_DETAIL)
    response = client.get("/plugins/pdf")
    assert response.status_code == 200
    assert "PDF text extractor" in response.text
    assert "alcove_pdf:extract" in response.text
    assert "Activation" in response.text


def test_plugin_detail_page_404_renders_listing(monkeypatch):
    client = _make_client(monkeypatch, detail=None)
    response = client.get("/plugins/missing")
    assert response.status_code == 404
    assert "Plugin not found" in response.text


def test_get_plugin_detail_uses_package_metadata(monkeypatch):
    from alcove import plugins as plugins_mod

    class FakeDist:
        metadata = {"Summary": "A test plugin", "Version": "0.1.0", "Name": "alcove-test"}

    class FakeEP:
        name = "testplugin"
        value = "alcove_test:run"
        dist = FakeDist()

    monkeypatch.setattr(
        plugins_mod,
        "entry_points",
        lambda *, group: [FakeEP()] if group == plugins_mod.EXTRACTORS_GROUP else [],
    )

    detail = plugins_mod.get_plugin_detail("testplugin")
    assert detail is not None
    assert detail["package"] == "alcove-test"
    assert detail["version"] == "0.1.0"
    assert detail["description"] == "A test plugin"


def test_get_plugin_detail_handles_missing_distribution(monkeypatch):
    from alcove import plugins as plugins_mod

    class FakeEP:
        name = "nodist"
        value = "nodist_plugin:run"
        dist = None

    monkeypatch.setattr(
        plugins_mod,
        "entry_points",
        lambda *, group: [FakeEP()] if group == plugins_mod.BACKENDS_GROUP else [],
    )

    detail = plugins_mod.get_plugin_detail("nodist")
    assert detail is not None
    assert detail["description"] == ""
    assert detail["version"] == ""
    assert detail["package"] == ""
