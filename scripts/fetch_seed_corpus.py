#!/usr/bin/env python3
import hashlib
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "scripts" / "seed_manifest.json"
OUT_DIR = ROOT / "data" / "raw" / "seed"


def load_manifest(path: pathlib.Path = MANIFEST_PATH):
    data = json.loads(path.read_text())
    required = {"id", "filename", "url", "sha256", "license", "source"}
    for item in data:
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Manifest entry missing keys: {missing} :: {item}")
    return data


def _allowed_hashes(value):
    if isinstance(value, list):
        return set(value)
    return {value}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_one(entry: dict, out_dir: pathlib.Path = OUT_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / entry["filename"]

    with urllib.request.urlopen(entry["url"]) as resp:
        data = resp.read()

    digest = sha256_bytes(data)
    if digest not in _allowed_hashes(entry["sha256"]):
        if entry.get("allow_hash_drift", False):
            print(f"warning: hash drift allowed for {entry['filename']} ({digest})")
            target.write_bytes(data)
            return target
        text = data.decode("utf-8", errors="ignore")
        markers = entry.get("must_contain") or []
        if markers and all(m in text for m in markers):
            print(
                f"warning: hash drift for {entry['filename']} ({digest}); "
                "accepted via content markers",
            )
        else:
            raise ValueError(
                f"Seed file '{entry['filename']}' appears corrupted or modified. "
                f"Expected one of {_allowed_hashes(entry['sha256'])}, got {digest}. "
                f"Delete data/raw/seed/{entry['filename']} and re-run make seed-demo."
            )

    target.write_bytes(data)
    return target


def main():
    manifest = load_manifest()
    for entry in manifest:
        path = fetch_one(entry)
        print(f"fetched {entry['id']} -> {path}")
    print(f"done: {len(manifest)} seed docs")


if __name__ == "__main__":
    main()
