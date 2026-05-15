from __future__ import annotations

import argparse
import os
import socket
import urllib.request
from contextlib import contextmanager


@contextmanager
def block_outbound_network(monkeypatch):
    def fail_urlopen(*args, **kwargs):
        raise AssertionError("unexpected outbound HTTP request in offline runtime path")

    def fail_create_connection(*args, **kwargs):
        raise AssertionError("unexpected outbound socket connection in offline runtime path")

    original_socket = socket.socket

    class GuardedSocket(original_socket):
        def connect(self, address):
            raise AssertionError(f"unexpected socket connect in offline runtime path: {address!r}")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    monkeypatch.setattr(socket, "create_connection", fail_create_connection)
    monkeypatch.setattr(socket, "socket", GuardedSocket)
    yield


def test_hash_runtime_paths_make_no_outbound_network_calls(tmp_path, monkeypatch):
    from alcove.cli import cmd_status
    from alcove.index.pipeline import run as index_run
    from alcove.ingest.pipeline import run as ingest_run
    from alcove.query.retriever import query_text
    from alcove.trust import build_trust_report

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "hello.txt").write_text("hello local alcove world", encoding="utf-8")

    chunks_file = tmp_path / "chunks.jsonl"
    chroma_dir = tmp_path / "chroma"

    monkeypatch.setenv("RAW_DIR", str(raw_dir))
    monkeypatch.setenv("CHUNKS_FILE", str(chunks_file))
    monkeypatch.setenv("CHROMA_PATH", str(chroma_dir))
    monkeypatch.setenv("VECTOR_BACKEND", "chromadb")
    monkeypatch.setenv("EMBEDDER", "hash")
    monkeypatch.delenv("ALCOVE_DEMO_ROOT", raising=False)
    monkeypatch.delenv("ALCOVE_MULTI_COLLECTION", raising=False)
    monkeypatch.delenv("CHROMA_COLLECTION", raising=False)

    with block_outbound_network(monkeypatch):
        assert ingest_run(raw_dir=str(raw_dir), out_file=str(chunks_file)) >= 1
        assert index_run(chunks_file=str(chunks_file), collection="default") >= 1
        result = query_text("hello", n_results=3)
        assert result["ids"][0]
        cmd_status(argparse.Namespace())
        report = build_trust_report()

    assert report["backend"]["name"] == "chromadb"
    assert report["embedder"]["name"] == "hash"
    assert report["index_provenance"]["collections"]["default"]["embedder"]["name"] == "hash"


def test_chromadb_backend_forces_telemetry_off(tmp_path, monkeypatch):
    from alcove.index.backend import ChromaBackend
    from alcove.index.embedder import HashEmbedder

    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)

    ChromaBackend(HashEmbedder())

    assert os.environ["ANONYMIZED_TELEMETRY"] == "False"
