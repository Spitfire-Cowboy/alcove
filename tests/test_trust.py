from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


class FakeDist:
    def __init__(self, *, version="1.2.3", root="/tmp/site-packages/pkg", files=None, direct_url=None):
        self.version = version
        self._root = Path(root)
        self.files = files or []
        self._direct_url = direct_url

    def locate_file(self, path):
        return self._root / path

    def read_text(self, name):
        if name == "direct_url.json":
            return self._direct_url
        return None


def test_distribution_has_native_extensions():
    from alcove.trust import _distribution_has_native_extensions

    dist = FakeDist(files=["module/__init__.py", "module/native.so"])
    assert _distribution_has_native_extensions(dist) is True


def test_detect_install_source_editable():
    from alcove.trust import _detect_install_source

    dist = FakeDist(
        direct_url='{"url":"file:///repo","dir_info":{"editable":true}}',
        root="/tmp/project",
    )
    assert _detect_install_source(dist) == "editable local checkout"


def test_huggingface_model_cache_detects_snapshot(tmp_path, monkeypatch):
    from alcove.trust import _huggingface_model_cache

    repo_dir = tmp_path / "models--sentence-transformers--all-MiniLM-L6-v2"
    snapshot = repo_dir / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    refs = repo_dir / "refs"
    refs.mkdir(parents=True)
    (refs / "main").write_text("abc123\n", encoding="utf-8")
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path))

    result = _huggingface_model_cache("sentence-transformers/all-MiniLM-L6-v2")
    assert result["revision"] == "abc123"
    assert result["local_path"] == str(snapshot)


def test_build_trust_report_uses_offline_metadata(monkeypatch, tmp_path):
    from alcove import trust

    def fake_distribution(name):
        mapping = {
            "alcove-search": FakeDist(
                version="0.4.0",
                root="/workspace/site-packages/alcove-search",
                direct_url='{"url":"file:///workspace","dir_info":{"editable":true}}',
            ),
            "chromadb": FakeDist(version="1.0.0", files=["chromadb/native.so"]),
            "fastapi": FakeDist(version="0.115.0", files=["fastapi/__init__.py"]),
        }
        if name in mapping:
            return mapping[name]
        raise trust.importlib_metadata.PackageNotFoundError

    monkeypatch.setattr(trust.importlib_metadata, "distribution", fake_distribution)
    monkeypatch.setattr(trust, "entry_points", lambda *, group: [])
    monkeypatch.setattr(
        trust,
        "_runtime_info",
        lambda: {
            "config_path": str(tmp_path / "alcove.toml"),
            "config_exists": False,
            "private_mode": True,
            "deployment_mode": "local",
            "instance_name": "Alcove",
        },
    )
    monkeypatch.setattr(trust, "list_plugins", lambda: [{"name": "demo", "type": "embedder", "module": "demo.mod:Embedder", "distribution_version": "0.1.0"}])
    monkeypatch.setenv("VECTOR_BACKEND", "chromadb")
    monkeypatch.setenv("EMBEDDER", "hash")

    report = trust.build_trust_report()

    assert report["alcove"]["install_source"] == "editable local checkout"
    assert report["backend"]["name"] == "chromadb"
    assert report["embedder"]["name"] == "hash"
    native_names = {pkg["name"] for pkg in report["packages"]["native"]}
    pure_names = {pkg["name"] for pkg in report["packages"]["pure_python"]}
    missing_names = {pkg["name"] for pkg in report["packages"]["missing"]}
    assert "chromadb" in native_names
    assert "fastapi" in pure_names
    assert "sentence-transformers" in missing_names
    assert report["plugins"]["installed"][0]["name"] == "demo"


def test_build_trust_report_with_allowlist_and_zvec(monkeypatch):
    from alcove import trust

    monkeypatch.setattr(trust, "_collect_package_details", lambda: [])
    monkeypatch.setattr(trust, "_alcove_info", lambda: {"version": "0.4.0"})
    monkeypatch.setattr(trust, "_python_info", lambda: {"version": "3.12.0"})
    monkeypatch.setattr(trust, "_runtime_info", lambda: {"config_path": "alcove.toml", "private_mode": True})
    monkeypatch.setattr(
        trust,
        "_backend_info",
        lambda: {
            "name": "zvec",
            "implementation": "alcove.index.backend.ZvecBackend",
            "storage_path": "./data/zvec",
            "telemetry_posture": "unknown",
            "network_posture": "local disk only by default",
        },
    )
    monkeypatch.setattr(
        trust,
        "_embedder_info",
        lambda: {
            "name": "custom",
            "implementation": "acme.Custom",
            "source": "plugin",
            "network_posture": "depends on plugin implementation",
        },
    )
    monkeypatch.setattr(trust, "load_index_provenance", lambda: {"version": 1, "collections": {}})
    monkeypatch.setattr(trust, "list_plugins", lambda: [])
    monkeypatch.setenv("ALCOVE_PLUGIN_ALLOWLIST", "safe-plugin")

    report = trust.build_trust_report()

    assert report["plugins"]["allowlist"] == "safe-plugin"
    assert report["backend"]["name"] == "zvec"
    assert report["embedder"]["source"] == "plugin"


def test_print_trust_report_includes_core_sections(capsys):
    from alcove.trust import print_trust_report

    report = {
        "python": {
            "executable": "/usr/bin/python3",
            "version": "3.12.1",
            "platform": "macOS",
            "in_virtualenv": True,
            "prefix": "/tmp/venv",
        },
        "alcove": {
            "version": "0.4.0",
            "install_source": "editable local checkout",
            "module_path": "/tmp/alcove",
        },
        "runtime": {
            "config_path": "alcove.toml",
            "private_mode": True,
        },
        "backend": {
            "name": "chromadb",
            "implementation": "alcove.index.backend.ChromaBackend",
            "storage_path": "./data/chroma",
            "telemetry_posture": "disabled",
            "network_posture": "local disk only by default",
        },
        "embedder": {
            "name": "sentence-transformers",
            "implementation": "alcove.index.embedder.SentenceTransformerEmbedder",
            "source": "builtin",
            "network_posture": "offline after optional one-time model download",
            "model": {
                "identifier": "all-MiniLM-L6-v2",
                "source": "huggingface:sentence-transformers/all-MiniLM-L6-v2",
                "local_path": None,
                "revision": None,
            },
        },
        "packages": {
            "native": [{"name": "chromadb", "version": "1.0.0", "role": "vector_backend", "installed": True}],
            "pure_python": [{"name": "fastapi", "version": "0.115.0", "role": "web", "installed": True}],
            "missing": [{"name": "zvec", "version": None, "role": "vector_backend", "installed": False}],
        },
        "plugins": {
            "allowlist": "demo-plugin",
            "installed": [{"name": "demo", "type": "embedder", "module": "demo.mod:Embedder", "distribution_version": "0.1.0"}],
        },
    }

    print_trust_report(report)
    out = capsys.readouterr().out
    assert "Trust Doctor" in out
    assert "Plugins" in out
    assert "Native extension packages" in out
    assert "Pure Python packages" in out
    assert "Not installed" in out


def test_print_trust_report_includes_provenance_and_empty_plugin_sections(capsys):
    from alcove.trust import print_trust_report

    report = {
        "python": {
            "executable": "/usr/bin/python3",
            "version": "3.12.1",
            "platform": "macOS",
            "in_virtualenv": False,
            "prefix": "/usr",
        },
        "alcove": {
            "version": "0.4.0",
            "install_source": "installed package",
            "module_path": "/tmp/alcove",
        },
        "runtime": {
            "config_path": "alcove.toml",
            "private_mode": True,
        },
        "backend": {
            "name": "zvec",
            "implementation": "alcove.index.backend.ZvecBackend",
            "storage_path": "./data/zvec",
            "telemetry_posture": "unknown",
            "network_posture": "local disk only by default",
        },
        "embedder": {
            "name": "hash",
            "implementation": "alcove.index.embedder.HashEmbedder",
            "source": "builtin",
            "network_posture": "offline",
        },
        "index_provenance": {
            "collections": {
                "docs": {
                    "indexed_at": "2026-05-15T10:00:00+00:00",
                    "chunk_count": 4,
                    "embedder": {"embedding_dimension": 384, "model": {}},
                }
            }
        },
        "packages": {"native": [], "pure_python": [], "missing": []},
        "plugins": {"allowlist": "", "installed": []},
    }

    print_trust_report(report)
    out = capsys.readouterr().out
    assert "Index provenance" in out
    assert "collection:          docs" in out
    assert "installed:           none" in out
    assert "  (none)" in out


def test_print_trust_report_includes_model_receipt(capsys):
    from alcove.trust import print_trust_report

    report = {
        "python": {
            "executable": "/usr/bin/python3",
            "version": "3.12.1",
            "platform": "macOS",
            "in_virtualenv": False,
            "prefix": "/usr",
        },
        "alcove": {
            "version": "0.4.0",
            "install_source": "installed package",
            "module_path": "/tmp/alcove",
        },
        "runtime": {"config_path": "alcove.toml", "private_mode": True},
        "backend": {
            "name": "chromadb",
            "implementation": "alcove.index.backend.ChromaBackend",
            "storage_path": "./data/chroma",
            "telemetry_posture": "disabled",
            "network_posture": "local disk only by default",
        },
        "embedder": {
            "name": "sentence-transformers",
            "implementation": "alcove.index.embedder.SentenceTransformerEmbedder",
            "source": "builtin",
            "network_posture": "offline after optional one-time model download",
        },
        "index_provenance": {
            "collections": {
                "docs": {
                    "indexed_at": "2026-05-15T10:00:00+00:00",
                    "chunk_count": 4,
                    "embedder": {
                        "embedding_dimension": 384,
                        "model": {"identifier": "all-MiniLM-L6-v2", "revision": "abc123"},
                    },
                }
            }
        },
        "packages": {"native": [], "pure_python": [], "missing": []},
        "plugins": {"allowlist": "", "installed": []},
    }

    print_trust_report(report)
    assert "model receipt:       all-MiniLM-L6-v2 @ abc123" in capsys.readouterr().out


def test_helper_functions_cover_edge_cases(monkeypatch, tmp_path):
    from alcove import trust

    assert trust._format_virtualenv({"in_virtualenv": False}) == "no"
    assert trust._format_virtualenv({"in_virtualenv": True, "prefix": None}) == "yes ((unknown))"

    monkeypatch.setenv("VECTOR_BACKEND", "zvec")
    monkeypatch.setenv("ZVEC_PATH", str(tmp_path / "zvec"))
    backend = trust._backend_info()
    assert backend["storage_path"] == str(tmp_path / "zvec")

    monkeypatch.setenv("EMBEDDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "custom-model")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embedder = trust._embedder_info()
    assert embedder["model"]["identifier"] == "custom-model"
    assert trust._embedder_network_posture("unknown-plugin") == "depends on plugin implementation"

    class FakeDist:
        def __init__(self, text):
            self._text = text

        def read_text(self, name):
            return self._text

        def locate_file(self, path):
            return "/workspace/project"

    assert trust._detect_install_source(FakeDist("{bad json")) == "local source tree"


def test_trust_helpers_cover_remaining_install_and_cache_paths(monkeypatch, tmp_path):
    from alcove import trust

    class RaisingDist:
        def read_text(self, name):
            raise OSError("boom")

        def locate_file(self, path):
            return "/tmp/site-packages/pkg"

    class DirectUrlDist:
        def __init__(self, payload, root="/tmp/project"):
            self._payload = payload
            self._root = root

        def read_text(self, name):
            return self._payload

        def locate_file(self, path):
            return self._root

    assert trust._detect_install_source(RaisingDist()) == "installed package"
    assert (
        trust._detect_install_source(
            DirectUrlDist('{"url":"https://github.com/acme/repo","vcs_info":{"vcs":"git"}}')
        )
        == "git checkout (https://github.com/acme/repo)"
    )
    assert trust._detect_install_source(DirectUrlDist('{"url":"file:///tmp/pkg.whl"}')) == "local file install"
    assert trust._detect_install_source(DirectUrlDist('{"url":"https://example.com/pkg.whl"}')) == "https://example.com/pkg.whl"

    monkeypatch.setattr(
        trust,
        "entry_points",
        lambda *, group: [SimpleNamespace(name="demo", value="demo.plugin:Impl")] if group == trust.EMBEDDERS_GROUP else [],
    )
    assert trust._plugin_target(trust.EMBEDDERS_GROUP, "demo") == "demo.plugin:Impl"
    assert trust._plugin_target(trust.EMBEDDERS_GROUP, "missing") is None
    assert trust._embedder_network_posture("hash") == "offline"
    assert trust._embedder_network_posture("sentence-transformers") == "offline after optional one-time model download"
    assert (
        trust._embedder_network_posture("ollama")
        == "local HTTP to Ollama by default; remote if OLLAMA_BASE_URL points elsewhere"
    )

    hf_home = tmp_path / "hf-home"
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.setenv("HF_HOME", str(hf_home))
    repo_dir = hf_home / "hub" / "models--sentence-transformers--custom-model"
    (repo_dir / "snapshots").mkdir(parents=True)
    cache = trust._huggingface_model_cache("sentence-transformers/custom-model")
    assert cache["local_path"] == str(repo_dir)
    assert cache["revision"] is None

    assert trust._huggingface_model_cache("sentence-transformers/missing-model") == {
        "local_path": None,
        "revision": None,
    }

    monkeypatch.setenv("SENTENCE_TRANSFORMERS_MODEL", "acme/custom-model")
    model = trust._embedder_model_info("sentence-transformers")
    assert model["identifier"] == "acme/custom-model"
    assert model["source"] == "huggingface:acme/custom-model"

    assert trust._embedder_model_info("missing-plugin") is None


def test_collect_package_details_skips_duplicates(monkeypatch):
    from alcove import trust

    monkeypatch.setattr(trust, "_PACKAGE_GROUPS", [("fastapi", "web"), ("FASTAPI", "duplicate"), ("uvicorn", "web")])
    monkeypatch.setattr(
        trust,
        "_package_detail",
        lambda package_name, role: {"name": package_name, "role": role, "installed": True, "version": "1.0.0"},
    )

    details = trust._collect_package_details()

    assert details == [
        {"name": "fastapi", "role": "web", "installed": True, "version": "1.0.0"},
        {"name": "uvicorn", "role": "web", "installed": True, "version": "1.0.0"},
    ]
