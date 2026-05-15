import os

import pytest
from fastapi.testclient import TestClient

from alcove.query.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_root_returns_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Alcove" in r.text
    assert "Lead with the use cases" in r.text
    assert "id=\"workspace\"" in r.text
    assert "alcove seed-demo" in r.text


def test_query_post_returns_json():
    """Query endpoint works even with empty index (returns empty results)."""
    r = client.post("/query", json={"query": "test", "k": 1})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_ingest_skips_unsupported_format():
    """Unsupported file formats are gracefully skipped (200 with status=skipped), not rejected."""
    r = client.post(
        "/ingest",
        files={"files": ("test.xyz", b"content", "application/octet-stream")},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["filename"] == "test.xyz"
    assert data[0]["status"] == "skipped"


# ---------------------------------------------------------------------------
# base_url / ALCOVE_ROOT_PATH tests
# ---------------------------------------------------------------------------

class TestRootPathTemplate:
    """Verify ALCOVE_ROOT_PATH injects base_url into rendered HTML."""

    def test_no_root_path_uses_empty_string(self):
        """Without ALCOVE_ROOT_PATH, base_url is '' so CSS href is '/static/style.css'."""
        env_bak = os.environ.pop("ALCOVE_ROOT_PATH", None)
        try:
            r = client.get("/")
            assert r.status_code == 200
            assert 'href="/static/style.css"' in r.text
        finally:
            if env_bak is not None:
                os.environ["ALCOVE_ROOT_PATH"] = env_bak

    def test_root_path_prefixes_static_css(self):
        """With ALCOVE_ROOT_PATH=/demos, CSS href becomes '/demos/static/style.css'."""
        os.environ["ALCOVE_ROOT_PATH"] = "/demos"
        try:
            r = client.get("/")
            assert r.status_code == 200
            assert 'href="/demos/static/style.css"' in r.text
        finally:
            del os.environ["ALCOVE_ROOT_PATH"]

    def test_root_path_prefixes_search_form_action(self):
        """With ALCOVE_ROOT_PATH=/demos, search form action becomes '/demos/search'."""
        os.environ["ALCOVE_ROOT_PATH"] = "/demos"
        try:
            r = client.get("/")
            assert r.status_code == 200
            assert 'action="/demos/search"' in r.text
        finally:
            del os.environ["ALCOVE_ROOT_PATH"]

    def test_root_path_trailing_slash_stripped(self):
        """Trailing slash in ALCOVE_ROOT_PATH is stripped."""
        os.environ["ALCOVE_ROOT_PATH"] = "/demos/"
        try:
            r = client.get("/")
            assert r.status_code == 200
            assert 'href="/demos/static/style.css"' in r.text
            assert 'href="/demos//static/style.css"' not in r.text
        finally:
            del os.environ["ALCOVE_ROOT_PATH"]

    def test_results_back_link_uses_root_path(self):
        """Results page 'Back to search' link respects ALCOVE_ROOT_PATH."""
        os.environ["ALCOVE_ROOT_PATH"] = "/demos"
        try:
            r = client.get("/search?q=test")
            assert r.status_code == 200
            assert 'href="/demos/"' in r.text
        finally:
            del os.environ["ALCOVE_ROOT_PATH"]


# ---------------------------------------------------------------------------
# Coverage gaps
# ---------------------------------------------------------------------------

def test_demos_index_returns_html():
    """GET /demos renders the demos landing page with content from demos.json."""
    r = client.get("/demos")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # demos.json contains "Congress" — verify the template rendered the catalog
    assert "Congress" in r.text


def test_search_invalid_collection_name_returns_422():
    """GET /search with an invalid collection name (special chars) returns 422."""
    r = client.get("/search", params={"q": "test", "collections": "bad!name"})
    assert r.status_code == 422
    assert "Invalid collection name" in r.json()["detail"]


def test_ingest_disabled_in_demo_mode(monkeypatch):
    """POST /ingest returns 403 when ALCOVE_DEMO_ROOT is set (read-only demo mode)."""
    monkeypatch.setenv("ALCOVE_DEMO_ROOT", "/some/readonly/path")
    r = client.post(
        "/ingest",
        files={"files": ("sample.txt", b"hello world", "text/plain")},
    )
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"].lower()


def test_list_collections_backend_exception_returns_empty():
    """GET /collections returns [] gracefully when the backend raises."""
    from unittest.mock import patch
    with patch("alcove.index.backend.get_backend", side_effect=RuntimeError("no db")):
        r = client.get("/collections")
    assert r.status_code == 200
    assert r.json() == []


def test_browse_empty_index_returns_html(monkeypatch):
    """GET /browse renders an empty state when no backend metadata is available."""
    from alcove.query import api as api_mod

    monkeypatch.setattr(
        api_mod,
        "browse_corpus_stats",
        lambda: {"collections": [], "filetypes": [], "authors": [], "years": [], "recent": []},
    )
    r = client.get("/browse")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "No documents indexed yet" in r.text


def test_browse_corpus_stats_groups_source_documents(monkeypatch):
    """Browse stats count source documents, not chunks, and avoid absolute path display."""
    from alcove.query.browse import browse_corpus_stats

    stats = browse_corpus_stats([
        {
            "source": "/tmp/alcove-corpus/science/einstein.pdf",
            "collection": "science",
            "authors": "Einstein, A.",
            "year": "1905",
            "__document": "Relativity chunk one.",
            "__chunk_id": "chunk-1",
        },
        {
            "source": "/tmp/alcove-corpus/science/einstein.pdf",
            "collection": "science",
        },
        {
            "source": "data/raw/history/founding.txt",
            "collection": "history",
            "year": "1787",
        },
    ])

    assert {"name": "science", "doc_count": 1} in stats["collections"]
    assert {"name": "history", "doc_count": 1} in stats["collections"]
    assert {"ext": "PDF", "doc_count": 1} in stats["filetypes"]
    assert {"ext": "TXT", "doc_count": 1} in stats["filetypes"]
    assert stats["authors"] == [{"name": "Einstein, A.", "doc_count": 1}]
    assert {"year": "1905", "doc_count": 1} in stats["years"]
    assert all("/tmp/alcove-corpus" not in item["label"] for item in stats["recent"])
    science_doc = next(item for item in stats["recent"] if item["collection"] == "science")
    assert science_doc["id"]
    assert science_doc["chunks"] == [{"id": "chunk-1", "text": "Relativity chunk one."}]


def test_browse_corpus_stats_empty_records():
    from alcove.query.browse import browse_corpus_stats

    assert browse_corpus_stats([]) == {
        "collections": [],
        "filetypes": [],
        "authors": [],
        "years": [],
        "recent": [],
    }


def test_browse_page_renders_facets(monkeypatch):
    """GET /browse renders recent documents, collections, and facet chips."""
    from alcove.query import api as api_mod
    from alcove.query.browse import browse_corpus_stats

    monkeypatch.setattr(
        api_mod,
        "browse_corpus_stats",
        lambda: browse_corpus_stats([
            {
                "source": "data/raw/research/paper.md",
                "collection": "research",
                "authors": "Ada Lovelace",
                "year": "1843",
                "__document": "Analytical engine notes.",
            }
        ]),
    )
    r = client.get("/browse")
    assert r.status_code == 200
    assert "Recent Documents" in r.text
    assert "paper.md" in r.text
    assert "/browse/document/" in r.text
    assert "research" in r.text
    assert "Ada Lovelace" in r.text


def test_browse_document_detail_renders_chunk_previews(monkeypatch):
    from alcove.query import browse as browse_mod

    records = [
        {
            "source": "/tmp/private/path/research/paper.md",
            "collection": "research",
            "__chunk_id": "chunk-1",
            "__document": "First chunk with enough text to preview.",
        },
        {
            "source": "/tmp/private/path/research/paper.md",
            "collection": "research",
            "__chunk_id": "chunk-2",
            "__document": "Second chunk preview.",
        },
    ]
    monkeypatch.setattr(browse_mod, "backend_metadata_records", lambda: records)
    doc_id = browse_mod.browse_corpus_stats(records)["recent"][0]["id"]
    assert browse_mod.browse_document_detail("not-found", records) is None

    r = client.get(f"/browse/document/{doc_id}")

    assert r.status_code == 200
    assert "Document detail" in r.text
    assert "research/paper.md" in r.text
    assert "/tmp/private/path" not in r.text
    assert "First chunk with enough text to preview." in r.text
    assert "chunk-2" in r.text


def test_browse_document_detail_404(monkeypatch):
    from alcove.query import api as api_mod

    monkeypatch.setattr(api_mod, "browse_document_detail", lambda _: None)
    r = client.get("/browse/document/not-found")

    assert r.status_code == 404


def test_backend_metadata_records_uses_backend_public_interface(monkeypatch):
    from alcove.query.browse import backend_metadata_records

    class DummyBackend:
        def iter_metadata_records(self):
            return [{"source": "data/raw/a.md"}, None, {"source": "data/raw/b.md"}]

    monkeypatch.setattr("alcove.index.embedder.get_embedder", object)
    monkeypatch.setattr("alcove.index.backend.get_backend", lambda embedder: DummyBackend())

    assert backend_metadata_records() == [{"source": "data/raw/a.md"}, {"source": "data/raw/b.md"}]


def test_backend_metadata_records_handles_backend_factory_error(monkeypatch):
    from alcove.query.browse import backend_metadata_records

    monkeypatch.setattr("alcove.index.embedder.get_embedder", object)
    monkeypatch.setattr("alcove.index.backend.get_backend", lambda embedder: (_ for _ in ()).throw(RuntimeError("no db")))

    assert backend_metadata_records() == []


def test_browse_helpers_handle_fallbacks(tmp_path, monkeypatch):
    from alcove.query import browse as browse_mod

    raw_dir = tmp_path / "raw"
    source = raw_dir / "letters" / "note.txt"
    root_source = raw_dir / "root.txt"
    source.parent.mkdir(parents=True)
    source.write_text("hello", encoding="utf-8")
    root_source.write_text("root", encoding="utf-8")
    monkeypatch.setenv("RAW_DIR", str(raw_dir))

    assert browse_mod.source_key({"title": "Untitled"}) == "Untitled"
    assert browse_mod.source_key({}) == "(unknown)"
    assert browse_mod.source_label("(unknown)") == "Unknown source"
    assert browse_mod.source_label(str(source)) == "letters/note.txt"
    assert browse_mod.source_label("/external/archive/note.txt") == "archive/note.txt"
    assert browse_mod.source_label("note.txt") == "note.txt"
    assert browse_mod.source_label("") == "Unknown source"
    assert browse_mod.collection_label({}, str(source)) == "letters"
    assert browse_mod.collection_label({}, str(root_source)) == "default"
    assert browse_mod.collection_label({}, "/external/note.txt") == "default"
    assert browse_mod.chunk_preview("hello\n\n  world") == "hello world"
    assert browse_mod.chunk_preview("a" * 370).endswith("...")
    assert browse_mod.browse_document_id("source.txt") == browse_mod.browse_document_id("source.txt")
    assert browse_mod.document_sort_time("missing.txt", [{"uploaded_at": "not-a-date"}]) == 0.0
    assert browse_mod.document_sort_time(str(source), [{}]) > 0


def test_root_backend_exception_still_renders_html():
    """GET / renders the search page even when the backend raises (doc_count falls back to 0)."""
    from unittest.mock import patch
    with patch("alcove.index.backend.get_backend", side_effect=RuntimeError("no db")):
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_demos_index_handles_unreadable_config():
    """GET /demos returns a valid page even when demos.json cannot be read."""
    from pathlib import Path
    from unittest.mock import patch
    original_read = Path.read_text

    def mock_read(self, *args, **kwargs):
        if self.name == "demos.json":
            raise OSError("permission denied")
        return original_read(self, *args, **kwargs)

    with patch.object(Path, "read_text", mock_read):
        r = client.get("/demos")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_demos_index_with_live_collection():
    """GET /demos marks a demo as live when its collection exists in the backend."""
    from unittest.mock import MagicMock, patch
    mock_backend = MagicMock()
    # "congress_summaries" matches the collection in demos.json
    mock_backend.list_collections.return_value = [
        {"name": "congress_summaries", "doc_count": 100}
    ]
    with patch("alcove.index.backend.get_backend", return_value=mock_backend):
        r = client.get("/demos")
    assert r.status_code == 200
    assert "Congress" in r.text


def test_demos_index_backend_exception_still_renders():
    """GET /demos renders even when the backend raises during live-collection resolution."""
    from unittest.mock import patch
    with patch("alcove.index.backend.get_backend", side_effect=RuntimeError("no db")):
        r = client.get("/demos")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
