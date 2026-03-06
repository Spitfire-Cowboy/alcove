#!/usr/bin/env python3
"""
Fetch the founders seed corpus defined in seed_manifest_founders.json.
Downloads all documents to data/raw/seed-founders/.

Empty sha256 list ([]) is treated the same as allow_hash_drift=true.
"""
import hashlib
import json
import pathlib
import sys
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "scripts" / "seed_manifest_founders.json"
OUT_DIR = ROOT / "data" / "raw" / "seed-founders"


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


def _hash_drift_allowed(entry: dict) -> bool:
    """Empty sha256 list [] counts as allow_hash_drift=true."""
    sha = entry["sha256"]
    if isinstance(sha, list) and len(sha) == 0:
        return True
    return entry.get("allow_hash_drift", False)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_one(entry: dict, out_dir: pathlib.Path = OUT_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / entry["filename"]

    with urllib.request.urlopen(entry["url"], timeout=30) as resp:
        data = resp.read()

    digest = sha256_bytes(data)
    allowed = _allowed_hashes(entry["sha256"])

    if allowed and digest not in allowed:
        # sha256 list was non-empty but didn't match
        if _hash_drift_allowed(entry):
            print(f"  warning: hash drift allowed for {entry['filename']} ({digest[:12]}...)")
            target.write_bytes(data)
            return target
        text = data.decode("utf-8", errors="ignore")
        markers = entry.get("must_contain") or []
        if markers and all(m in text for m in markers):
            print(
                f"  warning: hash drift for {entry['filename']} ({digest[:12]}...); "
                "accepted via content markers",
            )
        else:
            raise ValueError(
                f"Seed file '{entry['filename']}' appears corrupted or modified. "
                f"Expected one of {allowed}, got {digest}. "
                f"Delete {target} and re-run."
            )
    elif not allowed:
        # empty list — no hash to check, just verify content markers
        text = data.decode("utf-8", errors="ignore")
        markers = entry.get("must_contain") or []
        if markers and not all(m in text for m in markers):
            missing_markers = [m for m in markers if m not in text]
            raise ValueError(
                f"Seed file '{entry['filename']}': content markers not found: {missing_markers}"
            )
        print(f"  note: no sha256 for {entry['filename']}, accepted (hash drift allowed)")

    target.write_bytes(data)
    return target


def main():
    print(f"Loading manifest: {MANIFEST_PATH}")
    manifest = load_manifest()
    print(f"Found {len(manifest)} entries. Output dir: {OUT_DIR}\n")

    ok = []
    failed = []

    for entry in manifest:
        eid = entry["id"]
        print(f"[{len(ok) + len(failed) + 1}/{len(manifest)}] {eid}")
        print(f"  url: {entry['url']}")
        try:
            path = fetch_one(entry)
            size_kb = path.stat().st_size / 1024
            print(f"  OK  -> {path.relative_to(ROOT)}  ({size_kb:.1f} KB)")
            ok.append(eid)
        except urllib.error.URLError as exc:
            print(f"  FAIL (network): {exc}")
            failed.append((eid, str(exc)))
        except ValueError as exc:
            print(f"  FAIL (validation): {exc}")
            failed.append((eid, str(exc)))
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL (unexpected): {type(exc).__name__}: {exc}")
            failed.append((eid, str(exc)))
        print()

    print("=" * 60)
    print(f"Results: {len(ok)} succeeded, {len(failed)} failed")
    print()

    if ok:
        print("Succeeded:")
        for eid in ok:
            print(f"  + {eid}")

    if failed:
        print()
        print("Failed:")
        for eid, reason in failed:
            print(f"  - {eid}: {reason}")
        sys.exit(1)
    else:
        print(f"\nDone: all {len(manifest)} founders seed docs fetched to {OUT_DIR}")


if __name__ == "__main__":
    main()
