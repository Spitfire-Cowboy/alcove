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
