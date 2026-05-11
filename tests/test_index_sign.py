from __future__ import annotations

import importlib.util
import json
import stat
import sys
from pathlib import Path


_SCRIPT = Path(__file__).parent.parent / "tools" / "index-sign" / "sign.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("index_sign", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["index_sign"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_mod = _load_module()
sign_index = _mod.sign_index
verify_signed_index = _mod.verify_signed_index
SIGNED_INDEX_VERSION = _mod.SIGNED_INDEX_VERSION


_SAMPLE_INDEX = {
    "alcove_sync_version": 1,
    "exported_at": "2026-01-01T00:00:00+00:00",
    "collections": {
        "docs": {
            "ids": ["a", "b"],
            "documents": ["doc a", "doc b"],
            "metadatas": [{"source": "a.md"}, {"source": "b.md"}],
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
        }
    },
}


def test_sign_index_returns_versioned_envelope_and_creates_key(tmp_path) -> None:
    key_path = tmp_path / "alcove.key"
    envelope = sign_index(_SAMPLE_INDEX, key_path, signed_at="2026-01-01T00:00:00+00:00")

    assert envelope["alcove_signed_index_version"] == SIGNED_INDEX_VERSION
    assert envelope["signed_at"] == "2026-01-01T00:00:00+00:00"
    assert envelope["index"] == _SAMPLE_INDEX
    assert envelope["index_hash"].startswith("sha256:")
    assert "PUBLIC KEY" in envelope["signer_public_key_pem"]
    assert key_path.is_file()
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


def test_sign_index_rejects_unsupported_index_export_version(tmp_path) -> None:
    index = dict(_SAMPLE_INDEX, alcove_sync_version=2)

    try:
        sign_index(index, tmp_path / "alcove.key")
    except ValueError as exc:
        assert "alcove_sync_version 1" in str(exc)
    else:
        raise AssertionError("expected sign_index to reject unsupported export version")


def test_verify_signed_index_accepts_valid_envelope(tmp_path) -> None:
    envelope = sign_index(_SAMPLE_INDEX, tmp_path / "alcove.key")
    assert verify_signed_index(envelope) is True


def test_verify_signed_index_rejects_unsupported_or_missing_version(tmp_path) -> None:
    envelope = sign_index(_SAMPLE_INDEX, tmp_path / "alcove.key")
    envelope["alcove_signed_index_version"] = 99
    assert verify_signed_index(envelope) is False

    del envelope["alcove_signed_index_version"]
    assert verify_signed_index(envelope) is False


def test_verify_signed_index_rejects_tampering(tmp_path) -> None:
    envelope = sign_index(_SAMPLE_INDEX, tmp_path / "alcove.key")
    envelope["index"]["collections"]["docs"]["ids"].append("injected")
    assert verify_signed_index(envelope) is False


def test_verify_signed_index_rejects_hash_signature_key_and_fingerprint_changes(tmp_path) -> None:
    envelope = sign_index(_SAMPLE_INDEX, tmp_path / "alcove.key")

    bad_hash = dict(envelope, index_hash="sha256:" + "a" * 64)
    assert verify_signed_index(bad_hash) is False

    bad_signature = dict(envelope, index_signature="AAAA")
    assert verify_signed_index(bad_signature) is False

    bad_key = dict(envelope, signer_public_key_pem="not-a-pem")
    assert verify_signed_index(bad_key) is False

    bad_fingerprint = dict(envelope, signer_fingerprint="0" * 32)
    assert verify_signed_index(bad_fingerprint) is False


def test_cli_sign_verify_and_export_pubkey(tmp_path) -> None:
    index_path = tmp_path / "dump.json"
    signed_path = tmp_path / "dump.signed.json"
    key_path = tmp_path / "alcove.key"
    pubkey_path = tmp_path / "pubkey.pem"
    index_path.write_text(json.dumps(_SAMPLE_INDEX))

    assert _mod.main(["sign", "--index", str(index_path), "--key", str(key_path), "--out", str(signed_path)]) == 0
    assert signed_path.is_file()
    assert verify_signed_index(json.loads(signed_path.read_text()))

    assert _mod.main(["verify", "--signed", str(signed_path)]) == 0
    assert _mod.main(["export-pubkey", "--key", str(key_path), "--out", str(pubkey_path)]) == 0
    assert b"PUBLIC KEY" in pubkey_path.read_bytes()


def test_cli_missing_files_return_nonzero(tmp_path) -> None:
    assert _mod.main(["sign", "--index", str(tmp_path / "missing.json"), "--key", str(tmp_path / "k"), "--out", str(tmp_path / "o")]) != 0
    assert _mod.main(["verify", "--signed", str(tmp_path / "missing.signed.json")]) != 0
    assert _mod.main(["export-pubkey", "--key", str(tmp_path / "missing.key"), "--out", str(tmp_path / "pub.pem")]) != 0
