#!/usr/bin/env python3
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
INDEX = ROOT / "data" / "processed" / "seed_index.json"


def main():
    if not CHUNKS.exists():
        raise SystemExit("Missing chunks. Run ingest first.")

    per_source = Counter()
    total = 0
    with CHUNKS.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            per_source[row["source"]] += 1
            total += 1

    payload = {
        "total_chunks": total,
        "sources": dict(per_source),
        "note": "Tiny deterministic demo index artifact",
    }
    INDEX.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote index summary -> {INDEX}")


if __name__ == "__main__":
    main()
