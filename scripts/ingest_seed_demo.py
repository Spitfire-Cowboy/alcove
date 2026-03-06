#!/usr/bin/env python3
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "raw" / "seed"
OUT = ROOT / "data" / "processed" / "chunks.jsonl"


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk(text: str, size: int = 900):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i : i + size])


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in SEED_DIR.glob("*") if p.is_file()])
    if not files:
        raise SystemExit("No seed files found. Run: python3 scripts/fetch_seed_corpus.py")

    count = 0
    with OUT.open("w", encoding="utf-8") as f:
        for path in files:
            text = clean_text(path.read_text(errors="ignore"))
            for idx, c in enumerate(chunk(text), start=1):
                rec = {"id": f"{path.stem}:{idx}", "source": path.name, "chunk": c}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1

    print(f"wrote {count} chunks -> {OUT}")


if __name__ == "__main__":
    main()
