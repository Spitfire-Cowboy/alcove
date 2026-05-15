"""Tests for plugin discovery system."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from alcove.plugins import (
    discover_extractors,
    discover_backends,
    discover_embedders,
    discover_enrichers,
    list_plugins,
)


def _make_entry_point(name, value, load_return=None):
    ep = MagicMock()
    ep.name = name
    ep.value = value
    ep.load.return_value = load_return or MagicMock()
    return ep


class TestDiscoverExtractors:
    def test_returns_empty_when_no_plugins(self):
        with patch("alcove.plugins.entry_points", return_value=[]):
            assert discover_extractors() == {}

    def test_discovers_extractor_plugin(self):
        fake_fn = lambda p: "extracted text"
        ep = _make_entry_point("docx", "alcove_docx:extract_docx", fake_fn)
        with patch("alcove.plugins.entry_points", return_value=[ep]):
            result = discover_extractors()
            assert ".docx" in result
            assert result[".docx"] is fake_fn

    def test_dot_prefix_not_doubled(self):
        ep = _make_entry_point(".html", "alcove_html:extract", MagicMock())
        with patch("alcove.plugins.entry_points", return_value=[ep]):
            result = discover_extractors()
            assert ".html" in result
            assert "..html" not in result


class TestDiscoverBackends:
    def test_returns_empty_when_no_plugins(self):
        with patch("alcove.plugins.entry_points", return_value=[]):
            assert discover_backends() == {}

    def test_discovers_backend_plugin(self):
        fake_cls = type("FakeBackend", (), {})
        ep = _make_entry_point("milvus", "alcove_milvus:MilvusBackend", fake_cls)
        with patch("alcove.plugins.entry_points", return_value=[ep]):
            result = discover_backends()
            assert "milvus" in result
            assert result["milvus"] is fake_cls


class TestDiscoverEmbedders:
    def test_returns_empty_when_no_plugins(self):
        with patch("alcove.plugins.entry_points", return_value=[]):
            assert discover_embedders() == {}

    def test_discovers_embedder_plugin(self):
        fake_cls = type("CohereEmbedder", (), {})
        ep = _make_entry_point("cohere", "alcove_cohere:CohereEmbedder", fake_cls)
        with patch("alcove.plugins.entry_points", return_value=[ep]):
            result = discover_embedders()
            assert "cohere" in result
            assert result["cohere"] is fake_cls

    def test_allowlist_filters_embedder_plugins(self, monkeypatch):
        fake_cls = type("CohereEmbedder", (), {})
        ep = _make_entry_point("cohere", "alcove_cohere:CohereEmbedder", fake_cls)
        monkeypatch.setenv("ALCOVE_PLUGIN_ALLOWLIST", "other-plugin")
        with patch("alcove.plugins.entry_points", return_value=[ep]):
            assert discover_embedders() == {}


class TestListPlugins:
    def test_empty_when_no_plugins(self):
        with patch("alcove.plugins.entry_points", return_value=[]):
            assert list_plugins() == []

    def test_lists_across_groups(self):
        ext_ep = _make_entry_point("docx", "alcove_docx:extract_docx")
        backend_ep = _make_entry_point("milvus", "alcove_milvus:Milvus")
        embedder_ep = _make_entry_point("cohere", "alcove_cohere:Cohere")

        def fake_entry_points(*, group):
            return {
                "alcove.extractors": [ext_ep],
                "alcove.backends": [backend_ep],
                "alcove.embedders": [embedder_ep],
            }.get(group, [])

        with patch("alcove.plugins.entry_points", side_effect=fake_entry_points):
            plugins = list_plugins()
            assert len(plugins) == 3
            types = {p["type"] for p in plugins}
            assert types == {"extractor", "backend", "embedder"}

    def test_list_plugins_includes_distribution_version(self):
        ext_ep = _make_entry_point("docx", "alcove_docx:extract_docx")

        with patch("alcove.plugins.entry_points", return_value=[ext_ep]):
            with patch("alcove.plugins.importlib_metadata.version", return_value="1.0.0"):
                plugins = list_plugins()

        assert plugins[0]["distribution_version"] == "1.0.0"


class TestDiscoverEnrichers:
    def test_returns_empty_when_no_plugins(self):
        with patch("alcove.plugins.entry_points", return_value=[]):
            assert discover_enrichers() == {}

    def test_discovers_enricher_plugin(self):
        fake_fn = lambda text, metadata: {"category": "memo"}
        ep = _make_entry_point("doctype", "alcove_doctype:enrich", fake_fn)
        with patch("alcove.plugins.entry_points", return_value=[ep]):
            result = discover_enrichers()
            assert "doctype" in result
            assert result["doctype"] is fake_fn


class TestPipelineUsesPlugins:
    def test_plugin_extractor_called_for_custom_extension(self, tmp_path):
        from alcove.ingest.pipeline import run

        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "test.xyz").write_text("hello from xyz plugin")
        out = tmp_path / "chunks.jsonl"

        fake_extractor = lambda p: p.read_text()
        with patch("alcove.ingest.pipeline.discover_extractors", return_value={".xyz": fake_extractor}):
            n = run(raw_dir=str(raw), out_file=str(out))

        assert n >= 1
        import json
        chunks = [json.loads(line) for line in out.read_text().strip().split("\n")]
        assert any("hello from xyz plugin" in c["chunk"] for c in chunks)


class TestBackendUsesPlugins:
    def test_plugin_backend_used_when_configured(self, monkeypatch):
        fake_instance = MagicMock()
        fake_cls = MagicMock(return_value=fake_instance)
        embedder = MagicMock()

        monkeypatch.setenv("VECTOR_BACKEND", "custom-db")
        with patch("alcove.plugins.discover_backends", return_value={"custom-db": fake_cls}):
            from alcove.index.backend import get_backend
            result = get_backend(embedder)

        fake_cls.assert_called_once_with(embedder)
        assert result is fake_instance


class TestEmbedderUsesPlugins:
    def test_plugin_embedder_used_when_configured(self, monkeypatch):
        fake_instance = MagicMock()
        fake_cls = MagicMock(return_value=fake_instance)

        monkeypatch.setenv("EMBEDDER", "custom-emb")
        with patch("alcove.plugins.discover_embedders", return_value={"custom-emb": fake_cls}):
            from alcove.index.embedder import get_embedder
            result = get_embedder()

        fake_cls.assert_called_once()
        assert result is fake_instance
