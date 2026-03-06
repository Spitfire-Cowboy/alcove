import json
from pathlib import Path

from scripts.fetch_seed_corpus import load_manifest, sha256_bytes


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_entries_have_required_fields():
    manifest = load_manifest()
    assert len(manifest) >= 5
    for item in manifest:
        for key in ("id", "filename", "url", "sha256", "license", "source"):
            assert key in item


def test_manifest_filenames_unique():
    manifest = load_manifest()
    names = [m["filename"] for m in manifest]
    assert len(names) == len(set(names))


def test_sha256_helper_matches_known_value():
    assert sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
